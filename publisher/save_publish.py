from playwright.sync_api import Page
import time

def click_save(page: Page):
    print("\n--- Step 8: Save / Schedule ---")
    print(">> Looking for 'Schedule' button (formerly Save)...")

    try:
        # The button ID is usually 'done-button' for both Save and Schedule
        save_btn = page.locator("#done-button")
        
        if save_btn.is_visible():
            print(">> Clicking 'Schedule'...")
            save_btn.click()
            
            # --- HANDLE SUCCESS DIALOG ---
            print(">> Waiting for success dialog...")
            # We wait for the dialog that appears after saving
            # Usually has a header like "Video scheduled"
            try:
                page.wait_for_selector("ytcp-video-share-dialog", state="visible", timeout=15000)
                print(">> Success dialog appeared.")
                
                # Find and click the 'Close' button to return to the list
                # It's typically a ytcp-button with ID 'close-button'
                close_btn = page.locator("ytcp-video-share-dialog #close-button")
                
                if close_btn.is_visible():
                    print(">> Closing success dialog...")
                    close_btn.click()
                    # Wait for dialog to disappear so we can interact with the main page again
                    page.wait_for_selector("ytcp-video-share-dialog", state="hidden", timeout=5000)
                else:
                    print(">> Warning: Close button not found on success dialog.")
                    
            except:
                print(">> Warning: Success dialog did not appear (or timed out).")
            
            return True
        else:
            print(">> Error: 'Schedule' button not found.")
            return False

    except Exception as e:
        print(f"Error clicking 'Schedule': {e}")
        return False