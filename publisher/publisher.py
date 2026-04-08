import time
import json
import os
from playwright.sync_api import Page
from settings import VIDEOS_TO_PROCESS_COUNT
from config.navigation import navigate_to_shorts

# Import steps
from publisher.open_draft import open_first_draft
from publisher.edit_title import update_title
from publisher.edit_description import update_description
from publisher.edit_tags import update_tags
from publisher.edit_metadata import uncheck_notify_subscribers
from publisher.wizard_navigation import click_next
from publisher.ad_suitability import is_ad_suitability_completed, complete_ad_suitability
from publisher.video_elements import handle_video_elements
from publisher.checks import handle_checks
from publisher.visibility import handle_visibility
from publisher.save_publish import click_save

def load_analysis_data():
    path = "draft_analysis.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load {path}: {e}")
    return []

def process_one_video(page: Page, analysis_data: list, ignored_titles: list):
    """
    Returns:
    - "SUCCESS": Video processed.
    - "NO_DRAFTS": No matching drafts found.
    - "ERROR": Technical error.
    """
    current_title = open_first_draft(page, analysis_data, ignored_titles)

    if not current_title:
        return "NO_DRAFTS"

    video_data = next((item for item in analysis_data if item.get("title") == current_title), None)

    if not video_data:
        print(f"Error: Logic mismatch. Opened '{current_title}' but data missing.")
        ignored_titles.append(current_title)
        return "ERROR"

    print(f">> Processing found match: '{current_title}'...")

    new_title = video_data.get("new_title")
    if new_title:
        if not update_title(page, new_title): return "ERROR"

    description = video_data.get("youtube_description", "")
    hashtags = video_data.get("hashtags", [])
    if not update_description(page, description, hashtags): return "ERROR"

    tags = video_data.get("tags", "")
    update_tags(page, tags)

    if not uncheck_notify_subscribers(page): return "ERROR"

    print(">> Moving to Ad Suitability tab...")
    if not click_next(page): return "ERROR"

    if not is_ad_suitability_completed(page):
        if not complete_ad_suitability(page): return "ERROR"
    else:
        print(">> Ad Suitability already done.")

    print(">> Moving to Video Elements tab...")
    if not click_next(page): return "ERROR"
    if not handle_video_elements(page): return "ERROR"

    print(">> Moving to Checks tab...")
    if not click_next(page): return "ERROR"
    if not handle_checks(page): return "ERROR"

    print(">> Moving to Visibility tab...")
    if not click_next(page): return "ERROR"
    if not handle_visibility(page): return "ERROR"

    if not click_save(page): return "ERROR"

    print(">> Video processed successfully.")
    return "SUCCESS"

def run_publisher(page: Page):
    analysis_data = load_analysis_data()
    print(f"Loaded {len(analysis_data)} analysis entries.")

    target_count = VIDEOS_TO_PROCESS_COUNT
    print(f"\n=== STARTING PUBLISHER: {target_count} Videos ===")

    videos_processed = 0
    ignored_titles = []

    while videos_processed < target_count:
        print(f"\n--------------------------------------------------")
        print(f"ATTEMPTING NEXT VIDEO (Processed: {videos_processed}/{target_count})")
        print(f"--------------------------------------------------")

        if not navigate_to_shorts(page):
            print("CRITICAL: Navigation failed. Aborting.")
            break

        status = process_one_video(page, analysis_data, ignored_titles)

        if status == "SUCCESS":
            videos_processed += 1
            if videos_processed < target_count:
                print(">> Waiting 5 seconds before next video...")
                time.sleep(5)

        elif status == "NO_DRAFTS":
            print(">> No more matching drafts found.")
            break

        elif status == "ERROR":
            print(">> Critical error. Stopping to prevent bad publishing.")
            break

    print("\n=== BATCH PROCESSING COMPLETE ===")