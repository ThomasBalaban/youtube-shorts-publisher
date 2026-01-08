from playwright.sync_api import Page
import time

def click_next(page: Page):
    print(">> Clicking 'Next' button...")
    try:
        # Using the specific aria-label 'Next'
        # .last ensures we grab the active button at the bottom right, not hidden ones
        next_btn = page.locator("button[aria-label='Next']").last
        
        if next_btn.is_visible():
            next_btn.click()
            # A short sleep is crucial here to allow the wizard to animate to the new tab
            time.sleep(2) 
            return True
        else:
            print(">> Error: 'Next' button not found or not visible.")
            return False
    except Exception as e:
        print(f"Error clicking 'Next': {e}")
        return False