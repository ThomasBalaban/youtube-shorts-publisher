import time
from playwright.sync_api import Page
from settings import VIDEOS_TO_PROCESS_COUNT
from config.navigation import navigate_to_shorts

# Import steps
from publisher.open_draft import open_first_draft
from publisher.edit_description import update_description
from publisher.edit_metadata import uncheck_notify_subscribers
from publisher.wizard_navigation import click_next
from publisher.ad_suitability import is_ad_suitability_completed, complete_ad_suitability
from publisher.video_elements import handle_video_elements
from publisher.checks import handle_checks
from publisher.visibility import handle_visibility
from publisher.save_publish import click_save

def process_one_video(page: Page):
    """
    Encapsulates the logic for a single video. 
    Returns True if successful, False if failed.
    """
    # 1. Open Draft
    if not open_first_draft(page):
        return False

    # 2. Edit Description
    if not update_description(page):
        return False

    # 3. Uncheck Notify Subscribers
    if not uncheck_notify_subscribers(page):
        return False

    # --- PRE-CHECK: AD SUITABILITY STATUS ---
    ad_suitability_already_done = is_ad_suitability_completed(page)

    # 4. Navigate to Ad Suitability
    print(">> Moving to Ad Suitability tab...")
    if not click_next(page):
        return False
        
    # 5. Confirm Ad Suitability
    if ad_suitability_already_done:
        print(">> Skipping Ad Suitability form (previously completed).")
    else:
        if not complete_ad_suitability(page):
            return False

    # 6. Navigate to Video Elements
    print(">> Moving to Video Elements tab...")
    if not click_next(page):
        return False

    # 7. Handle Video Elements
    if not handle_video_elements(page):
        return False

    # 8. Navigate to Checks
    print(">> Moving to Checks tab...")
    if not click_next(page):
        return False

    # 9. Verify Checks
    if not handle_checks(page):
        return False

    # 10. Navigate to Visibility
    print(">> Checks passed. Moving to Visibility tab...")
    if not click_next(page):
        return False

    # 11. Handle Visibility (Scheduling)
    if not handle_visibility(page):
        return False

    # 12. Save / Schedule
    if not click_save(page):
        return False

    print(">> Video processed successfully.")
    return True

def run_publisher(page: Page):
    """
    Main loop that processes multiple videos based on settings.
    """
    print(f"\n=== STARTING PUBLISHER: TARGET {VIDEOS_TO_PROCESS_COUNT} VIDEOS ===")
    
    for i in range(VIDEOS_TO_PROCESS_COUNT):
        print(f"\n--------------------------------------------------")
        print(f"STARTING VIDEO {i+1} of {VIDEOS_TO_PROCESS_COUNT}")
        print(f"--------------------------------------------------")
        
        # 1. Ensure we are on the Shorts list (Reset state)
        print(">> Resetting navigation to Shorts list...")
        if not navigate_to_shorts(page):
            print("CRITICAL: Could not navigate to Shorts list. Aborting loop.")
            break
        
        # 2. Process one video
        success = process_one_video(page)
        
        if not success:
            print(f"\n>> Stopping loop due to failure on video {i+1}.")
            break
            
        print(f"\n>> Video {i+1} complete. Waiting 5 seconds before next...")
        time.sleep(5)

    print("\n=== BATCH PROCESSING COMPLETE ===")