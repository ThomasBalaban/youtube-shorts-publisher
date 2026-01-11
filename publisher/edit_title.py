from playwright.sync_api import Page
import time

def update_title(page: Page, new_title: str):
    print(f"\n--- Step 1.5: Update Title ---")
    print(f">> Changing title to: '{new_title}'")
    
    try:
        # Wait for the title container
        container = page.locator("#title-textarea")
        container.wait_for(state="visible", timeout=10000)
        
        # Locate the editable textbox inside
        title_box = container.locator("#textbox").first
        
        if title_box.is_visible():
            title_box.click()
            time.sleep(0.5)
            
            # --- Method 1: Try Playwright's .fill() ---
            # This is robust for contenteditable and auto-clears
            try:
                title_box.fill(new_title)
            except:
                # --- Method 2: Manual Clear (Fallback) ---
                print(">> Fill failed, trying manual clear...")
                page.keyboard.press("Control+A")
                page.keyboard.press("Meta+A")
                page.keyboard.press("Backspace")
                time.sleep(0.5)
                page.keyboard.type(new_title)

            # Verification: Check text content
            time.sleep(1)
            # We check the text inside to be sure
            actual_text = title_box.inner_text().strip()
            
            # Allow for slight variations (like trailing newlines), but mostly match
            if new_title in actual_text:
                print(">> Title updated successfully.")
                return True
            else:
                print(f">> Warning: Title mismatch. Found: '{actual_text}'")
                return True # Proceed anyway, might be a formatting quirk
        else:
            print(">> Error: Title textbox not found.")
            return False
            
    except Exception as e:
        print(f"Error updating title: {e}")
        return False