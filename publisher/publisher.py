from playwright.sync_api import Page
from publisher.open_draft import open_first_draft
from publisher.edit_description import update_description
from publisher.edit_metadata import uncheck_notify_subscribers
from publisher.wizard_navigation import click_next
from publisher.ad_suitability import is_ad_suitability_completed, complete_ad_suitability
from publisher.video_elements import handle_video_elements
from publisher.checks import handle_checks
from publisher.visibility import handle_visibility
from publisher.save_publish import click_save

def process_single_draft(page: Page):
    print("\n=== STARTING SINGLE VIDEO PROCESSING ===")

    # 1. Open Draft
    if not open_first_draft(page):
        return

    # 2. Edit Description
    if not update_description(page):
        return

    # 3. Uncheck Notify Subscribers
    if not uncheck_notify_subscribers(page):
        print(">> Aborting due to metadata failure.")
        return

    # --- PRE-CHECK: AD SUITABILITY STATUS ---
    ad_suitability_already_done = is_ad_suitability_completed(page)

    # 4. Navigate to Ad Suitability
    print(">> Moving to Ad Suitability tab...")
    if not click_next(page):
        return
        
    # 5. Confirm Ad Suitability
    if ad_suitability_already_done:
        print(">> Skipping Ad Suitability form (previously completed).")
    else:
        if not complete_ad_suitability(page):
            print(">> Aborting due to Ad Suitability failure.")
            return

    # 6. Navigate to Video Elements
    print(">> Moving to Video Elements tab...")
    if not click_next(page):
        return

    # 7. Handle Video Elements
    if not handle_video_elements(page):
        return

    # 8. Navigate to Checks
    print(">> Moving to Checks tab...")
    if not click_next(page):
        return

    # 9. Verify Checks
    if not handle_checks(page):
        print(">> Aborting due to Checks failure.")
        return

    # 10. Navigate to Visibility
    print(">> Checks passed. Moving to Visibility tab...")
    if not click_next(page):
        return

    # 11. Handle Visibility (Unlisted)
    if not handle_visibility(page):
        print(">> Aborting due to Visibility failure.")
        return

    # 12. Save / Publish
    if not click_save(page):
        print(">> Aborting: Could not click Save.")
        return

    print("\n>> All steps complete. Video saved successfully!")
    print(">> Pausing execution for manual inspection.")