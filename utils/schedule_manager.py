import json
import os
from datetime import datetime, timedelta, time

def get_next_schedule_time():
    """
    Calculates the next available schedule slot (12:00 PM, 6:00 PM, 9:00 PM).
    Logic: 
    1. Scan all existing scheduled videos to find occupied slots.
    2. Start from NOW and find the first future slot that is NOT occupied.
    """
    json_path = os.path.join("saved_shorts_data", "scheduled_videos.json")
    occupied_slots = set()
    
    # --- 1. Load Occupied Slots ---
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            
            for video in data:
                if video.get("schedule") and video["schedule"].get("iso"):
                    iso_str = video["schedule"]["iso"]
                    try:
                        # Parse ISO string (e.g., 2026-01-08T18:00:00-05:00)
                        # We only care about the matching datetime, so we strip timezone for easy comparison
                        # (Assuming the bot runs in the same timezone as the intended schedule)
                        dt = datetime.fromisoformat(iso_str).replace(tzinfo=None)
                        occupied_slots.add(dt)
                    except ValueError:
                        continue
            
            print(f"   [Scheduler] Found {len(occupied_slots)} occupied slots from file.")
        except Exception as e:
            print(f"   [Scheduler] Error reading JSON: {e}")

    # --- 2. Find First Available Slot ---
    now = datetime.now()
    current_check_date = now.date()
    
    # Check the next 30 days for a slot
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

            # Rule 2: Slot must not be in the occupied list
            # We check if the exact slot exists in our set
            if slot in occupied_slots:
                print(f"   [Scheduler] Skipping occupied slot: {slot}")
                continue
            
            # If we pass both rules, this is our winner
            time_str = slot.strftime("%I:%M %p").lstrip("0") # "6:00 PM"
            date_str = slot.strftime("%b %d, %Y")            # "Jan 08, 2026"
            
            print(f"   [Scheduler] Next Available Slot: {date_str} @ {time_str}")
            return date_str, time_str

    print("Error: Could not calculate a slot within 30 days.")
    return None, None