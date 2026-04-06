"""
uploader/upload_video.py

Scans (project_parent)/simpleautosubs/output for video files and uploads
each one through YouTube Studio — no form filling, no wizard steps.

After attaching the file and waiting for the upload to finish, any open
dialog is closed and the next file is processed.

On success: file is deleted from output/.
On failure: file is moved to output/failed/.
"""

import os
import time
from pathlib import Path
from playwright.sync_api import Page

from config.navigation import navigate_to_shorts
from publisher.close_draft import close_dialog

# ---------------------------------------------------------------------------
# Output directory — (parent of this project) / simpleautosubs / output
# ---------------------------------------------------------------------------
_THIS_FILE     = Path(os.path.abspath(__file__))
_PROJECT_DIR   = _THIS_FILE.parent.parent
_SHARED_PARENT = _PROJECT_DIR.parent
OUTPUT_DIR     = _SHARED_PARENT / "simpleautosubs" / "output"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def _get_pending_videos() -> list[Path]:
    if not OUTPUT_DIR.exists():
        return []
    return [
        f for f in sorted(OUTPUT_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]


def _mark_success(video_path: Path) -> None:
    try:
        video_path.unlink()
        print(f"[Uploader] Deleted: {video_path.name}")
    except Exception as e:
        print(f"[Uploader] Warning: Could not delete {video_path.name}: {e}")


def _mark_failed(video_path: Path) -> None:
    failed_dir = OUTPUT_DIR / "failed"
    failed_dir.mkdir(exist_ok=True)
    try:
        video_path.rename(failed_dir / video_path.name)
        print(f"[Uploader] Moved to failed/: {video_path.name}")
    except Exception as e:
        print(f"[Uploader] Warning: Could not move {video_path.name}: {e}")


# ---------------------------------------------------------------------------
# Upload steps
# ---------------------------------------------------------------------------

def _click_create_button(page: Page) -> bool:
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
    print("[Uploader] Looking for 'Upload videos' option...")
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


def _attach_file(page: Page, video_path: Path) -> bool:
    print(f"[Uploader] Attaching: {video_path.name}")
    try:
        file_input = page.locator("input[type='file']").first
        file_input.wait_for(state="attached", timeout=15000)
        file_input.set_input_files(str(video_path))
        print("[Uploader] File attached. Upload starting...")
        return True
    except Exception as e:
        print(f"[Uploader] ERROR attaching file: {e}")
        return False


def _wait_for_upload_complete(page: Page, timeout_minutes: int = 10) -> bool:
    """Polls the progress bar until upload finishes or times out."""
    print("[Uploader] Waiting for upload to complete...")
    timeout_ms = timeout_minutes * 60 * 1000
    poll_interval = 3000
    elapsed = 0

    # Wait for the upload dialog to open at all
    try:
        page.wait_for_selector("ytcp-uploads-dialog", state="visible", timeout=30000)
        print("[Uploader] Upload dialog open.")
    except Exception:
        print("[Uploader] Warning: Upload dialog slow to appear.")

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
# Single video orchestrator
# ---------------------------------------------------------------------------

def upload_one_video(page: Page, video_path: Path) -> bool:
    print(f"\n[Uploader] ── Uploading: '{video_path.name}' ──")

    if not _click_create_button(page):        return False
    time.sleep(1)
    if not _click_upload_videos_option(page): return False
    time.sleep(1)
    if not _attach_file(page, video_path):    return False
    close_dialog(page)

    print(f"[Uploader] ✓ Done: '{video_path.name}'")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_uploader(page: Page) -> None:
    from settings import UPLOAD_LIMIT

    print(f"\n=== MODE: UPLOADER ===")
    print(f"[Uploader] Scanning: {OUTPUT_DIR}")

    if not OUTPUT_DIR.exists():
        print(f"[Uploader] Output directory does not exist: {OUTPUT_DIR}")
        return

    videos = _get_pending_videos()

    if not videos:
        print("[Uploader] No video files found.")
        return

    if UPLOAD_LIMIT and UPLOAD_LIMIT > 0:
        if len(videos) > UPLOAD_LIMIT:
            print(f"[Uploader] UPLOAD_LIMIT={UPLOAD_LIMIT}: capping at {UPLOAD_LIMIT} of {len(videos)} file(s).")
            videos = videos[:UPLOAD_LIMIT]

    print(f"[Uploader] Uploading {len(videos)} file(s).")

    for i, video_path in enumerate(videos, 1):
        print(f"\n[Uploader] ── File {i}/{len(videos)}: {video_path.name} ──")

        if not navigate_to_shorts(page):
            print("[Uploader] CRITICAL: Navigation failed. Aborting.")
            break

        success = upload_one_video(page, video_path)

        if success:
            _mark_success(video_path)
        else:
            _mark_failed(video_path)

        if i < len(videos):
            print("[Uploader] Waiting 5s before next upload...")
            time.sleep(5)

    print("\n[Uploader] All done.")