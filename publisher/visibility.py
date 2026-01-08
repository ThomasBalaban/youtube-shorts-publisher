from playwright.sync_api import Page
import time
from utils.schedule_manager import get_next_schedule_time

def handle_visibility(page: Page):
    print("\n--- Step 7: Visibility (Scheduling) ---")
    
    # 1. Calculate Time
    target_date, target_time = get_next_schedule_time()
    if not target_date:
        return False

    print(f">> Target: {target_date} @ {target_time}")

    try:
        # 2. Click 'Schedule' Radio
        # This reveals the container with ID 'second-container'
        schedule_radio = page.locator("tp-yt-paper-radio-button[name='SCHEDULE']")
        schedule_radio.scroll_into_view_if_needed()
        time.sleep(1)
        schedule_radio.click()
        
        # Wait for the picker container to appear
        # Selector based on your snippet: .date-timezone-container inside #second-container
        page.wait_for_selector(".date-timezone-container", state="visible", timeout=5000)
        time.sleep(1)

        # 3. Handle DATE
        print(">> Setting Date...")
        # The input is inside ytcp-date-picker -> tp-yt-paper-input -> input
        # We verify visibility of the date-picker component first
        date_picker = page.locator("ytcp-date-picker").first
        date_input = date_picker.locator("input").first
        
        date_input.click()
        time.sleep(0.5)
        date_input.fill(target_date)
        page.keyboard.press("Enter")
        time.sleep(1) # Wait for calendar to close/validate

        # 4. Handle TIME
        print(">> Setting Time...")
        # The time input is inside ytcp-time-of-day-picker -> tp-yt-paper-input -> input
        # Note: The dropdown listbox is separate, but typing usually works if valid.
        
        time_picker = page.locator("ytcp-time-of-day-picker").first
        time_input = time_picker.locator("input").first
        
        time_input.click()
        time.sleep(0.5)
        
        # We type the time (e.g., "6:00 PM")
        time_input.fill(target_time)
        time.sleep(1) # Wait for the dropdown to filter
        
        # CRITICAL: Select from the listbox to ensure format matching
        # YouTube uses a special whitespace (\u202f) in "PM", so exact string match might fail.
        # We look for the visible option in the listbox and click it.
        
        # The listbox appears in a dialog. We search for the option containing our text.
        # We use strict=False to match "6:00 PM" even if the DOM has "6:00 PM"
        time_option = page.locator("tp-yt-paper-item").filter(has_text=target_time).first
        
        if time_option.is_visible():
            print(f"   [UI] Found list option for {target_time}. Clicking...")
            time_option.click()
        else:
            print("   [UI] List option not found. Pressing Enter to confirm typed value.")
            page.keyboard.press("Enter")
            
        time.sleep(1)

        return True

    except Exception as e:
        print(f"Error setting schedule: {e}")
        return False