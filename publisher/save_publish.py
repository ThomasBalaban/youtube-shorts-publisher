from playwright.sync_api import Page
import time
from settings import TEST_MODE

def click_save(page: Page):
    print("\n--- Step 8: Save / Publish ---")
    
    # --- TEST MODE CHECK ---
    if TEST_MODE:
        print("\n**************************************************")
        print(">> TEST MODE ENABLED: Skipping 'Save' button click.")
        print(">> The video will remain a draft so you can verify changes.")
        print("**************************************************\n")
        return True
    # ---------------------------

    print(">> Looking for 'Save' button...")

    try:
        # 1. Click the main Save/Schedule button FIRST
        save_btn = page.locator("#done-button")
        
        if save_btn.is_visible():
            save_btn.click()
            print(">> 'Save' button clicked. Checking for subsequent dialogs...")
            # No sleep here needed, we will wait dynamically in the next block
        else:
            print(">> Error: 'Save' button (#done-button) not found or not visible.")
            return False

        # 2. Check for "Issue found" / Copyright Warning Popup
        print(">> Looking for warning dialog...")
        
        # Define the locators based on your HTML
        # Parent component: <ytcp-prechecks-warning-dialog>
        warning_dialog = page.locator("ytcp-prechecks-warning-dialog")
        
        # Specific title text: <h1 id="dialog-title">Issue found</h1>
        warning_title = warning_dialog.locator("#dialog-title").filter(has_text="Issue found")
        
        try:
            # We wait up to 5 seconds for the "Issue found" text to appear
            # This handles the animation delay after clicking Save
            warning_title.wait_for(state="visible", timeout=5000)
            
            print(">> [Info] 'Issue found' warning detected.")
            
            # Target the 'Publish' button inside the warning dialog
            publish_btn = warning_dialog.locator("button[aria-label='Publish']")
            
            if publish_btn.is_visible():
                print(">> Clicking 'Publish' button inside warning dialog...")
                publish_btn.click()
                time.sleep(3) # Wait for dialog to close/transition
            else:
                 print(">> [Warning] Warning dialog found, but 'Publish' button not visible.")
                 
        except:
            # If the timeout hits (element not found), we assume everything is fine
            print(">> No problems found (warning dialog not detected).")

        # 3. Wait for the final Success/Share dialog
        close_button = page.locator("ytcp-video-share-dialog #close-button")
        
        try:
            print(">> Waiting for final success dialog...")
            # Wait up to 10 seconds for the success popup
            close_button.wait_for(state="visible", timeout=10000)
            
            # Click the Close button
            close_button.click()
            print(">> Success: Final confirmation dialog closed.")
            
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f">> Warning: Final 'Close' button not found or dialog didn't appear: {e}")
            return True

    except Exception as e:
        print(f"Error during Save flow: {e}")
        return False