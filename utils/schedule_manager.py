import json
import os
from datetime import datetime, timedelta, time as dt_time

# ── Hub settings path ─────────────────────────────────────────────────────────
# Structure: shared_parent / youtube_hub / hub_settings.json
#            shared_parent / youtube_shorts_publisher / utils / schedule_manager.py
_UTILS_DIR       = os.path.dirname(os.path.abspath(__file__))
_PUBLISHER_DIR   = os.path.dirname(_UTILS_DIR)
_SHARED_PARENT   = os.path.dirname(_PUBLISHER_DIR)
_HUB_SETTINGS    = os.path.join(_SHARED_PARENT, "youtube_hub", "hub_settings.json")

DEFAULT_SCHEDULE_TIMES = ["10:00", "12:00", "16:00", "18:00", "20:00"]

def _load_schedule_times() -> list[dt_time]:
    """Load HH:MM strings from hub_settings.json and return as time objects."""
    raw = DEFAULT_SCHEDULE_TIMES
    try:
        if os.path.exists(_HUB_SETTINGS):
            with open(_HUB_SETTINGS, "r") as f:
                data = json.load(f)
            saved = data.get("schedule_times")
            if saved and isinstance(saved, list) and len(saved) > 0:
                raw = saved
    except Exception as e:
        print(f"   [Scheduler] Could not read hub_settings.json: {e}")

    times = []
    for s in raw:
        try:
            h, m = map(int, s.split(":"))
            times.append(dt_time(h, m))
        except Exception:
            pass
    return sorted(times) if times else [dt_time(10, 0), dt_time(12, 0), dt_time(16, 0), dt_time(18, 0), dt_time(20, 0)]

# ── Session memory ────────────────────────────────────────────────────────────
_session_occupied_slots: set = set()

def get_next_schedule_time():
    """
    Finds the next available slot from hub_settings.json schedule_times.
    Falls back to DEFAULT_SCHEDULE_TIMES if settings are unavailable.
    """
    json_path = os.path.join("saved_shorts_data", "scheduled_videos.json")
    occupied_slots: set = set()

    # 1. Load occupied slots from file
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            for video in data:
                if video.get("schedule") and video["schedule"].get("iso"):
                    try:
                        dt = datetime.fromisoformat(video["schedule"]["iso"]).replace(tzinfo=None)
                        occupied_slots.add(dt)
                    except ValueError:
                        continue
            print(f"   [Scheduler] Slots from file: {len(occupied_slots)}")
        except Exception as e:
            print(f"   [Scheduler] Error reading scheduled_videos.json: {e}")

    # 2. Load time slots from hub_settings.json
    daily_times = _load_schedule_times()
    print(f"   [Scheduler] Using {len(daily_times)} daily slots: {[t.strftime('%H:%M') for t in daily_times]}")

    # 3. Find first available slot
    now = datetime.now()
    current_date = now.date()

    for day_offset in range(60):
        target_date = current_date + timedelta(days=day_offset)
        daily_slots = [datetime.combine(target_date, t) for t in daily_times]

        for slot in daily_slots:
            if slot <= now:
                continue
            if slot in occupied_slots:
                continue
            if slot in _session_occupied_slots:
                print(f"   [Scheduler] Skipping session-occupied slot: {slot}")
                continue

            _session_occupied_slots.add(slot)
            time_str = slot.strftime("%I:%M %p").lstrip("0")   # "6:00 PM"
            date_str = slot.strftime("%b %d, %Y")              # "Jan 08, 2026"
            print(f"   [Scheduler] Next Available Slot: {date_str} @ {time_str}")
            return date_str, time_str

    print("Error: Could not find an available slot within 60 days.")
    return None, None