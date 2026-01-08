import json
import os
from datetime import datetime, timedelta, time

def get_next_schedule_time():
    """
    Calculates the next available schedule slot.
    Slots: 12:00 PM, 6:00 PM, 9:00 PM.
    Logic: Starts from MAX(Now, Last_Scheduled_Video).
    """
    json_path = os.path.join("saved_shorts_data", "scheduled_videos.json")
    
    # --- 1. Determine Starting Point ---
    now = datetime.now()
    
    # Default: Start searching from 'Now' if no previous data exists
    # This allows us to catch today's 6pm/9pm slots if we are running at 4pm
    last_scheduled_dt = now

    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            
            timestamps = []
            for video in data:
                if video.get("schedule") and video["schedule"].get("iso"):
                    iso_str = video["schedule"]["iso"]
                    try:
                        clean_iso = iso_str[:19] 
                        dt = datetime.strptime(clean_iso, "%Y-%m-%dT%H:%M:%S")
                        timestamps.append(dt)
                    except ValueError:
                        continue
            
            if timestamps:
                last_from_file = max(timestamps)
                print(f"   [Scheduler] Last scheduled video in file: {last_from_file}")
                
                # If the last video is in the future, we continue from there.
                # If it's in the past (e.g. yesterday), we start from 'Now' to avoid scheduling in the past.
                if last_from_file > now:
                    last_scheduled_dt = last_from_file
                else:
                    print("   [Scheduler] Last video is in the past. Starting fresh from Now.")
                    last_scheduled_dt = now

        except Exception as e:
            print(f"   [Scheduler] Error reading JSON: {e}")

    # --- 2. Find Next Slot ---
    current_check_dt = last_scheduled_dt
    
    # Check next 14 days
    for day_offset in range(14):
        target_date = current_check_dt.date() + timedelta(days=day_offset)
        
        # Define the 3 slots for this target date
        slots = [
            datetime.combine(target_date, time(12, 0)), # 12:00 PM
            datetime.combine(target_date, time(18, 0)), # 6:00 PM
            datetime.combine(target_date, time(21, 0))  # 9:00 PM
        ]
        
        for slot in slots:
            # 1. Must be after the last scheduled video (sequence order)
            # 2. Must be in the future relative to real-world time (validity)
            if slot > current_check_dt and slot > now:
                
                # Formatting
                time_str = slot.strftime("%I:%M %p").lstrip("0") # "6:00 PM"
                date_str = slot.strftime("%b %d, %Y")            # "Jan 08, 2026"
                
                print(f"   [Scheduler] Next Slot Calculated: {date_str} @ {time_str}")
                return date_str, time_str

    print("Error: Could not calculate a slot within 14 days.")
    return None, None