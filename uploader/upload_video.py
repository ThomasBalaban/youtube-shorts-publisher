"""
uploader/upload_video.py

Scans (project_parent)/simpleautosubs/output for video files and uploads
them in batches of up to 15 through a single YouTube Studio dialog session.

Flow per batch:
  1. Open Create -> Upload videos dialog
  2. Attach all files at once
  3. Wait 5 seconds, then click the dialog close button
     (handles both single-video and multi-video upload screens)
  4. Wait up to 3 minutes for YouTube to finish processing in the background
  5. Hard-cap: if the batch hasn't finished within 10 minutes, force-close and move on
  6. Repeat for next batch automatically

Files are NOT deleted. Uploaded filenames tracked in uploader/uploaded_files.json.
"""

import json
import os
import time
from pathlib import Path
from playwright.sync_api import Page

from config.navigation import navigate_to_shorts
from uploader.check_unuploaded import run_audit

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_THIS_FILE     = Path(os.path.abspath(__file__))
_PROJECT_DIR   = _THIS_FILE.parent.parent
_SHARED_PARENT = _PROJECT_DIR.parent
OUTPUT_DIR     = _SHARED_PARENT / "simpleautosubs" / "output"
UPLOADED_LOG   = _PROJECT_DIR / "uploader" / "uploaded_files.json"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
BATCH_SIZE = 15

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------
POST_ATTACH_WAIT_S   = 5     # seconds to wait after attaching before closing dialog
POST_CLOSE_WAIT_S    = 180   # 3 minutes — let YouTube process uploads in background
BATCH_HARD_CAP_S     = 600   # 10 minutes — absolute ceiling per batch


# ---------------------------------------------------------------------------
# Upload log helpers
# ---------------------------------------------------------------------------

def _load_uploaded_log() -> set:
    if UPLOADED_LOG.exists():
        try:
            with open(UPLOADED_LOG, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_uploaded_log(uploaded: set) -> None:
    try:
        with open(UPLOADED_LOG, "w") as f:
            json.dump(sorted(uploaded), f, indent=2)
    except Exception as e:
        print(f"[Uploader] Warning: Could not save uploaded log: {e}")


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def _get_pending_videos(uploaded: set) -> list[Path]:
    if not OUTPUT_DIR.exists():
        return []
    return [
        f for f in sorted(OUTPUT_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        and f.name not in uploaded
    ]


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


def _attach_files(page: Page, video_paths: list[Path]) -> bool:
    print(f"[Uploader] Attaching {len(video_paths)} file(s) at once...")
    try:
        file_input = page.locator("input[type='file']").first
        file_input.wait_for(state="attached", timeout=15000)
        file_input.set_input_files([str(p) for p in video_paths])
        print("[Uploader] All files attached. Uploads starting...")
        return True
    except Exception as e:
        print(f"[Uploader] ERROR attaching files: {e}")
        return False


def _close_upload_dialog(page: Page) -> bool:
    """
    Clicks the dialog close button that works for both single-video and
    multi-video upload screens. Called ~5 seconds after attaching files.
    YouTube continues uploading in the background after this is dismissed.
    """
    print("[Uploader] Closing upload dialog (background upload continues)...")

    close_selectors = [
        "#ytcp-uploads-dialog-close-button",
        "ytcp-uploads-dialog #close-button",
        "ytcp-icon-button[aria-label='Close']",
    ]

    for selector in close_selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=3000):
                btn.click()
                print(f"[Uploader] Dialog closed via: {selector}")
                return True
        except Exception:
            continue

    print("[Uploader] Warning: Could not find dialog close button — upload may still be running.")
    return False


def _wait_with_progress(label: str, total_seconds: int, page: Page) -> None:
    """Waits total_seconds, printing progress every 30 seconds."""
    print(f"[Uploader] {label} — waiting {total_seconds // 60}m {total_seconds % 60}s...")
    elapsed = 0
    while elapsed < total_seconds:
        chunk = min(30, total_seconds - elapsed)
        page.wait_for_timeout(chunk * 1000)
        elapsed += chunk
        remaining = total_seconds - elapsed
        if remaining > 0:
            print(f"[Uploader]   {elapsed}s elapsed, {remaining}s remaining...")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_uploader(page: Page) -> None:
    from settings import UPLOAD_LIMIT

    print(f"\n=== MODE: UPLOADER ===")
    print(f"[Uploader] Scanning: {OUTPUT_DIR}")

    if not OUTPUT_DIR.exists():
        print(f"[Uploader] Output directory does not exist: {OUTPUT_DIR}")
        print("[Uploader] All done.")
        return

    uploaded = _load_uploaded_log()
    print(f"[Uploader] {len(uploaded)} file(s) already uploaded (skipping).")

    all_pending = _get_pending_videos(uploaded)

    if not all_pending:
        print("[Uploader] No new video files found.")
        run_audit()
        print("[Uploader] All done.")
        return

    # Apply optional hard cap from settings
    if UPLOAD_LIMIT and UPLOAD_LIMIT > 0:
        all_pending = all_pending[:UPLOAD_LIMIT]

    total = len(all_pending)
    print(f"[Uploader] {total} file(s) to upload across batches of {BATCH_SIZE}.")

    # Split into batches
    batches = [all_pending[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    for batch_num, batch in enumerate(batches, 1):
        batch_start = time.time()
        print(f"\n[Uploader] ── Batch {batch_num}/{len(batches)} ({len(batch)} file(s)) ──")
        for v in batch:
            print(f"   - {v.name}")

        if not navigate_to_shorts(page):
            print("[Uploader] CRITICAL: Navigation failed. Aborting.")
            break

        if not _click_create_button(page):
            break
        time.sleep(1)

        if not _click_upload_videos_option(page):
            break
        time.sleep(1)

        if not _attach_files(page, batch):
            break

        # ── Wait 5s then close the dialog ────────────────────────────────────
        print(f"[Uploader] Waiting {POST_ATTACH_WAIT_S}s before closing dialog...")
        page.wait_for_timeout(POST_ATTACH_WAIT_S * 1000)
        _close_upload_dialog(page)

        # ── Wait for YouTube to process uploads in the background ─────────────
        # Cap at either POST_CLOSE_WAIT_S (3 min) or remaining hard-cap time.
        elapsed_so_far = int(time.time() - batch_start)
        budget = max(0, BATCH_HARD_CAP_S - elapsed_so_far)
        wait_time = min(POST_CLOSE_WAIT_S, budget)

        if wait_time > 0:
            _wait_with_progress(
                f"Batch {batch_num} background processing",
                wait_time,
                page,
            )
        else:
            print(f"[Uploader] Hard cap reached for batch {batch_num} — moving on.")

        # ── Log the batch ─────────────────────────────────────────────────────
        for v in batch:
            uploaded.add(v.name)
        _save_uploaded_log(uploaded)

        batch_elapsed = int(time.time() - batch_start)
        print(f"[Uploader] Batch {batch_num} logged. ({batch_elapsed}s total)")

        if batch_num < len(batches):
            print("[Uploader] Waiting 5s before next batch...")
            time.sleep(5)

    print("\n[Uploader] All done.")