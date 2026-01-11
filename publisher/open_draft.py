from playwright.sync_api import Page

def open_first_draft(page: Page, analysis_data: list, ignore_titles: list = None):
    print("\n--- Step 1: Open First Draft ---")
    
    if ignore_titles is None:
        ignore_titles = []
        
    # Create a set of titles we actually want to process
    target_titles = {item.get("title") for item in analysis_data if item.get("title")}
    
    print(f"Scanning for {len(target_titles)} target titles (Ignoring {len(ignore_titles)})...")

    # Wait for the video list to load
    try:
        page.wait_for_selector("ytcp-video-row", state="visible", timeout=10000)
    except:
        print("Error: Video rows did not load.")
        return None

    rows = page.locator("ytcp-video-row").all()

    for row in rows:
        try:
            # Check if it's a draft
            if "Draft" in row.inner_text():
                title_link = row.locator("#video-title").first
                
                if title_link.is_visible():
                    video_title = title_link.inner_text().strip()
                    
                    # 1. Skip if previously ignored
                    if video_title in ignore_titles:
                        continue
                        
                    # 2. Skip Backtracks
                    if "Backtrack" in video_title:
                        continue

                    # 3. CRITICAL: Check if this title exists in our analysis JSON
                    if video_title in target_titles:
                        print(f">> Found Match: '{video_title}'")
                        print(">> Opening Draft...")
                        title_link.click()
                        return video_title
                    else:
                        # Log that we saw it but skipped it (optional, keeps logs clean)
                        # print(f"   [Skipping] No analysis data for: '{video_title}'")
                        pass

        except Exception as e:
            continue

    print("No matching drafts found on the current page.")
    return None