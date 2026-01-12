from playwright.sync_api import Page
import time

def update_tags(page: Page, tags: str):
    print("\n--- Step 2.5: Update Tags ---")
    
    if not tags:
        print(">> No tags provided in analysis. Skipping.")
        return True
        
    print(f">> Processing tags ({len(tags)} chars)...")
    
    # Selectors
    tags_container_selector = "#tags-container"
    tags_input_selector = "#tags-container #text-input"
    clear_button_selector = "#tags-container #clear-button"
    
    try:
        # 1. Wait for the general container to ensure section is loaded
        page.wait_for_selector(tags_container_selector, state="visible", timeout=10000)
        
        # 2. Scroll to the input to ensure buttons are in view/interactive
        tag_box = page.locator(tags_input_selector).first
        tag_box.scroll_into_view_if_needed()
        time.sleep(0.5)

        # --- NEW: Clear Existing Tags ---
        # We check if the 'Clear' button is visible. 
        # YouTube usually hides this button if there are no tags.
        clear_btn = page.locator(clear_button_selector).first
        
        if clear_btn.is_visible():
            print(">> Existing tags detected. Clicking 'Clear' button...")
            clear_btn.click()
            time.sleep(1) # Wait for tags to disappear
        else:
            print(">> No existing tags to clear.")

        # 3. Click to focus the input box
        tag_box.click()
        
        # 4. Fill the comma-separated string
        print(f">> Filling new tags: {tags[:50]}...")
        tag_box.fill(tags)
        time.sleep(1)
        
        # 5. Press Enter to confirm the last tag (crucial for the final chip to form)
        page.keyboard.press("Enter")
        
        print(">> Tags added successfully.")
        return True
        
    except Exception as e:
        print(f"Error handling tags: {e}")
        # Return True so the bot doesn't crash on a minor metadata error
        return True