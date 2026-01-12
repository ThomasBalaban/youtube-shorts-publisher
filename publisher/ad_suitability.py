from playwright.sync_api import Page
import time

def is_ad_suitability_completed(page: Page):
    """
    Checks the stepper at the top of the dialog to see if Ad Suitability
    is already marked as 'completed'.
    MUST BE RUN BEFORE NAVIGATING TO THE AD SUITABILITY TAB.
    """
    print(">> Checking Ad Suitability status (via Stepper)...")
    try:
        # Selector based on the test-id and state provided
        # We look for the button specifically with state="completed"
        stepper_btn = page.locator('button[test-id="CONTENT_RATINGS"][state="completed"]')
        
        if stepper_btn.is_visible():
            print(">> [Status] Ad Suitability is ALREADY COMPLETED.")
            return True
        else:
            print(">> [Status] Ad Suitability is NOT complete.")
            return False
            
    except Exception as e:
        print(f"Warning: Could not check stepper status: {e}")
        return False

def complete_ad_suitability(page: Page):
    """
    Fills out the Ad Suitability form (None of the above -> Submit).
    """
    print("\n--- Step 4: Ad Suitability (Filling Form) ---")
    
    # --- PART 1: CHECK 'NONE OF THE ABOVE' ---
    print(">> Looking for 'None of the above' checkbox...")
    
    try:
        checkbox_selector = "ytcp-checkbox-lit[label='None of the above']"
        
        # Wait for form
        try:
            page.wait_for_selector(checkbox_selector, state="visible", timeout=10000)
        except:
            print(">> Error: 'None of the above' checkbox did not appear.")
            return False
        
        checkbox_host = page.locator(checkbox_selector).first
        checkbox_host.scroll_into_view_if_needed()
        time.sleep(1)
        
        # Check inner state
        checkbox_inner = checkbox_host.locator("#checkbox")
        if checkbox_inner.get_attribute("aria-checked") == "false":
            print(">> Checkbox is unchecked. Clicking it now...")
            checkbox_host.click()
            time.sleep(1)
        else:
            print(">> 'None of the above' was already checked.")

        # Verification
        if checkbox_inner.get_attribute("aria-checked") != "true":
            print(">> Error: Failed to check 'None of the above'.")
            return False
            
    except Exception as e:
        print(f"Error handling Ad Suitability checkbox: {e}")
        return False

    # --- PART 2: SUBMIT RATING ---
    print(">> Looking for 'Submit rating' button...")
    try:
        submit_btn = page.locator("#submit-questionnaire-button")
        
        # Check if button exists
        if submit_btn.is_visible():
            
            # --- FIX: Check if disabled first ---
            # If the rating is already submitted, the button is present but disabled.
            # Playwright's click() waits for it to be enabled, causing the timeout.
            is_disabled = submit_btn.is_disabled() or submit_btn.get_attribute("aria-disabled") == "true"
            
            if is_disabled:
                print(">> [Info] 'Submit rating' button is DISABLED (Rating likely already submitted).")
                print(">> Proceeding as success.")
                return True

            # If enabled, click it
            submit_btn.click()
            print(">> Clicked 'Submit rating'.")
            time.sleep(3) # Wait for processing
            return True
        else:
            print(">> Warning: 'Submit rating' button not visible.")
            return True # Proceed anyway
            
    except Exception as e:
        print(f"Error clicking 'Submit rating': {e}")
        return False