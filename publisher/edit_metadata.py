from playwright.sync_api import Page
import time

def uncheck_notify_subscribers(page: Page):
    print("\n--- Step 3: Uncheck Notify Subscribers ---")
    print(">> Verifying 'Notify Subscribers' checkbox...")
    
    try:
        # Find the host element by ID
        notify_host = page.locator("#notify-subscribers")
        # Check the 'aria-checked' state on the inner div
        notify_inner = notify_host.locator("#checkbox")
        
        # Ensure it is in view
        notify_host.scroll_into_view_if_needed()
        time.sleep(1)

        # Check current state
        is_checked = notify_inner.get_attribute("aria-checked")
        print(f"   [Debug] Initial State (aria-checked): {is_checked}")

        if is_checked == "true":
            print(">> Checkbox is CHECKED. Clicking to uncheck...")
            notify_host.click()
            time.sleep(2) # Give UI time to update
        else:
            print(">> Checkbox appeared unchecked initially. Verifying...")

        # --- STRICT VERIFICATION ---
        final_state = notify_inner.get_attribute("aria-checked")
        
        if final_state == "true":
            print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("CRITICAL ERROR: 'Notify Subscribers' is STILL CHECKED.")
            print("We cannot proceed safely. Stopping execution.")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            return False
        elif final_state == "false":
            print(">> SUCCESS: 'Notify Subscribers' is confirmed UNCHECKED.")
            return True
        else:
            print(f"ERROR: Unknown checkbox state '{final_state}'. Stopping for safety.")
            return False

    except Exception as e:
        print(f"Error handling 'Notify Subscribers': {e}")
        return False