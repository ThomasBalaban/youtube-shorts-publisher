"""
uploader/check_unuploaded.py

Audits the simpleautosubs output folder against uploaded_files.json.
Run this if the uploader reports nothing to upload but you suspect
files are still sitting in the output folder.

If ALL files in the output folder are already uploaded (not_yet_uploaded == 0),
every video file is moved to the macOS Trash automatically.
"""

import json
from pathlib import Path

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None

# ---------------------------------------------------------------------------
# Paths (mirrors upload_video.py)
# ---------------------------------------------------------------------------
_THIS_FILE     = Path(__file__).resolve()
_PROJECT_DIR   = _THIS_FILE.parent.parent
_SHARED_PARENT = _PROJECT_DIR.parent
OUTPUT_DIR     = _SHARED_PARENT / "simpleautosubs" / "output"
UPLOADED_LOG   = _PROJECT_DIR / "uploader" / "uploaded_files.json"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# ---------------------------------------------------------------------------

def load_uploaded() -> set:
    if not UPLOADED_LOG.exists():
        print(f"[Audit] No uploaded_files.json found at {UPLOADED_LOG}")
        return set()
    with open(UPLOADED_LOG, "r") as f:
        return set(json.load(f))


def get_output_videos() -> list[Path]:
    if not OUTPUT_DIR.exists():
        print(f"[Audit] Output folder does not exist: {OUTPUT_DIR}")
        return []
    return [
        f for f in sorted(OUTPUT_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]


def _trash_all_videos(videos: list[Path]) -> None:
    """Move every file in the list to the macOS Trash."""
    if send2trash is None:
        print(
            "[Audit] 'send2trash' is not installed — cannot move files to Trash.\n"
            "        Run:  pip install send2trash"
        )
        return

    print(f"\n[Audit] Moving {len(videos)} file(s) to Trash...")
    failed = []
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
        print("[Audit] All files moved to Trash successfully.")


def run_audit():
    print(f"\n=== UPLOAD AUDIT ===")
    print(f"Output folder : {OUTPUT_DIR}")
    print(f"Uploaded log  : {UPLOADED_LOG}\n")

    uploaded = load_uploaded()
    videos   = get_output_videos()

    if not videos:
        print("[Audit] Output folder is empty — nothing to upload.")
        return

    not_uploaded = [v for v in videos if v.name not in uploaded]
    already_done = [v for v in videos if v.name in uploaded]

    print(f"Total files in output : {len(videos)}")
    print(f"Logged as uploaded    : {len(already_done)}")
    print(f"Not yet uploaded      : {len(not_uploaded)}")

    if not_uploaded:
        print("\n── Files NOT in uploaded_files.json ──")
        for v in not_uploaded:
            print(f"  ✗  {v.name}")
    else:
        print("[Audit] All files in output folder are already logged as uploaded.")
        _trash_all_videos(already_done)

    if already_done and not_uploaded:
        print("\n── Files already uploaded ──")
        for v in already_done:
            print(f"  ✓  {v.name}")


if __name__ == "__main__":
    run_audit()