from playwright.sync_api import Page
from publisher.open_draft import open_first_draft
from publisher.edit_description import update_description
from publisher.edit_metadata import uncheck_notify_subscribers

def process_single_draft(page: Page):
    print("\n=== STARTING SINGLE VIDEO PROCESSING ===")

    # Step 1: Open
    if not open_first_draft(page):
        return

    # Step 2: Description
    update_description(page)

    # Step 3: Metadata (Strict Checkbox)
    if not uncheck_notify_subscribers(page):
        print(">> Aborting due to metadata failure.")
        return

    print("\n>> All steps complete. Pausing execution for manual inspection.")