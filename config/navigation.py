from playwright.sync_api import Page
from settings import ENABLE_SCRAPING_MODE
import time


def _dismiss_blocking_dialog(page) -> None:
    """Best-effort: close a leftover/stuck upload-edit dialog before we try
    to navigate.

    A draft that fails mid-edit can leave its ``ytcp-uploads-dialog`` open
    (sometimes ``stuck``), and that dialog intercepts pointer events — so the
    very next navigation click times out. We close it here.

    Safety: this only ever *closes/discards* — it never clicks Save/Publish,
    so it cannot publish anything. Discarding a half-edited draft just leaves
    it as a draft (already logged + skipped), which is the desired outcome.
    Never raises.
    """
    try:
        if not page.locator("ytcp-uploads-dialog").first.is_visible(timeout=1000):
            return
    except Exception:
        return

    print("[Nav] A leftover upload/edit dialog is open — closing it first.")

    for selector in (
        "#ytcp-uploads-dialog-close-button",
        "ytcp-uploads-dialog #close-button",
        "ytcp-icon-button[aria-label='Close']",
    ):
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=3000)
                break
        except Exception:
            continue

    # Closing an edited draft can pop a "Discard changes?" confirmation.
    # Discard is the safe choice — abandons the edit (no publish), draft stays.
    for selector in (
        "ytcp-button:has-text('Discard')",
        "tp-yt-paper-button:has-text('Discard')",
        "button:has-text('Discard')",
    ):
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=3000)
                print("[Nav] Discarded the stuck draft's unsaved edits.")
                break
        except Exception:
            continue

    # Final fallback if anything is still up.
    try:
        if page.locator("ytcp-uploads-dialog").first.is_visible(timeout=1000):
            page.keyboard.press("Escape")
    except Exception:
        pass

    page.wait_for_timeout(1000)


def navigate_to_shorts(page):
    print("--- Starting Navigation Sequence ---")

    # Clear any stuck dialog left over from a prior draft before we start
    # clicking, or those clicks get intercepted and time out.
    _dismiss_blocking_dialog(page)

    # --- STEP 1: CLICK CONTENT ---
    print("Looking for 'Content' button...")
    content_clicked = False
    
    # We will try 3 different selectors ranging from specific to general
    selectors = [
        "div.nav-item-text:has-text('Content')",
        "a[href*='/videos/upload']",
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
        print("ERROR: Could not click 'Content' button.")
        return False

    # --- STEP 2: WAIT FOR PAGE CHANGE ---
    try:
        page.wait_for_url("**/videos/**", timeout=10000)
    except:
        print("Warning: URL update slow.")

    # --- STEP 3: CLICK SHORTS ---
    print("Looking for 'Shorts'...")
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
        if ENABLE_SCRAPING_MODE == False:
            page.wait_for_timeout(3000)
            # This is just a focus/defocus nicety — it must never be fatal.
            # A blocked click here (e.g. an overlay intercepting it) used to
            # hang for the full 30s default timeout and crash the whole run.
            try:
                header = page.locator("h1.page-title").first
                header.click(timeout=5000)
            except Exception:
                print("Note: page-title focus click skipped (non-fatal — "
                      "something is overlaying it).")

        print("--- Navigation Complete ---")
        return True
    
    print("ERROR: Could not find 'Shorts' tab.")
    return False