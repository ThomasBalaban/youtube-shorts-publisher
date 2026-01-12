from playwright.sync_api import Page
import time

def open_first_draft(page: Page, analysis_data: list, ignore_titles: list = None):
    print("\n--- Step 1: Open First Draft ---")
    
    if ignore_titles is None:
        ignore_titles = []
        
    # --- BUILD LOOKUP MAP ---
    # Maps { Visible Title -> Original Title Key }
    title_map = {}
    for item in analysis_data:
        original_title = item.get("title")
        if original_title:
            title_map[original_title] = original_title
            
            new_title = item.get("new_title")
            if new_title:
                title_map[new_title] = original_title
    
    print(f"Scanning for {len(title_map)} potential title matches (Ignoring {len(ignore_titles)})...")

    page_count = 1

    # --- PAGINATION LOOP ---
    while True:
        print(f">> Scanning Page {page_count}...")

        # Wait for rows to load
        try:
            page.wait_for_selector("ytcp-video-row", state="visible", timeout=5000)
        except:
            print("   [Info] No video rows detected on this page.")

        # Get all rows on current page
        rows = page.locator("ytcp-video-row").all()

        # --- ROW SCANNING ---
        for row in rows:
            try:
                # Check if it's a draft
                # (We check text content safely to avoid stale element errors)
                row_text = row.inner_text()
                if "Draft" in row_text:
                    title_link = row.locator("#video-title").first
                    
                    if title_link.is_visible():
                        visible_title = title_link.inner_text().strip()
                        
                        # 1. Filter Backtracks
                        if "Backtrack" in visible_title:
                            continue

                        # 2. Check for Match in our Map
                        if visible_title in title_map:
                            original_key = title_map[visible_title]
                            
                            # 3. Check Ignore List
                            if original_key in ignore_titles:
                                continue

                            print(f">> Found Match: '{visible_title}'")
                            if visible_title != original_key:
                                 print(f"   (Mapped to original analysis key: '{original_key}')")
                                 
                            print(">> Opening Draft...")
                            title_link.click()
                            
                            return original_key

            except Exception as e:
                # Stale element or UI update during scan
                continue
        
        # --- PAGINATION LOGIC (Re-used from scraper) ---
        print(f"   [Info] No match found on Page {page_count}.")
        
        # Look for the 'Next Page' button
        next_button = page.locator("#navigate-after")
        
        # Check if button exists and is actionable (not disabled)
        if not next_button.is_visible() or next_button.get_attribute("aria-disabled") == "true":
            print(">> End of list reached. No matching drafts found.")
            break
        
        print(">> Navigating to next page...")
        next_button.click()
        
        # Wait for the table to refresh
        time.sleep(3)
        page_count += 1

    return None