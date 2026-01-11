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
        # You identified it has id="textbox" inside the title-textarea component
        title_box = container.locator("#textbox").first
        
        if title_box.is_visible():
            title_box.click()
            time.sleep(0.5)
            
            # Select All + Backspace to clear current title
            # Using Meta+A (Mac) and Control+A (Windows) sequence to be safe, 
            # or just the one you used before. Sticking to Meta+A as per your previous files.
            page.keyboard.press("Meta+A")
            page.keyboard.press("Control+A") # Safety measure for different OS
            page.keyboard.press("Backspace")
            
            # Type the new title
            page.keyboard.type(new_title)
            time.sleep(1)
            print(">> Title updated successfully.")
            return True
        else:
            print(">> Error: Title textbox not found.")
            return False
            
    except Exception as e:
        print(f"Error updating title: {e}")
        return False