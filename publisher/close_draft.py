from playwright.sync_api import Page, expect
import time

def close_draft(page: Page):
    print(">> Closing draft dialog...")
    
    # 1. robust selector based on the HTML you provided
    # Targeting the button specifically inside the uploads dialog
    selector = "ytcp-uploads-dialog ytcp-icon-button[aria-label='Save and close']"
    
    try:
        # Wait for the button to be properly in the DOM and visible
        close_btn = page.locator(selector).first
        close_btn.wait_for(state="visible", timeout=5000)
        
        # 2. Hover first to trigger any UI "wake up" (helps with tooltips/overlays)
        close_btn.hover()
        time.sleep(0.5)
        
        # 3. Click with force=False first (standard click), fallback to force if needed
        print(">> Clicking 'Save and close' button...")
        try:
            close_btn.click(timeout=2000)
        except:
            print(">> Standard click failed, trying force click...")
            close_btn.click(force=True)

        # 4. CRITICAL VERIFICATION
        # We wait for the button itself to disappear. 
        # If the button is gone, the dialog is effectively gone/closed.
        print(">> Verifying dialog closure...")
        try:
            close_btn.wait_for(state="hidden", timeout=5000)
            print(">> Success: Draft dialog closed (Button is no longer visible).")
            time.sleep(1) # Safety pause for animations
            return True
        except:
            print(">> ERROR: 'Save and close' button is still visible. Click failed.")
            return False

    except Exception as e:
        print(f"Error handling close button: {e}")
        return False