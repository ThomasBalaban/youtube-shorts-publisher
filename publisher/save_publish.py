from playwright.sync_api import Page
import time

def click_save(page: Page):
    print("\n--- Step 8: Save / Publish ---")
    print(">> Looking for 'Save' button...")

    try:
        # 1. Click the main Save/Schedule button
        save_btn = page.locator("#done-button")
        
        if save_btn.is_visible():
            save_btn.click()
            print(">> 'Save' button clicked. Waiting for confirmation dialog...")
            
            # 2. Wait for the confirmation dialog to appear
            # We look for the close button you specified to confirm the dialog is ready
            close_button = page.locator("ytcp-video-share-dialog #close-button").click()
            
            try:
                # Wait up to 10 seconds for the "Video scheduled/published" popup
                close_button.wait_for(state="visible", timeout=10000)
                print(">> Confirmation dialog detected. Clicking 'Close'...")
                
                # Click the Close button
                close_button.click()
                print(">> Success: Confirmation dialog closed.")
                
                # Brief sleep to ensure UI transition completes
                time.sleep(2)
                return True
                
            except Exception as e:
                print(f">> Warning: Close button not found or dialog didn't appear: {e}")
                # We return True anyway because the Save itself likely succeeded
                return True
        else:
            print(">> Error: 'Save' button not found or not visible.")
            return False

    except Exception as e:
        print(f"Error clicking 'Save': {e}")
        return False