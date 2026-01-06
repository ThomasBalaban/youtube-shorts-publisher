import time
from playwright.sync_api import Page

class VideoScraper:
    def __init__(self, page: Page):
        self.page = page

    def find_drafts(self):
        draft_titles = []
        page_count = 1
        
        while True:
            print(f"Scanning page {page_count}...")
            
            # Wait for rows to appear
            try:
                self.page.wait_for_selector("ytcp-video-row", state="visible", timeout=5000)
            except:
                print("No video rows found on this page.")
                break

            rows = self.page.locator("ytcp-video-row").all()
            drafts_on_page = 0

            for row in rows:
                try:
                    # 1. Check for 'Draft' status (Using the method that worked)
                    visibility_cell = row.locator(".tablecell-visibility")
                    status_element = visibility_cell.locator(".ytcp-video-row").first
                    status_text = status_element.inner_text().strip()
                    
                    if status_text == "Draft":
                        drafts_on_page += 1
                        
                        # 2. Extract Title (New Logic)
                        # Look for class video-title-wrapper, then the 'a' tag inside it
                        title_element = row.locator(".video-title-wrapper a").first
                        
                        if title_element.count() > 0:
                            title = title_element.inner_text().strip()
                            print(f" -> Found Draft: {title}")
                            draft_titles.append(title)
                        else:
                            print(" -> Found Draft, but could not extract title.")
                            
                except Exception as e:
                    continue

            print(f"Found {len(rows)} videos and {drafts_on_page} drafts on this page.")

            # 3. Pagination
            next_button = self.page.locator("#navigate-after")
            
            if not next_button.is_visible() or next_button.get_attribute("aria-disabled") == "true":
                print("End of list reached.")
                break
            
            print("Moving to next page...")
            next_button.click()
            time.sleep(3) 
            page_count += 1

        return draft_titles