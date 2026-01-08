import json
import os
from datetime import datetime, timedelta, time

def get_next_schedule_time():
    """
    Calculates the next available schedule slot based on saved data.
    Slots: 12:00 PM, 6:00 PM, 9:00 PM.
    """
    json_path = os.path.join("saved_shorts_data", "scheduled_videos.json")
    
    # --- 1. Determine Starting Point ---
    # Default: Start checking from "Tomorrow" at 9 AM (so the first slot found is Tomorrow 12 PM)
    now = datetime.now()
    start_date = now + timedelta(days=1)
    last_scheduled_dt = datetime.combine(start_date.date(), time(9, 0))

    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            
            timestamps = []
            for video in data:
                # We look for the 'iso' timestamp in the schedule object
                if video.get("schedule") and video["schedule"].get("iso"):
                    iso_str = video["schedule"]["iso"]
                    # Parse ISO string to datetime object (ignoring timezone for simple comparison)
                    # ISO Format example: "2026-01-30T15:15:00-05:00"
                    try:
                        # Taking first 19 chars gets 'YYYY-MM-DDTHH:MM:SS' which is safe for naive datetime
                        clean_iso = iso_str[:19] 
                        dt = datetime.strptime(clean_iso, "%Y-%m-%dT%H:%M:%S")
                        timestamps.append(dt)
                    except ValueError:
                        continue
            
            if timestamps:
                last_scheduled_dt = max(timestamps)
                print(f"   [Scheduler] Last scheduled video found in file: {last_scheduled_dt}")
            else:
                print("   [Scheduler] No valid timestamps in JSON. Using default start.")

        except Exception as e:
            print(f"   [Scheduler] Error reading JSON: {e}")

    # --- 2. Find Next Slot ---
    # We check slots sequentially starting after the last_scheduled_dt
    current_check_dt = last_scheduled_dt
    
    # Look ahead up to 14 days to find a slot (safe buffer)
    for day_offset in range(14):
        # We check the date of (Start Time + offset)
        # Note: If day_offset is 0, we are checking the rest of the current 'last scheduled' day
        target_date = current_check_dt.date() + timedelta(days=day_offset)
        
        # Define the 3 slots for this target date
        slots = [
            datetime.combine(target_date, time(12, 0)), # 12:00 PM
            datetime.combine(target_date, time(18, 0)), # 6:00 PM
            datetime.combine(target_date, time(21, 0))  # 9:00 PM
        ]
        
        for slot in slots:
            if slot > current_check_dt:
                # Found our winner
                # Return strings formatted for YouTube input
                # Date: "Jan 30, 2026"
                # Time: "12:00 PM" or "6:00 PM"
                
                # Removing leading zero from hour for cleaner typing (06:00 PM -> 6:00 PM)
                time_str = slot.strftime("%I:%M %p").lstrip("0") 
                date_str = slot.strftime("%b %d, %Y")
                
                print(f"   [Scheduler] Next Slot Calculated: {date_str} @ {time_str}")
                return date_str, time_str

    print("Error: Could not calculate a slot within 14 days.")
    return None, None