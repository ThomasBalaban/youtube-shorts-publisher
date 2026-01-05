import os
from playwright.sync_api import sync_playwright
# Import your new function
from config.navigation import navigate_to_shorts

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
        
        # Wait for the dashboard to load initially
        try:
            page.wait_for_selector("ytcp-navigation-drawer", timeout=30000)
        except:
            print("Dashboard didn't load. You might need to log in.")

        # --- CALL THE NAVIGATION FUNCTION ---
        navigate_to_shorts(page)

        print("\nBrowser is open. Ctrl+C in terminal to stop.")
        
        try:
            while True:
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("Stopping...")

if __name__ == "__main__":
    run()