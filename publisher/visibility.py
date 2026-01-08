from playwright.sync_api import Page
import time

def handle_visibility(page: Page):
    print("\n--- Step 7: Visibility ---")
    print(">> Waiting for Visibility options...")

    # --- TODO: SCHEDULING FUNCTIONALITY ---
    # As requested, this is the placeholder for future scheduling logic.
    print(">> [TODO] Work on scheduling functionality.")

    try:
        # Selector based on the specific 'name' attribute in your snippet
        unlisted_radio = page.locator('tp-yt-paper-radio-button[name="UNLISTED"]')
        
        # Wait for the element to load
        unlisted_radio.wait_for(state="visible", timeout=10000)
        
        # Check if it is already selected
        is_checked = unlisted_radio.get_attribute("aria-checked")
        
        if is_checked == "true":
            print(">> 'Unlisted' is already selected.")
        else:
            print(">> Selecting 'Unlisted'...")
            unlisted_radio.click()
            time.sleep(0.5) # Allow UI update
            
            # Verify selection
            if unlisted_radio.get_attribute("aria-checked") == "true":
                print(">> Success: 'Unlisted' selected.")
            else:
                print(">> Error: Failed to select 'Unlisted'.")
                return False
                
        return True

    except Exception as e:
        print(f"Error setting visibility: {e}")
        return False