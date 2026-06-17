"""Append-only log of drafts the publisher could not process.

A single bad draft used to halt the whole batch ("Critical error. Stopping
to prevent bad publishing."). Instead we now record the failure here, skip
the draft, and keep going — so one slow/odd draft doesn't block the rest.
Review or retry the recorded shorts later.

Mirrors the additive-log style of uploader/uploaded_files.json.
"""
import json
import time
from pathlib import Path

FAILED_LOG = Path(__file__).resolve().parent / "failed_shorts.json"


def record_failed_short(
    visible_title: str,
    reason: str,
    base_key: str = None,
    intended_title: str = None,
) -> Path:
    """Append one failure record to failed_shorts.json (created if absent)."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "visible_title": visible_title,
        "reason": reason,
        "base_key": base_key,
        "intended_title": intended_title,
    }

    data = []
    if FAILED_LOG.exists():
        try:
            with open(FAILED_LOG, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                data = loaded
        except Exception:
            # Corrupt/unreadable log — start fresh rather than crash the run.
            data = []

    data.append(entry)

    try:
        # tmp + replace so a crash mid-write can't corrupt the log.
        tmp = FAILED_LOG.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(FAILED_LOG)
    except Exception as e:
        print(f"[FailedLog] Could not write {FAILED_LOG}: {e}")

    return FAILED_LOG
