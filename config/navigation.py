def navigate_to_shorts(page):
    print("--- Starting Navigation Sequence ---")
    
    # --- STEP 1: CLICK CONTENT ---
    print("Looking for 'Content' button...")
    content_clicked = False
    
    # We will try 3 different selectors ranging from specific to general
    selectors = [
        # 1. The exact class you found
        "div.nav-item-text:has-text('Content')",
        # 2. The link that goes to the videos page (often the most robust)
        "a[href*='/videos/upload']",
        # 3. Just the text 'Content' anywhere (fallback)
        "text='Content'"
    ]

    for i in range(30):
        # First, try to hover the sidebar to expand it if it's collapsed
        try:
            page.locator("ytcp-navigation-drawer").hover(timeout=500)
        except:
            pass

        # Iterate through our list of potential selectors
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    # force=True skips the "is this actionable" check
                    btn.click(force=True)
                    print(f">> Success: Clicked Content using selector: {selector}")
                    content_clicked = True
                    break
            except Exception:
                continue
        
        if content_clicked:
            break
            
        print(f"Waiting for Content button... ({i+1}/30)")
        page.wait_for_timeout(1000)

    if not content_clicked:
        print("ERROR: Could not click 'Content' button. Dumping page text for debug:")
        # This will print what Playwright actually sees on the left side
        try:
            print(page.locator("ytcp-navigation-drawer").inner_text())
        except:
            print("Could not read sidebar text.")
        return False

    # --- STEP 2: WAIT FOR PAGE CHANGE ---
    try:
        page.wait_for_url("**/videos/**", timeout=10000)
    except:
        print("Warning: URL update slow.")

    # --- STEP 3: CLICK SHORTS ---
    print("Looking for 'Shorts' filter...")
    shorts_clicked = False
    
    for i in range(15):
        try:
            # Try to click the specific custom element
            shorts_filter = page.locator("ytcp-ve", has_text="Shorts")
            if shorts_filter.is_visible():
                shorts_filter.click(force=True)
                print(">> Success: Clicked 'Shorts'.")
                shorts_clicked = True
                break
        except Exception:
            pass
        page.wait_for_timeout(1000)

    if shorts_clicked:
        print("--- Navigation Complete ---")
        return True
    
    print("ERROR: Could not find 'Shorts' tab.")
    return False