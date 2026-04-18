"""
youtube_shorts_publisher/settings.py

Reads runtime flags from runtime_settings.json (written by the launcher)
so the mode can be changed without touching this file.
Falls back to hardcoded defaults when no override file exists.
"""
import json
import os

from gemjam import GEMJAM

_RUNTIME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runtime_settings.json")


def _load_runtime() -> dict:
    if os.path.exists(_RUNTIME_FILE):
        try:
            with open(_RUNTIME_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


_cfg = _load_runtime()

PROCESS_SINGLE_VIDEO    = _cfg.get("PROCESS_SINGLE_VIDEO",    False)
ENABLE_SCRAPING_MODE    = _cfg.get("ENABLE_SCRAPING_MODE",    False)
ENABLE_ANALYSIS_MODE    = _cfg.get("ENABLE_ANALYSIS_MODE",    False)
ENABLE_UPLOAD_MODE      = _cfg.get("ENABLE_UPLOAD_MODE",      True)
UPLOAD_LIMIT            = _cfg.get("UPLOAD_LIMIT",            0)
VIDEOS_TO_PROCESS_COUNT = _cfg.get("VIDEOS_TO_PROCESS_COUNT", 100)
GEMINI_API_KEY          = GEMJAM