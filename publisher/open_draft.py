"""Scan YT Studio's draft list, open the first row whose title is in
``allowed_titles`` (and isn't in ``ignore_titles``). Returns the visible
draft title that was opened, or None if nothing matched on any page."""
import time
from typing import Iterable, Optional, Set
from playwright.sync_api import Page


def open_first_draft(
    page: Page,
    allowed_titles: Iterable[str],
    ignore_titles: Optional[Iterable[str]] = None,
) -> Optional[str]:
    print("\n--- Step 1: Open First Draft ---")

    allowed: Set[str] = set(allowed_titles)
    ignored: Set[str] = set(ignore_titles or [])

    print(f"Scanning for {len(allowed)} eligible draft titles "
          f"(ignoring {len(ignored)})...")

    page_count = 1
    while True:
        print(f">> Scanning Page {page_count}...")

        try:
            page.wait_for_selector("ytcp-video-row", state="visible", timeout=5000)
        except Exception:
            print("   [Info] No video rows detected on this page.")

        rows = page.locator("ytcp-video-row").all()

        for row in rows:
            try:
                row_text = row.inner_text()
                if "Draft" not in row_text:
                    continue

                title_link = row.locator("#video-title").first
                if not title_link.is_visible():
                    continue

                visible_title = title_link.inner_text().strip()

                if visible_title in ignored:
                    continue
                if visible_title not in allowed:
                    continue

                print(f">> Found Match: '{visible_title}'")
                print(">> Opening Draft...")
                title_link.click()
                return visible_title

            except Exception:
                # Stale element / UI re-render during scan
                continue

        print(f"   [Info] No match found on Page {page_count}.")

        next_button = page.locator("#navigate-after")
        if not next_button.is_visible() or next_button.get_attribute("aria-disabled") == "true":
            print(">> End of list reached. No matching drafts found.")
            break

        print(">> Navigating to next page...")
        next_button.click()
        time.sleep(3)
        page_count += 1

    return None
