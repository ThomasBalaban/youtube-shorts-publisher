"""
Strategist client.

Reads title + metadata recommendations from the sibling shorts_strategist
project and exposes them to the publisher via a simple lookup keyed by the
YT Studio draft title.

Join logic:
  draft_title (e.g. "Backtrack 2026 04 24 20 26 30 as")
    → reverse YT's transform: replace spaces with dashes, append ".mp4"
    → look up in canonical map: {output_filename → shorts_metadata base_key}
    → when several metadata records share an output_filename, the latest
      file_info.shipped_at wins (that's the live record for the upload
      currently sitting on disk)
    → read titles/<base>.json + metadata/<base>.json from the strategist
    → return DraftMetadata
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_THIS_FILE      = Path(__file__).resolve()
_PROJECT_DIR    = _THIS_FILE.parent.parent       # youtube_shorts_publisher/
_SHARED_PARENT  = _PROJECT_DIR.parent             # youtube-automator/

SHORTS_DATA_DIR     = _SHARED_PARENT / "shorts-auto-editor" / "shorts_data"
STRATEGIST_RECS_DIR = _SHARED_PARENT / "shorts_strategist" / "output" / "recommendations"


@dataclass
class DraftMetadata:
    """Everything the publisher needs to fill a YouTube Studio draft."""
    base_key:        str            # "shorts_metadata_19"
    output_filename: str            # "Backtrack 2026-04-24 20-26-30-as.mp4"
    title:           Optional[str]  # from strategist title rec (or fallback)
    title_source:    str            # "strategist" | "auto_editor" | "missing"
    description:     Optional[str]
    hashtags:        List[str]      = field(default_factory=list)
    tags:            Optional[str]  = None


def _filename_to_yt(filename: str) -> str:
    """Forward transform: strip .mp4, replace dashes with spaces.

    YT Studio shows uploaded ``<name>.mp4`` files as ``<name with dashes
    replaced by spaces>``. The reverse direction is ambiguous (original
    spaces collapse with the dash-derived spaces), so we never invert it
    — we key the canonical map by the forward-transformed title instead.
    """
    if filename.endswith(".mp4"):
        filename = filename[:-4]
    return filename.replace("-", " ")


def _read_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _build_canonical_map() -> Dict[str, Dict[str, str]]:
    """Walk shorts_metadata_*.json, return {yt_title: {base_key, output_filename}}.

    When multiple metadata records resolve to the same YT-style title
    (because their output_filenames collide), the one with the latest
    file_info.shipped_at wins. That's the record for the file currently
    sitting at shorts-auto-editor/output/<filename>.
    """
    by_yt: Dict[str, Dict[str, str]] = {}
    if not SHORTS_DATA_DIR.is_dir():
        return {}

    pattern = str(SHORTS_DATA_DIR / "shorts_metadata_*.json")
    for path in sorted(glob.glob(pattern)):
        body = _read_json(Path(path))
        if not body:
            continue
        record = body[0] if isinstance(body, list) and body else body
        if not isinstance(record, dict):
            continue
        file_info = record.get("file_info") or {}
        out = file_info.get("output_filename")
        if not out:
            continue
        yt_title = _filename_to_yt(out)
        shipped_at = file_info.get("shipped_at") or ""
        base_key = os.path.basename(path)[:-5]  # strip ".json"
        existing = by_yt.get(yt_title)
        if existing is None or shipped_at > existing["shipped_at"]:
            by_yt[yt_title] = {
                "base_key":        base_key,
                "output_filename": out,
                "shipped_at":      shipped_at,
            }
    return by_yt


class StrategistClient:
    """Lazy in-memory index of strategist recommendations."""

    def __init__(self) -> None:
        self._by_yt_title = _build_canonical_map()

    def known_draft_titles(self) -> List[str]:
        """Every YT-style draft title that has a strategist artifact."""
        return list(self._by_yt_title.keys())

    def lookup_by_draft_title(self, draft_title: str) -> Optional[DraftMetadata]:
        info = self._by_yt_title.get(draft_title.strip())
        if not info:
            return None
        base_key        = info["base_key"]
        output_filename = info["output_filename"]

        title_art = _read_json(STRATEGIST_RECS_DIR / "titles"   / f"{base_key}.json") or {}
        meta_art  = _read_json(STRATEGIST_RECS_DIR / "metadata" / f"{base_key}.json") or {}
        tp = title_art.get("payload") or {}
        mp = meta_art.get("payload")  or {}

        # Resolve title by strategist verdict so the source label reflects
        # whose decision is shipping: "replace" → strategist's alternative,
        # "keep"/"tied" → strategist explicitly endorsed the auto-editor's
        # current title. "missing" means no strategist title rec exists.
        verdict = tp.get("verdict")
        recommended = tp.get("recommended_title")
        current = tp.get("current_title")
        if verdict == "replace" and recommended:
            title, source = recommended, "strategist_replace"
        elif verdict in ("keep", "tied") and current:
            title, source = current, f"strategist_{verdict}"
        elif recommended:                       # legacy artifacts w/o verdict
            title, source = recommended, "strategist_replace"
        elif current:
            title, source = current, "strategist_unknown_verdict"
        else:
            title, source = None, "missing"

        return DraftMetadata(
            base_key=base_key,
            output_filename=output_filename,
            title=title,
            title_source=source,
            description=mp.get("description"),
            hashtags=list(mp.get("hashtags") or []),
            tags=mp.get("tags"),
        )

    def summary(self) -> Dict[str, int]:
        """Quick counts for logging."""
        return {
            "canonical_videos": len(self._by_yt_title),
        }
