from playwright.sync_api import Page
import time

def update_description(page: Page, description: str, hashtags: list):
    print("\n--- Step 2: Update Description ---")
    
    # 1. Format the text
    # We join the list of tags into a string like "#tag1 #tag2"
    tags_string = " ".join(hashtags) if hashtags else ""
    
    # Create the full block: Description + Double Newline + Tags
    full_text = f"{description}\n\n{tags_string}".strip()
    
    print(f">> Preparing description ({len(full_text)} chars)...")
    
    print(">> Waiting for description box...")
    description_selector = "div#textbox[aria-label*='Tell viewers']"
    
    try:
        page.wait_for_selector(description_selector, state="visible", timeout=15000)
        desc_box = page.locator(description_selector).first
        
        desc_box.click()
        time.sleep(0.5)
        
        print(">> Clearing old description...")
        # robust clear
        page.keyboard.press("Control+A")
        page.keyboard.press("Meta+A") 
        page.keyboard.press("Backspace")
        
        print(">> Typing new description...")
        # Using .fill() is preferred for speed, but .type() is safer for rich text editors
        # if .fill() fails in the future, revert to .type(full_text)
        try:
            desc_box.fill(full_text)
        except:
            print("   [Info] .fill() failed, reverting to keyboard typing...")
            page.keyboard.type(full_text)
        
    except Exception as e:
        print(f"Error handling description: {e}")
        return False

    # --- Click Show More ---
    print(">> Looking for 'Show more' button...")
    try:
        show_more_btn = page.locator("button", has_text="Show more").first
        
        # Scroll to reveal 'Show more'
        show_more_btn.scroll_into_view_if_needed()
        time.sleep(1) 
        
        if show_more_btn.is_visible():
            show_more_btn.click()
            print(">> Clicked 'Show more'.")
        else:
            print(">> 'Show more' button not found (might be already expanded).")
            
    except Exception as e:
        print(f"Error clicking 'Show more': {e}")
        return False
        
    return True