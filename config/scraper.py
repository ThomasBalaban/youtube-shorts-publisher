import time
import json
import re
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import Page

class VideoScraper:
    def __init__(self, page: Page):
        self.page = page
        self.timezone = ZoneInfo("America/New_York")
        self.data_folder = "saved_shorts_data"
        self._ensure_data_folder()

    def _ensure_data_folder(self):
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)

    def _parse_tooltip_date(self, text):
        """Helper to parse the scheduled date from tooltip."""
        try:
            match = re.search(r"public on (.+)", text)
            if not match:
                return None, "No date pattern found"

            raw_date_str = match.group(1).strip()
            clean_date_str = raw_date_str.replace("\u202f", " ")
            dt_naive = datetime.strptime(clean_date_str, "%B %d, %Y at %I:%M %p")
            dt_aware = dt_naive.replace(tzinfo=self.timezone)
            
            return dt_aware, clean_date_str
        except Exception as e:
            return None, str(e)

    def scrape_all(self):
        """
        Scrapes BOTH Drafts and Scheduled videos in a single pass.
        Outputs three JSON files:
        1. draft_videos.json
        2. scheduled_videos.json
        3. backtrack_videos.json (Subset of above with 'Backtrack' in title)
        """
        print("\n--- Starting Unified Scraper (Drafts + Scheduled) ---")
        
        drafts_data = []
        scheduled_data = []
        page_count = 1
        
        # --- STEP 1: SCAN PAGES ---
        while True:
            print(f"Scanning page {page_count}...")
            
            try:
                self.page.wait_for_selector("ytcp-video-row", state="visible", timeout=5000)
            except:
                print("No video rows found.")
                break

            rows = self.page.locator("ytcp-video-row").all()
            
            for row in rows:
                try:
                    # Get status text
                    visibility_cell = row.locator(".tablecell-visibility")
                    status_text = visibility_cell.inner_text().strip()
                    
                    # Get Title
                    title_el = row.locator("#video-title").first
                    if title_el.count() == 0:
                        continue
                    title = title_el.inner_text().strip()

                    # === LOGIC A: DRAFT VIDEO ===
                    if "Draft" in status_text:
                        print(f" -> Found Draft: {title}")
                        
                        # Check for 'Backtrack' in title
                        has_backtrack = "Backtrack" in title
                        
                        drafts_data.append({
                            "title": title,
                            "has_backtrack": has_backtrack
                        })

                    # === LOGIC B: SCHEDULED VIDEO ===
                    elif "Scheduled" in status_text:
                        print(f" -> Found Scheduled: {title}")
                        
                        # Hover to get tooltip
                        hover_target = visibility_cell.locator(".label-span", has_text="Scheduled").first
                        timestamp_data = None
                        raw_tooltip = "Label not visible"

                        if hover_target.is_visible():
                            hover_target.hover()
                            try:
                                tooltip = self.page.locator("ytcp-paper-tooltip-body", has_text="public on").first
                                tooltip.wait_for(state="visible", timeout=2000)
                                raw_tooltip = tooltip.inner_text().strip()
                                
                                dt_obj, debug_info = self._parse_tooltip_date(raw_tooltip)
                                
                                if dt_obj:
                                    timestamp_data = {
                                        "iso": dt_obj.isoformat(),
                                        "year": dt_obj.year,
                                        "month": dt_obj.month,
                                        "day": dt_obj.day,
                                        "hour": dt_obj.hour,
                                        "minute": dt_obj.minute,
                                        "timezone": str(self.timezone),
                                        "raw_clean": debug_info
                                    }
                            except:
                                raw_tooltip = "Tooltip capture failed"
                            
                            self.page.mouse.move(0, 0) # Clear tooltip

                        scheduled_data.append({
                            "title": title,
                            "original_tooltip": raw_tooltip,
                            "schedule": timestamp_data
                        })

                except Exception as e:
                    print(f"Error processing row: {e}")
                    continue

            # --- STEP 2: PAGINATION ---
            next_button = self.page.locator("#navigate-after")
            if not next_button.is_visible() or next_button.get_attribute("aria-disabled") == "true":
                print("End of list reached.")
                break
            
            print("Moving to next page...")
            next_button.click()
            time.sleep(3) 
            page_count += 1

        # --- STEP 3: SAVE PRIMARY FILES ---
        drafts_path = os.path.join(self.data_folder, "draft_videos.json")
        scheduled_path = os.path.join(self.data_folder, "scheduled_videos.json")

        with open(drafts_path, "w", encoding="utf-8") as f:
            json.dump(drafts_data, f, indent=4)
            
        with open(scheduled_path, "w", encoding="utf-8") as f:
            json.dump(scheduled_data, f, indent=4, default=str)

        # --- STEP 4: GENERATE BACKTRACK FILE ---
        # We filter the lists we just generated based on the criteria
        print("\n>> Generating 'Backtrack' subset file...")
        backtrack_data = []

        # 1. Add matching Drafts (using the boolean flag we created)
        for video in drafts_data:
            if video.get("has_backtrack", False):
                entry = video.copy()
                entry["current_status"] = "Draft"
                backtrack_data.append(entry)

        # 2. Add matching Scheduled videos (checking title string)
        for video in scheduled_data:
            if "Backtrack" in video.get("title", ""):
                entry = video.copy()
                entry["current_status"] = "Scheduled"
                backtrack_data.append(entry)

        backtrack_path = os.path.join(self.data_folder, "backtrack_videos.json")
        with open(backtrack_path, "w", encoding="utf-8") as f:
            json.dump(backtrack_data, f, indent=4, default=str)

        print(f"\nScrape Complete.")
        print(f"Drafts saved: {len(drafts_data)} -> {drafts_path}")
        print(f"Scheduled saved: {len(scheduled_data)} -> {scheduled_path}")
        print(f"Backtrack subset: {len(backtrack_data)} -> {backtrack_path}")