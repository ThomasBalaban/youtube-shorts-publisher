from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        # headless=False lets you actually see the browser window
        browser = p.chromium.launch(headless=False)
        
        # Create a new tab
        page = browser.new_page()
        
        print("Navigating to YouTube...")
        page.goto("https://www.youtube.com")

        # Get the title to verify we are there
        print(f"Page title: {page.title()}")

        # Keep the script running so the browser doesn't close immediately
        input("Press Enter in the terminal to close the browser...")
        
        browser.close()

if __name__ == "__main__":
    run()