import json
import os
from datetime import datetime, timedelta, time

# --- NEW: Session Memory ---
# This set will store slots we have assigned during this specific run of the script.
# This prevents the bot from picking the same time twice in one batch.
_session_occupied_slots = set()

def get_next_schedule_time():
    """
    Calculates the next available schedule slot (12:00 PM, 6:00 PM, 9:00 PM).
    Logic: 
    1. Scan existing scheduled videos from JSON (File Memory).
    2. Combine with slots assigned during this run (Session Memory).
    3. Start from NOW and find the first future slot that is NOT occupied.
    4. Reserve that slot in Session Memory and return it.
    """
    json_path = os.path.join("saved_shorts_data", "scheduled_videos.json")
    occupied_slots = set()
    
    # --- 1. Load Occupied Slots from File ---
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            
            for video in data:
                if video.get("schedule") and video["schedule"].get("iso"):
                    iso_str = video["schedule"]["iso"]
                    try:
                        # Parse ISO string and remove timezone for comparison
                        dt = datetime.fromisoformat(iso_str).replace(tzinfo=None)
                        occupied_slots.add(dt)
                    except ValueError:
                        continue
            
            print(f"   [Scheduler] Slots from file: {len(occupied_slots)}")
        except Exception as e:
            print(f"   [Scheduler] Error reading JSON: {e}")

    # --- 2. Find First Available Slot ---
    now = datetime.now()
    current_check_date = now.date()
    
    # Check the next 30 days
    for day_offset in range(30):
        target_date = current_check_date + timedelta(days=day_offset)
        
        # Define the 3 fixed slots for this target date
        daily_slots = [
            datetime.combine(target_date, time(12, 0)), # 12:00 PM
            datetime.combine(target_date, time(18, 0)), # 6:00 PM
            datetime.combine(target_date, time(21, 0))  # 9:00 PM
        ]
        
        for slot in daily_slots:
            # Rule 1: Slot must be in the future relative to 'now'
            if slot <= now:
                continue

            # Rule 2: Slot must not be in the JSON file
            if slot in occupied_slots:
                # print(f"   [Scheduler] Skipping file-occupied slot: {slot}") # Optional debug
                continue

            # Rule 3: Slot must not have been used in THIS session
            if slot in _session_occupied_slots:
                print(f"   [Scheduler] Skipping session-occupied slot: {slot}")
                continue
            
            # If we pass all rules, this is our winner
            
            # --- IMPORTANT: Lock this slot for the next iteration ---
            _session_occupied_slots.add(slot)
            
            time_str = slot.strftime("%I:%M %p").lstrip("0") # "6:00 PM"
            date_str = slot.strftime("%b %d, %Y")            # "Jan 08, 2026"
            
            print(f"   [Scheduler] Next Available Slot: {date_str} @ {time_str}")
            return date_str, time_str

    print("Error: Could not calculate a slot within 30 days.")
    return None, None