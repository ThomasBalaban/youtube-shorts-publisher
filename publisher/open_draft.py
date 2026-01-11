from playwright.sync_api import Page

def open_first_draft(page: Page, ignore_titles: list = None):
    print("\n--- Step 1: Open First Draft ---")
    
    if ignore_titles is None:
        ignore_titles = []
        
    print(f"Looking for 'Draft' (Ignoring {len(ignore_titles)} skipped titles)...")

    # Wait for the video list to load
    try:
        page.wait_for_selector("ytcp-video-row", state="visible", timeout=10000)
    except:
        print("Error: Video rows did not load.")
        return None

    rows = page.locator("ytcp-video-row").all()

    for row in rows:
        try:
            if "Draft" in row.inner_text():
                title_link = row.locator("#video-title").first
                
                if title_link.is_visible():
                    video_title = title_link.inner_text().strip()
                    
                    # --- CHECK IGNORE LIST ---
                    if video_title in ignore_titles:
                        continue
                    # -------------------------

                    # --- FILTER BACKTRACK ---
                    if "Backtrack" in video_title:
                        # We implicitly ignore Backtracks always
                        continue
                    
                    print(f">> Opening Draft: '{video_title}'")
                    title_link.click()
                    return video_title
        except Exception as e:
            continue

    print("No suitable drafts found on the current page.")
    return None