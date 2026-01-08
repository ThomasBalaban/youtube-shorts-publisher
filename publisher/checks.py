from playwright.sync_api import Page
import time

def handle_checks(page: Page):
    print("\n--- Step 6: Checks ---")
    print(">> Waiting for 'Checks' section to load...")

    # 1. Confirm we are on the Checks tab
    try:
        page.wait_for_selector("ytcp-dialog-modal-header", has_text="Checks", timeout=10000)
    except:
        print(">> Warning: 'Checks' header not detected.")

    # 2. Verify "No issues found"
    # The user noted there are typically two checks: Copyright and Ad Suitability.
    # We want to ensure NO issues are present.
    print(">> Verifying check results...")
    
    max_retries = 10 # Wait up to 20 seconds (10 * 2s) if it's still loading
    checks_passed = False

    for i in range(max_retries):
        # We look for the specific success text
        # Using a locator that matches any element containing the text
        issues_found = page.locator("text='No issues found'")
        count = issues_found.count()
        
        if count >= 1:
            print(f">> Success: Found {count} instance(s) of 'No issues found'.")
            checks_passed = True
            break
        
        # Check if it's still processing (optional safeguard)
        if page.locator("text='Checking'").count() > 0:
            print(f"   ... Checks are still running. Waiting ({i+1}/{max_retries})...")
        else:
            print(f"   ... Waiting for checks result ({i+1}/{max_retries})...")
            
        time.sleep(2)

    if not checks_passed:
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("CRITICAL WARNING: Did not find 'No issues found'.")
        print("There might be a copyright claim or the check is stuck.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        # We return False to stop the bot from publishing a video with issues
        return False

    return True