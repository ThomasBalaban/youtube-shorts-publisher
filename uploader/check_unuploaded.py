"""
uploader/check_unuploaded.py

Audits the shorts-auto-editor output folder against:
  - uploaded_files.json                       (additive local log of past uploads)
  - saved_shorts_data/draft_videos.json       (current YT Studio drafts)
  - saved_shorts_data/scheduled_videos.json   (current YT Studio scheduled)

A file is "uploaded" if EITHER the local log lists it OR its filename
maps to a title that appears in the latest YT scrape (drafts or
scheduled). The union is safer than either signal alone — the log can
miss uploads done manually, and the scrape can lag behind a recent
batch.

Files are bucketed into:
  (1) Not on YouTube        — needs upload, KEPT on disk
  (2) Uploaded, still draft — already on YT, trashed
  (3) Uploaded, scheduled   — already on YT, trashed
  (4) Logged but absent from
      both drafts and       — published, trashed
      scheduled

Run this when the uploader reports nothing to do but you suspect files
are still sitting in shorts-auto-editor/output/.

Anything that has made it onto YouTube (draft, scheduled, or published)
gets moved to the macOS Trash. Only files NOT yet on YouTube stay on
disk so the uploader can pick them up.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None

# Re-use the strategist client so the audit knows BOTH possible YT titles
# for any given file: (a) the raw filename-derived title before the
# publisher renames it, and (b) the strategist's recommended title after
# the publisher renames the draft. Without (b) the audit would mis-bucket
# any file whose YT draft has already been retitled.
from publisher.strategist_client import _filename_to_yt, StrategistClient

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_THIS_FILE     = Path(__file__).resolve()
_PROJECT_DIR   = _THIS_FILE.parent.parent
_SHARED_PARENT = _PROJECT_DIR.parent
OUTPUT_DIR     = _SHARED_PARENT / "shorts-auto-editor" / "output"
UPLOADED_LOG   = _PROJECT_DIR / "uploader" / "uploaded_files.json"
SCRAPE_DIR     = _PROJECT_DIR / "saved_shorts_data"
DRAFT_SCRAPE   = SCRAPE_DIR / "draft_videos.json"
SCHED_SCRAPE   = SCRAPE_DIR / "scheduled_videos.json"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[Audit] Warning: could not parse {path.name}: {e}")
        return None


def load_uploaded_log() -> Set[str]:
    data = _load_json(UPLOADED_LOG)
    if not isinstance(data, list):
        print(f"[Audit] No uploaded log at {UPLOADED_LOG} — treating as empty.")
        return set()
    return set(data)


def load_scrape_titles(path: Path, label: str) -> Set[str]:
    data = _load_json(path)
    if data is None:
        print(f"[Audit] No {label} scrape at {path.name} — treating as empty.")
        return set()
    titles = set()
    for entry in data:
        t = (entry.get("title") or "").strip() if isinstance(entry, dict) else ""
        if t:
            titles.add(t)
    return titles


def get_output_videos() -> List[Path]:
    if not OUTPUT_DIR.exists():
        print(f"[Audit] Output folder does not exist: {OUTPUT_DIR}")
        return []
    return [
        f for f in sorted(OUTPUT_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------

def _candidate_titles(filename: str, client: StrategistClient) -> Set[str]:
    """Every YT title this filename could plausibly be sitting under.

    Before the publisher runs, the YT draft title is the
    filename-with-dashes-replaced-by-spaces form. After the publisher
    runs, the draft has been renamed to the strategist's recommended
    title. We have to check both.
    """
    titles = {_filename_to_yt(filename)}
    pre_rename = _filename_to_yt(filename)
    meta = client.lookup_by_draft_title(pre_rename)
    if meta and meta.title:
        titles.add(meta.title)
    return titles


def _bucket_videos(
    videos: List[Path],
    uploaded_log: Set[str],
    draft_titles: Set[str],
    scheduled_titles: Set[str],
    client: StrategistClient,
) -> Dict[str, List[Path]]:
    """Return one list per bucket key."""
    buckets: Dict[str, List[Path]] = {
        "not_uploaded": [],
        "draft":        [],
        "scheduled":    [],
        "published":    [],
    }
    for v in videos:
        candidates = _candidate_titles(v.name, client)
        in_log   = v.name in uploaded_log
        in_draft = bool(candidates & draft_titles)
        in_sched = bool(candidates & scheduled_titles)

        if in_draft:
            buckets["draft"].append(v)
        elif in_sched:
            buckets["scheduled"].append(v)
        elif in_log:
            # Logged as uploaded but no longer on YT's draft/scheduled lists
            # → already published, safe to clean up.
            buckets["published"].append(v)
        else:
            buckets["not_uploaded"].append(v)
    return buckets


# ---------------------------------------------------------------------------
# Trashing
# ---------------------------------------------------------------------------

def _trash_all_videos(videos: List[Path]) -> None:
    if not videos:
        return
    if send2trash is None:
        print(
            "[Audit] 'send2trash' is not installed — cannot move files to Trash.\n"
            "        Run:  pip install send2trash"
        )
        return

    print(f"\n[Audit] Moving {len(videos)} file(s) already on YouTube to Trash...")
    failed: List[Path] = []
    for v in videos:
        try:
            send2trash(str(v))
            print(f"  🗑  {v.name}")
        except Exception as e:
            print(f"  ✗  {v.name}  ({e})")
            failed.append(v)

    if failed:
        print(f"\n[Audit] Warning: {len(failed)} file(s) could not be trashed.")
    else:
        print("[Audit] All on-YouTube files moved to Trash successfully.")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_bucket(label: str, marker: str, videos: List[Path]) -> None:
    if not videos:
        return
    print(f"\n── {label} ({len(videos)}) ──")
    for v in videos:
        print(f"  {marker}  {v.name}")


def run_audit():
    print(f"\n=== UPLOAD AUDIT ===")
    print(f"Output folder    : {OUTPUT_DIR}")
    print(f"Local upload log : {UPLOADED_LOG}")
    print(f"YT draft scrape  : {DRAFT_SCRAPE}")
    print(f"YT sched scrape  : {SCHED_SCRAPE}")

    uploaded_log     = load_uploaded_log()
    draft_titles     = load_scrape_titles(DRAFT_SCRAPE, "drafts")
    scheduled_titles = load_scrape_titles(SCHED_SCRAPE, "scheduled")
    videos           = get_output_videos()
    client           = StrategistClient()

    print(f"\nLog entries      : {len(uploaded_log)}")
    print(f"YT drafts        : {len(draft_titles)}")
    print(f"YT scheduled     : {len(scheduled_titles)}")
    print(f"Strategist videos: {client.summary().get('canonical_videos', 0)}")
    print(f"Output files     : {len(videos)}")

    if not videos:
        print("\n[Audit] Output folder is empty — nothing to audit.")
        return

    buckets = _bucket_videos(videos, uploaded_log, draft_titles, scheduled_titles, client)

    print(f"\nNot on YouTube — KEEP   : {len(buckets['not_uploaded'])}")
    print(f"Drafts — TRASH          : {len(buckets['draft'])}")
    print(f"Scheduled — TRASH       : {len(buckets['scheduled'])}")
    print(f"Published — TRASH       : {len(buckets['published'])}")

    _print_bucket("Files NOT yet on YouTube (kept)",      "✗",  buckets["not_uploaded"])
    _print_bucket("Files uploaded, still drafts (trash)", "📝", buckets["draft"])
    _print_bucket("Files uploaded and scheduled (trash)", "⏰", buckets["scheduled"])
    _print_bucket("Files published (trash)",              "✓",  buckets["published"])

    on_youtube = buckets["draft"] + buckets["scheduled"] + buckets["published"]
    _trash_all_videos(on_youtube)


if __name__ == "__main__":
    run_audit()
