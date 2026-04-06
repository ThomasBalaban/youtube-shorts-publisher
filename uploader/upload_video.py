"""
uploader/upload_video.py

Handles uploading a new video through YouTube Studio's UI.
Reads jobs from uploader/upload_queue.json, written by an external app.

Queue file format (uploader/upload_queue.json):
[
  {
    "file_path": "/absolute/path/to/video.mp4",
    "title": "My Video Title",
    "youtube_description": "Description text here.",
    "hashtags": ["#Gaming", "#Shorts"],
    "tags": "gaming, funny, shorts",
    "schedule": true          // true = use schedule_manager, false = save as draft
  }
]

Each entry is removed from the queue after it is successfully processed.
Failed entries are moved to uploader/upload_queue_failed.json.
"""

import json
import os
import time
from pathlib import Path
from playwright.sync_api import Page

from config.navigation import navigate_to_shorts
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

# ---------------------------------------------------------------------------
# Paths — all queue files live inside the uploader/ folder
# ---------------------------------------------------------------------------
_UPLOADER_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE  = os.path.join(_UPLOADER_DIR, "upload_queue.json")
FAILED_FILE = os.path.join(_UPLOADER_DIR, "upload_queue_failed.json")


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------

def load_queue() -> list:
    """Returns the current list of pending upload jobs."""
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Uploader] Warning: Could not read {QUEUE_FILE}: {e}")
        return []


def _save_queue(jobs: list) -> None:
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)


