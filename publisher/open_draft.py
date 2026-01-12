from playwright.sync_api import Page

def open_first_draft(page: Page, analysis_data: list, ignore_titles: list = None):
    print("\n--- Step 1: Open First Draft ---")
    
    if ignore_titles is None:
        ignore_titles = []
        
    # --- BUILD LOOKUP MAP ---
    # Maps { Visible Title -> Original Title Key }
    # This allows us to find a match even if the video has already been renamed to 'new_title'
    title_map = {}
    for item in analysis_data:
        original_title = item.get("title")
        if original_title:
            # Map the original title to itself (Primary Match)
            title_map[original_title] = original_title
            
            # Map the new_title to the original title (Secondary Match)
            # This handles cases where the bot updated the title but crashed/stopped before publishing
            new_title = item.get("new_title")
            if new_title:
                title_map[new_title] = original_title
    
    print(f"Scanning for {len(title_map)} potential title matches (Ignoring {len(ignore_titles)})...")

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
                    visible_title = title_link.inner_text().strip()
                    
                    # 1. Filter Backtracks
                    if "Backtrack" in visible_title:
                        continue

                    # 2. Check for Match in our Map
                    if visible_title in title_map:
                        original_key = title_map[visible_title]
                        
                        # 3. Check Ignore List (We check the ID/Original Key)
                        if original_key in ignore_titles:
                            continue

                        print(f">> Found Match: '{visible_title}'")
                        if visible_title != original_key:
                             print(f"   (Mapped to original analysis key: '{original_key}')")
                             
                        print(">> Opening Draft...")
                        title_link.click()
                        
                        # CRITICAL: We return the ORIGINAL key.
                        # This ensures the main script can look up the correct JSON data 
                        # even if the visible title on YouTube is already the "new" one.
                        return original_key

        except Exception as e:
            continue

    print("No matching drafts found on the current page.")
    return None