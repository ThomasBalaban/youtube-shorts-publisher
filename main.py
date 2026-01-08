import os
import sys
from playwright.sync_api import sync_playwright
from config.navigation import navigate_to_shorts
from config.scraper import VideoScraper
from publisher.publisher import run_publisher  # Changed import
from settings import PROCESS_SINGLE_VIDEO, ENABLE_SCRAPING_MODE

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
        
        if navigate_to_shorts(page):
            
            # --- BRANCHING LOGIC ---
            if ENABLE_SCRAPING_MODE:
                print("\n=== MODE: SCRAPER ===")
                scraper = VideoScraper(page)
                scraper.scrape_all()
                
            elif PROCESS_SINGLE_VIDEO:
                # --- MODE: PUBLISHER (LOOPS INTERNALLY) ---
                print("\n=== MODE: PUBLISHER ===")
                run_publisher(page)
                
            else:
                print("No action selected in settings.py")
            
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