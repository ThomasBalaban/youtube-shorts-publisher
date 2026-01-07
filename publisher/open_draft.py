from playwright.sync_api import Page

def open_first_draft(page: Page):
    print("\n--- Step 1: Open First Draft ---")
    print("Looking for the first available 'Draft'...")

    # Wait for the video list to load
    try:
        page.wait_for_selector("ytcp-video-row", state="visible", timeout=10000)
    except:
        print("Error: Video rows did not load.")
        return False

    rows = page.locator("ytcp-video-row").all()

    for row in rows:
        try:
            if "Draft" in row.inner_text():
                title_link = row.locator("#video-title").first
                
                if title_link.is_visible():
                    video_title = title_link.inner_text().strip()
                    print(f">> Opening Draft: '{video_title}'")
                    title_link.click()
                    return True
        except Exception as e:
            continue

    print("No drafts found on the first page.")
    return False