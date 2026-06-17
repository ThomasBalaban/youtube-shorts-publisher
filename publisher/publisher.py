import time
from typing import List
from playwright.sync_api import Page

from settings import VIDEOS_TO_PROCESS_COUNT
from config.navigation import navigate_to_shorts

from publisher.strategist_client import StrategistClient
from publisher.open_draft import open_first_draft
from publisher.failed_log import record_failed_short
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


def process_one_video(
    page: Page,
    client: StrategistClient,
    allowed_titles: set,
    ignored_titles: List[str],
) -> str:
    """
    Returns:
      "SUCCESS"    — video processed
      "NO_DRAFTS"  — no matching draft on any page
      "ERROR"      — technical failure (recorded + skipped, batch continues)
    """
    current_title = open_first_draft(page, allowed_titles, ignored_titles)
    if not current_title:
        return "NO_DRAFTS"

    meta = client.lookup_by_draft_title(current_title)

    def fail(reason: str) -> str:
        """Record the failed draft, add it to the ignore set so the next
        loop iteration skips it (otherwise we'd re-open the same draft
        forever), and return ERROR so the caller moves on."""
        if current_title not in ignored_titles:
            ignored_titles.append(current_title)
        record_failed_short(
            current_title,
            reason,
            base_key=getattr(meta, "base_key", None),
            intended_title=getattr(meta, "title", None),
        )
        print(f">> Recorded failed short '{current_title}' "
              f"(reason: {reason}); skipping and moving on.")
        return "ERROR"

    if not meta:
        print(f"Error: opened '{current_title}' but no strategist match.")
        return fail("no_strategist_match")

    print(f">> Processing draft: '{current_title}'")
    print(f"   → base_key:  {meta.base_key}")
    print(f"   → title:     {meta.title!r}  (source: {meta.title_source})")

    if meta.title:
        if not update_title(page, meta.title):
            return fail("title_update")

    if not update_description(page, meta.description or "", meta.hashtags):
        return fail("description_update")

    update_tags(page, meta.tags or "")

    if not uncheck_notify_subscribers(page):
        return fail("notify_subscribers_toggle")

    print(">> Moving to Ad Suitability tab...")
    if not click_next(page): return fail("next_to_ad_suitability")

    if not is_ad_suitability_completed(page):
        if not complete_ad_suitability(page): return fail("ad_suitability")
    else:
        print(">> Ad Suitability already done.")

    print(">> Moving to Video Elements tab...")
    if not click_next(page): return fail("next_to_video_elements")
    if not handle_video_elements(page): return fail("video_elements")

    print(">> Moving to Checks tab...")
    if not click_next(page): return fail("next_to_checks")
    if not handle_checks(page): return fail("checks")

    print(">> Moving to Visibility tab...")
    if not click_next(page): return fail("next_to_visibility")
    if not handle_visibility(page): return fail("visibility")

    if not click_save(page): return fail("save")

    print(">> Video processed successfully.")
    return "SUCCESS"


def run_publisher(page: Page) -> None:
    client = StrategistClient()
    allowed_titles = set(client.known_draft_titles())
    print(f"Loaded {len(allowed_titles)} eligible draft titles from strategist.")

    target_count = VIDEOS_TO_PROCESS_COUNT
    print(f"\n=== STARTING PUBLISHER: {target_count} Videos ===")

    videos_processed = 0
    videos_failed = 0
    ignored_titles: List[str] = []

    while videos_processed < target_count:
        print(f"\n{'-' * 50}")
        print(f"ATTEMPTING NEXT VIDEO (Processed: {videos_processed}/{target_count}"
              f"{f', Failed: {videos_failed}' if videos_failed else ''})")
        print(f"{'-' * 50}")

        if not navigate_to_shorts(page):
            print("CRITICAL: Navigation failed. Aborting.")
            break

        status = process_one_video(page, client, allowed_titles, ignored_titles)

        if status == "SUCCESS":
            videos_processed += 1
            if videos_processed < target_count:
                print(">> Waiting 5 seconds before next video...")
                time.sleep(5)

        elif status == "NO_DRAFTS":
            print(">> No more matching drafts found.")
            break

        elif status == "ERROR":
            # The failed draft was recorded to failed_shorts.json and added to
            # the ignore set, so we move on to the next draft instead of
            # halting the whole batch. The ignore set guarantees we don't
            # re-open it; when only failed/ignored drafts remain, the next
            # scan returns NO_DRAFTS and the loop ends.
            videos_failed += 1
            print(">> Moving on to the next draft.")
            time.sleep(2)

    summary = f"\n=== BATCH PROCESSING COMPLETE (published: {videos_processed}"
    if videos_failed:
        from publisher.failed_log import FAILED_LOG
        summary += f", failed: {videos_failed} → see {FAILED_LOG.name}"
    summary += ") ==="
    print(summary)
