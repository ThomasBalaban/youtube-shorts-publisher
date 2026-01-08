from playwright.sync_api import Page
import time
import re
from datetime import datetime
from utils.schedule_manager import get_next_schedule_time

def handle_visibility(page: Page):
    print("\n--- Step 7: Visibility (Scheduling) ---")
    
    # 1. Calculate Time
    target_date_str, target_time_str = get_next_schedule_time()
    if not target_date_str:
        return False

    print(f">> Target: {target_date_str} @ {target_time_str}")

    try:
        target_dt = datetime.strptime(target_date_str, "%b %d, %Y")
        target_month_year = target_dt.strftime("%b %Y") 
        target_day = str(target_dt.day)                 
    except ValueError as e:
        print(f"Error parsing target date: {e}")
        return False

    try:
        # 2. Click 'Schedule' Container
        print(">> Clicking 'Schedule' container...")
        schedule_container = page.locator("#second-container")
        schedule_container.scroll_into_view_if_needed()
        time.sleep(1)
        schedule_container.click()
        
        print(">> Waiting for visibility options...")
        page.wait_for_selector("ytcp-video-visibility-select", state="visible", timeout=10000)
        
        # Scoped locator for the triggers
        # We define them here to ensure the section is loaded
        datepicker_trigger = page.locator(".date-timezone-container #datepicker-trigger").first
        
        # --- NEW: Time Container Selector ---
        # Using the specific ID you found
        time_container_trigger = page.locator("#time-of-day-container").first
        
        datepicker_trigger.wait_for(state="visible", timeout=10000)
        time.sleep(1) 

        # 3. Open Calendar (Date Logic - CONFIRMED WORKING)
        print(">> Opening Calendar...")
        datepicker_trigger.click()
        
        calendar_dialog = page.locator("ytcp-date-picker tp-yt-paper-dialog")
        calendar_dialog.wait_for(state="visible", timeout=5000)
        time.sleep(0.5)

        # 4. Navigate Month
        print(f">> Navigating to month: {target_month_year}...")
        next_month_btn = page.locator("ytcp-date-picker #next-month")
        
        month_found = False
        for _ in range(24):
            month_container = page.locator(f".calendar-month:has-text('{target_month_year}')")
            if month_container.is_visible():
                print(f"   [UI] Found month: {target_month_year}")
                month_found = True
                break
            else:
                if next_month_btn.is_visible():
                    next_month_btn.click()
                    time.sleep(0.2)
                else:
                    break
        
        if not month_found:
            print(f"Error: Could not find month '{target_month_year}'")
            return False

        # 5. Select Day
        print(f">> Selecting day: {target_day}...")
        month_container = page.locator(f".calendar-month:has-text('{target_month_year}')")
        day_pattern = re.compile(rf"^\s*{target_day}\s*$")
        day_cell = month_container.locator(".calendar-day").filter(has_text=day_pattern).first
        
        if day_cell.is_visible():
            day_cell.click()
            print("   [UI] Date clicked.")
            time.sleep(1) 
        else:
            print(f"Error: Day '{target_day}' not found.")
            return False

        # 6. Handle TIME (Updated Logic)
        print(">> Opening Time Picker...")
        
        # Click the container to open the listbox
        time_container_trigger.click()
        
        # Wait for the specific time picker dialog
        time_dialog = page.locator("ytcp-time-of-day-picker tp-yt-paper-dialog")
        time_dialog.wait_for(state="visible", timeout=5000)
        time.sleep(0.5)
        
        # Select the time from the list
        # target_time_str is like "6:00 PM"
        # The list items might have "6:00\u202fPM". Playwright's has_text usually matches nicely.
        print(f">> Selecting time: {target_time_str}...")
        
        # We scope to the active time picker's listbox
        time_option = page.locator("ytcp-time-of-day-picker tp-yt-paper-item").filter(has_text=target_time_str).first
        
        # Scroll to it just in case (the list is long)
        if time_option.is_visible():
             time_option.scroll_into_view_if_needed()
             time_option.click()
             print("   [UI] Time clicked.")
        else:
            # Fallback: if scroll didn't work or text mismatch, try typing into the input inside that container
            print("   [Warning] Time option not found in list. Attempting to type...")
            # Close the dialog by clicking the trigger again or outside? 
            # Actually, the input inside #time-of-day-container is usually editable.
            
            input_box = time_container_trigger.locator("input").first
            input_box.click()
            input_box.fill(target_time_str)
            page.keyboard.press("Enter")
            
        time.sleep(1)

        return True

    except Exception as e:
        print(f"Error setting schedule: {e}")
        return False