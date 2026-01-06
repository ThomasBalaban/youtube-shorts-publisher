import os
import sys
from playwright.sync_api import sync_playwright
from config.navigation import navigate_to_shorts
from config.scraper import VideoScraper
from publisher.publisher import process_single_draft
from settings import PROCESS_SINGLE_VIDEO

def run():
    user_data_dir = os.path.join(os.getcwd(), "user_data")

    with sync_playwright() as p:
        print(f"Launching browser with profile at: {user_data_dir}")
        
        context = p.chromium.launch_persistent_context(
            user_data_dir, 
            headless=False,
            channel="chrome", 
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.pages[0]
        
        print("Navigating to YouTube Studio...")
        page.goto("https://studio.youtube.com/")
        
        # 1. Navigate to Shorts
        if navigate_to_shorts(page):
            
            # 2. Check Configuration
            if PROCESS_SINGLE_VIDEO:
                # --- SINGLE VIDEO MODE ---
                process_single_draft(page)
            else:
                # --- BULK SCRAPE MODE ---
                print("\n--- Starting Draft Scraper ---")
                scraper = VideoScraper(page)
                draft_titles = scraper.find_drafts()
                
                print(f"\nTotal Drafts Collected: {len(draft_titles)}")
                if len(draft_titles) > 0:
                    print("Draft Titles:", draft_titles)
                else:
                    print("No draft titles collected.")
            
        else:
            print("Could not navigate to Shorts. Aborting.")

        print("\nProcess finished. Browser remaining open...")
        print("Ctrl+C to close.")
        try:
            while True:
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("Stopping...")

if __name__ == "__main__":
    run()