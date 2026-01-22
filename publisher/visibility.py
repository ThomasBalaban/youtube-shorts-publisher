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
        # Parse the calculated target date
        target_dt = datetime.strptime(target_date_str, "%b %d, %Y")
        
        # Determine strict formats for the UI matching
        # "%B" = Full Month (e.g., "January"), "%b" = Abbr (e.g., "Jan")
        target_month_full = target_dt.strftime("%B %Y") 
        target_month_abbr = target_dt.strftime("%b %Y")
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
        datepicker_trigger = page.locator(".date-timezone-container #datepicker-trigger").first
        time_container_trigger = page.locator("#time-of-day-container").first
        
        datepicker_trigger.wait_for(state="visible", timeout=10000)
        time.sleep(1) 

        # 3. Open Calendar
        print(">> Opening Calendar...")
        datepicker_trigger.click()
        
        calendar_dialog = page.locator("ytcp-date-picker tp-yt-paper-dialog")
        calendar_dialog.wait_for(state="visible", timeout=5000)
        time.sleep(0.5)

        # 4. Navigate Month
        print(f">> Navigating to month: {target_month_full}...")
        
        # Use the ID 'next-month' as requested
        next_month_btn = page.locator("ytcp-date-picker #next-month")
        
        month_found = False
        # Loop up to 24 times (2 years) to find the month
        for _ in range(24):
            # Check for Full Month (e.g. "January 2026") OR Abbreviated (e.g. "Jan 2026")
            if page.locator(f".calendar-month:has-text('{target_month_full}')").is_visible():
                print(f"   [UI] Found month: {target_month_full}")
                month_found = True
                break
            elif page.locator(f".calendar-month:has-text('{target_month_abbr}')").is_visible():
                print(f"   [UI] Found month: {target_month_abbr}")
                month_found = True
                break
            else:
                if next_month_btn.is_visible():
                    # Click the next month button
                    next_month_btn.click()
                    time.sleep(0.2)
                else:
                    break
        
        if not month_found:
            print(f"Error: Could not find month '{target_month_full}'")
            return False

        # 5. Select Day
        print(f">> Selecting day: {target_day}...")
        # Re-locate the container for the found month (using whichever format worked or defaulting to full)
        month_container = page.locator(f".calendar-month:has-text('{target_month_full}')")
        if not month_container.is_visible():
             month_container = page.locator(f".calendar-month:has-text('{target_month_abbr}')")
        
        day_pattern = re.compile(rf"^\s*{target_day}\s*$")
        day_cell = month_container.locator(".calendar-day").filter(has_text=day_pattern).first
        
        if day_cell.is_visible():
            day_cell.click()
            print("   [UI] Date clicked.")
            time.sleep(1) 
        else:
            print(f"Error: Day '{target_day}' not found.")
            return False

        # 6. Handle TIME
        print(">> Opening Time Picker...")
        time_container_trigger.click()
        
        time_dialog = page.locator("ytcp-time-of-day-picker tp-yt-paper-dialog")
        time_dialog.wait_for(state="visible", timeout=5000)
        time.sleep(0.5)
        
        print(f">> Selecting time: {target_time_str}...")
        time_option = page.locator("ytcp-time-of-day-picker tp-yt-paper-item").filter(has_text=target_time_str).first
        
        if time_option.is_visible():
             time_option.scroll_into_view_if_needed()
             time_option.click()
             print("   [UI] Time clicked.")
        else:
            print("   [Warning] Time option not found in list. Attempting to type...")
            input_box = time_container_trigger.locator("input").first
            input_box.click()
            input_box.fill(target_time_str)
            page.keyboard.press("Enter")
            
        time.sleep(1)
        return True

    except Exception as e:
        print(f"Error setting schedule: {e}")
        return False