from playwright.sync_api import Page

def process_single_draft(page: Page):
    print("\n--- Single Video Mode ---")
    print("Looking for the first available 'Draft'...")

    # Wait for the video list to load
    try:
        page.wait_for_selector("ytcp-video-row", state="visible", timeout=10000)
    except:
        print("Error: Video rows did not load.")
        return

    rows = page.locator("ytcp-video-row").all()

    for row in rows:
        try:
            # Check if this row is a Draft
            # We look for the text "Draft" in the visibility column
            if "Draft" in row.inner_text():
                print("-> Found a draft candidate.")
                
                # Locate the title link using the specific ID you found
                # Selector: #video-title inside the row
                title_link = row.locator("#video-title").first
                
                if title_link.is_visible():
                    video_title = title_link.inner_text().strip()
                    print(f">> CLICKING Draft: '{video_title}'")
                    
                    # Perform the click
                    title_link.click()
                    
                    print(">> Click successful. Pausing execution for manual inspection.")
                    return True
        except Exception as e:
            print(f"Error checking row: {e}")
            continue

    print("No drafts found on the first page.")
    return False