def _save_failed(job: dict, reason: str) -> None:
    current = []
    if os.path.exists(FAILED_FILE):
        try:
            with open(FAILED_FILE, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            pass
    job["failure_reason"] = reason
    job["failed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    current.append(job)
    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)


# ---------------------------------------------------------------------------
# Upload steps
# ---------------------------------------------------------------------------

def _click_create_button(page: Page) -> bool:
    """Clicks the 'Create' / upload button to open the upload dialog."""
    print("[Uploader] Looking for 'Create' button...")

    selectors = [
        "#upload-btn",
        "ytcp-button#create-icon",
        "button[aria-label='Create']",
        "#create-icon",
    ]

    for attempt in range(10):
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    print(f"[Uploader] Clicked Create using: {selector}")
                    return True
            except Exception:
                continue
        print(f"[Uploader] Waiting for Create button... ({attempt + 1}/10)")
        page.wait_for_timeout(1500)

    print("[Uploader] ERROR: Could not find Create button.")
    return False


def _click_upload_videos_option(page: Page) -> bool:
    """After the Create dropdown opens, clicks 'Upload videos'."""
    print("[Uploader] Looking for 'Upload videos' menu option...")
    selectors = [
        "tp-yt-paper-item:has-text('Upload videos')",
        "ytcp-ve:has-text('Upload videos')",
        "text='Upload videos'",
    ]
    for attempt in range(8):
        for selector in selectors:
            try:
                opt = page.locator(selector).first
                if opt.is_visible():
                    opt.click()
                    print("[Uploader] Clicked 'Upload videos'.")
                    return True
            except Exception:
                continue
        page.wait_for_timeout(1000)

    print("[Uploader] ERROR: 'Upload videos' option not found.")
    return False


def _attach_file(page: Page, file_path: str) -> bool:
    """
    Locates the hidden file input inside the upload dialog and attaches the file.
    Returns True when the file has been attached and the upload has started.
    """
    abs_path = str(Path(file_path).resolve())

    if not os.path.exists(abs_path):
        print(f"[Uploader] ERROR: File not found: {abs_path}")
        return False

    print(f"[Uploader] Attaching file: {abs_path}")

    try:
        file_input = page.locator("input[type='file']").first
        file_input.wait_for(state="attached", timeout=15000)
        file_input.set_input_files(abs_path)
        print("[Uploader] File attached. Upload starting...")
        return True
    except Exception as e:
        print(f"[Uploader] ERROR attaching file: {e}")
        return False


def _wait_for_upload_complete(page: Page, timeout_minutes: int = 10) -> bool:
    """
    Waits until YouTube Studio indicates the upload and processing is done.
    Returns True when complete, False on timeout.
    """
    print("[Uploader] Waiting for upload to complete...")
    timeout_ms = timeout_minutes * 60 * 1000
    poll_interval = 3000
    elapsed = 0

    try:
        page.wait_for_selector("#title-textarea", state="visible", timeout=30000)
        print("[Uploader] Upload dialog opened. Monitoring progress...")
    except Exception:
        print("[Uploader] Warning: Title textarea not detected quickly.")

    while elapsed < timeout_ms:
        try:
            progress_bar = page.locator("ytcp-video-upload-progress")
            if progress_bar.count() > 0:
                progress_text = progress_bar.inner_text()
                print(f"[Uploader]   Progress: {progress_text.strip()[:60]}")

                if any(kw in progress_text for kw in ["Upload complete", "Checks complete", "Video uploaded"]):
                    print("[Uploader] Upload complete!")
                    return True
            else:
                print("[Uploader] Progress indicator gone. Upload likely complete.")
                return True

        except Exception:
            return True

        page.wait_for_timeout(poll_interval)
        elapsed += poll_interval

    print(f"[Uploader] ERROR: Upload did not finish within {timeout_minutes} minutes.")
    return False


# ---------------------------------------------------------------------------
# Main upload orchestrator
# ---------------------------------------------------------------------------

def upload_one_video(page: Page, job: dict) -> bool:
    """
    Runs the full upload + metadata + scheduling flow for a single job.
    Returns True on success, False on any failure.
    """
    file_path  = job.get("file_path", "")
    title      = job.get("title", "Untitled Short")
    description = job.get("youtube_description", "")
    hashtags   = job.get("hashtags", [])
    tags       = job.get("tags", "")
    should_schedule = job.get("schedule", True)

    print(f"\n[Uploader] ── Starting upload: '{title}' ──")
    print(f"[Uploader]   File: {file_path}")
    print(f"[Uploader]   Schedule: {should_schedule}")

    if not _click_create_button(page):   return False
    time.sleep(1)
    if not _click_upload_videos_option(page): return False
    time.sleep(1)
    if not _attach_file(page, file_path): return False
    if not _wait_for_upload_complete(page): return False

    if title:
        if not update_title(page, title): return False

    if not update_description(page, description, hashtags): return False
    update_tags(page, tags)

    if not uncheck_notify_subscribers(page): return False

    print("[Uploader] Moving to Ad Suitability...")
    if not click_next(page): return False
    if not is_ad_suitability_completed(page):
        if not complete_ad_suitability(page): return False

    print("[Uploader] Moving to Video Elements...")
    if not click_next(page): return False
    if not handle_video_elements(page): return False

    print("[Uploader] Moving to Checks...")
    if not click_next(page): return False
    if not handle_checks(page): return False

    print("[Uploader] Moving to Visibility...")
    if not click_next(page): return False

    if should_schedule:
        if not handle_visibility(page): return False
    else:
        print("[Uploader] Saving as private draft (schedule=false).")

    if not click_save(page): return False

    print(f"[Uploader] ✓ Upload complete: '{title}'")
    return True


# ---------------------------------------------------------------------------
# Runner (called from main.py)
# ---------------------------------------------------------------------------

def run_uploader(page: Page) -> None:
    """
    Processes all jobs in uploader/upload_queue.json one at a time.
    Successful jobs are removed from the queue.
    Failed jobs are moved to uploader/upload_queue_failed.json.
    """
    print("\n=== MODE: UPLOADER ===")

    jobs = load_queue()

    if not jobs:
        print("[Uploader] upload_queue.json is empty or missing. Nothing to do.")
        print(f"[Uploader] Expected queue file at: {QUEUE_FILE}")
        return

    print(f"[Uploader] Found {len(jobs)} job(s) in queue.")

    remaining_jobs = list(jobs)

    for i, job in enumerate(jobs):
        title = job.get("title", "Untitled")
        print(f"\n[Uploader] ── Job {i + 1}/{len(jobs)}: '{title}' ──")

        if not job.get("file_path"):
            print("[Uploader] ERROR: Job missing 'file_path'. Skipping.")
            _save_failed(job, "Missing file_path")
            remaining_jobs.remove(job)
            _save_queue(remaining_jobs)
            continue

        if not navigate_to_shorts(page):
            print("[Uploader] CRITICAL: Navigation failed. Aborting batch.")
            break

        success = upload_one_video(page, job)

        remaining_jobs.remove(job)
        _save_queue(remaining_jobs)

        if success:
            print(f"[Uploader] Job {i + 1} succeeded.")
        else:
            print(f"[Uploader] Job {i + 1} FAILED. Moving to upload_queue_failed.json.")
            _save_failed(job, "upload_one_video returned False")

        if remaining_jobs:
            print("[Uploader] Waiting 5s before next job...")
            time.sleep(5)

    print("\n[Uploader] All jobs processed.")