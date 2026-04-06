import os
import time
import json
import random
import re
from pathlib import Path
from playwright.sync_api import Page
from config.navigation import navigate_to_shorts
import google.generativeai as genai
from settings import GEMINI_API_KEY

# ── Safe word mapping ─────────────────────────────────────────────────────────
SAFE_WORD_MAPPING = {
    # Suggestive / double-meaning phrases
    "suck me": "GET ME",
    "sucked me": "GOT ME",
    "sucking me": "PULLING ME",
    "blow me": "BLEW IT",
    "choke me": "CAUGHT ME",
    "ride me": "HIT ME",
    "mount me": "CLIMB ME",
    # Profanity (single words)
    "dick": "MAN PARTS",
    "dicks": "MAN PARTS",
    "penis": "MAN PARTS",
    "cock": "ROOSTER",
    "fuck": "EFF",
    "fucking": "FREAKING",
    "shit": "CRAP",
    "bitch": "DUDE",
    "ass": "BUTT",
    "damn": "DANG",
    "hell": "HECK",
    "piss": "DRIP",
    "wtf": "WHAT",
    "stfu": "BE QUIET",
}


def _limit_caps(title: str, max_caps_words: int = 3) -> str:
    words = title.split()
    caps_used = 0
    result = []
    for word in words:
        core = re.sub(r"[^A-Za-z]", "", word)
        is_all_caps = core.isupper() and len(core) > 1
        if is_all_caps:
            if caps_used < max_caps_words:
                result.append(word)
                caps_used += 1
            else:
                result.append(word.capitalize())
        else:
            result.append(word)
    return " ".join(result)


class PlaywrightAnalyzer:
    def __init__(self, page: Page):
        self.page = page
        self.output_file = "draft_analysis.json"
        self.failed_file = "failed_shorts_data.json"
        self.temp_dir = Path(os.getcwd()) / "temp_draft_download"
        self.temp_dir.mkdir(exist_ok=True)
        genai.configure(api_key=GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel('models/gemini-2.5-pro')

    def _load_analyzed_titles(self):
        analyzed = set()
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        if 'title' in item: analyzed.add(item['title'])
                        if 'new_title' in item: analyzed.add(item['new_title'])
            except:
                pass
        return analyzed

    def _load_failed_titles(self):
        failed = set()
        if os.path.exists(self.failed_file):
            try:
                with open(self.failed_file, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        if 'title' in item: failed.add(item['title'])
            except:
                pass
        return failed

    def _save_failure(self, title, error_msg):
        current_data = []
        if os.path.exists(self.failed_file):
            try:
                with open(self.failed_file, 'r') as f:
                    current_data = json.load(f)
            except:
                pass
        current_data.append({
            "title": title,
            "error": str(error_msg),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        with open(self.failed_file, 'w') as f:
            json.dump(current_data, f, indent=2)

    def _save_result(self, result):
        current_data = []
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    current_data = json.load(f)
            except:
                pass
        current_data.append(result)
        with open(self.output_file, 'w') as f:
            json.dump(current_data, f, indent=2)

    def _pass_one_describe(self, video_file) -> str:
        """
        Pass 1: Watch the video and produce a free-form analytical description.
        No JSON, no constraints — just accurate observation.
        """
        prompt = """
        Watch this video carefully. Your job is purely observation — no formatting, no JSON.

        Write a short analytical breakdown covering:
        - What game is being played? If you are certain, name it. If you have any doubt at all,
          write Unknown. Do not guess. Do not go with your best impression. The cost of a wrong
          game name is higher than the cost of saying Unknown, so when in doubt, Unknown wins.
        - What is the key moment or punchline of the clip? Describe it precisely.
        - How does the streamer react? (e.g. screams, laughs, goes quiet, swears, etc.)
        - What makes this clip funny, scary, or satisfying — or what stops it from being any of those things?
        - Is there any chat interaction or on-screen text worth noting?
        - On a gut level, would a stranger who has never seen this streamer find this entertaining? Why or why not?

        Be honest and specific. Do not pad or hype. If the clip is slow or boring, say so.
        """
        print("  [Pass 1] Describing video...")
        response = self.gemini_model.generate_content([video_file, prompt])
        description = response.text.strip()
        print(f"  [Pass 1] Done. ({len(description)} chars)")
        return description

    def _pass_two_metadata(self, description: str, current_title: str) -> dict:
        """
        Pass 2: Convert the Pass 1 description into structured metadata JSON.
        Text-only — video is not re-uploaded.
        """
        prompt = f"""
        You are an expert YouTube Shorts strategist. A video analyst has already watched a clip
        and written the following breakdown:

        --- ANALYST NOTES ---
        {description}
        --- END NOTES ---

        The clip's current working title is: "{current_title}"

        Using ONLY the analyst notes above, return a valid JSON object with these fields:

        1. "description": A short, vivid summary of what happens (1-2 sentences).

        2. "virality": An integer score from 1-10. Use this exact discipline:
           - START at 5. Every clip is average until proven otherwise.
           - To reach 6: one clear positive signal (a funny moment, a good reaction, a satisfying payoff).
           - To reach 7: two positive signals AND the moment is self-explanatory to someone who doesn't play games.
           - To reach 8: the clip would make a non-gamer laugh or gasp if it showed up on their feed.
             It needs ALL THREE: a punchline so clean it works without context, a strong audible reaction,
             AND something that makes it rewatchable. All three required, no exceptions.
           - 9-10: Would trend outside gaming entirely. Do not use.
           - DISTRIBUTION CHECK: Scores must vary. Most gaming highlights land at 6-7. An 8 should feel
             rare — if you are giving everything an 8, you are not being critical enough. When in doubt,
             go one point lower.

        3. "virality_reasoning": One sentence. Name the specific signal(s) that moved the score up OR
           the specific weakness(es) that held it down.

        4. "game_name": Take this directly from the analyst notes. If the notes express any uncertainty
           or say "Unknown", return "Unknown". Do not infer or guess.

        5. "is_fnaf_game": Boolean. True ONLY if the game is Five Nights at Freddy's or a direct FNAF fan-game.

        6. "new_title": A click-worthy title (max 60 chars).
           - STYLE: Punchy, conversational. Written the way a person naturally talks.
           - CAPS RULE: AT MOST 2-3 key words in ALL CAPS. Do NOT write full sentences in caps.
           - GOOD: "My Dog JUMPED ME Mid-Fight!", "He Actually Shot Himself?!"
           - BAD: "MY DOG JUMPED ME MID FIGHT!", "HE SHOT HIMSELF!?"
           - FLAGGING: Avoid phrasing that sounds sexual, violent toward real people, or drug-related.
           - One emoji allowed at the end if it genuinely fits.

        7. "youtube_description": 1-2 sentences. Enthusiastic, first-person, story-driven.
           - NO: "Watch as...", "In this video..."
           - YES: "I literally broke the physics engine!", "My dog picked the worst possible moment."
           - Include the game name naturally if known.

        8. "hashtags": Max 3. If is_fnaf_game is true, first hashtag MUST be "#fnaf".

        9. "tags": Comma-separated. Under 250 characters total.

        Return pure JSON only.
        """
        print("  [Pass 2] Generating metadata...")
        response = self.gemini_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        print("  [Pass 2] Done.")
        return data

    def analyze_with_gemini(self, video_path, current_title):
        print(f"   [Gemini] Uploading {current_title}...")
        video_file = genai.upload_file(path=str(video_path))
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)
        try:
            description = self._pass_one_describe(video_file)
            genai.delete_file(video_file.name)
            data = self._pass_two_metadata(description, current_title)

            # 1. Emoji removal (65% chance)
            if random.random() < 0.65:
                data['new_title'] = re.sub(r'[^\x00-\x7F]+', '', data['new_title']).strip()

            # 2. Safety filter — phrases first, then single words
            for bad, safe in sorted(SAFE_WORD_MAPPING.items(), key=lambda x: -len(x[0])):
                pattern = re.compile(r'\b' + re.escape(bad) + r'\b', re.IGNORECASE)
                data['new_title'] = pattern.sub(safe, data['new_title'])

            # 3. Caps limiter
            data['new_title'] = _limit_caps(data['new_title'], max_caps_words=3)

            # 4. Restore original title key
            data['title'] = current_title

            # 5. FNAF hashtag safety
            if data.get('is_fnaf_game', False):
                tags = data.get('hashtags', [])
                if not tags or tags[0].lower() != '#fnaf':
                    tags = [t for t in tags if t.lower() != '#fnaf']
                    tags.insert(0, '#fnaf')
                    data['hashtags'] = tags[:3]

            return data
        except Exception as e:
            print(f"  Gemini Error: {e}")
            try:
                genai.delete_file(video_file.name)
            except:
                pass
            return {"title": current_title, "error": str(e)}

    def run(self):
        print("\n=== MODE: PLAYWRIGHT ANALYZER (Drafts Only) ===")
        analyzed_titles = self._load_analyzed_titles()
        failed_titles = self._load_failed_titles()
        print(f">> Loaded {len(analyzed_titles)} previously analyzed titles.")
        print(f">> Loaded {len(failed_titles)} previously failed titles (will be skipped).")

        while True:
            rows_found = False
            for attempt in range(3):
                try:
                    self.page.wait_for_selector("ytcp-video-row", state="visible", timeout=6000)
                    rows_found = True
                    break
                except:
                    print(f">> Waiting for video rows... (Attempt {attempt+1}/3)")
                    time.sleep(2)

            if not rows_found:
                print(">> No video rows found after retries. Checking navigation...")
                navigate_to_shorts(self.page)
                continue

            rows = self.page.locator("ytcp-video-row").all()
            processed_in_pass = 0

            for row in rows:
                try:
                    visibility_cell = row.locator(".tablecell-visibility")
                    status_text = visibility_cell.inner_text().strip()
                    title_el = row.locator("#video-title").first
                    if title_el.count() == 0:
                        continue
                    title = title_el.inner_text().strip()
                    if "Draft" not in status_text:
                        continue
                    if title in analyzed_titles or title in failed_titles:
                        continue

                    print(f"\n>> Processing Draft: {title}")
                    row.evaluate("element => element.scrollIntoView({ block: 'center', behavior: 'instant' })")
                    time.sleep(0.5)
                    row.hover()
                    time.sleep(0.5)

                    options_btn = row.locator("ytcp-icon-button[aria-label='Options']").first
                    opt_box = options_btn.bounding_box()
                    if not opt_box:
                        print("   [Warning] Options button not visible. Skipping.")
                        continue

                    opt_x = opt_box["x"] + opt_box["width"] / 2
                    opt_y = opt_box["y"] + opt_box["height"] / 2
                    self.page.mouse.move(opt_x, opt_y, steps=10)
                    time.sleep(1.0)
                    self.page.mouse.click(opt_x, opt_y)

                    download_info = None
                    try:
                        time.sleep(1.0)
                        active_dialog = self.page.locator("tp-yt-paper-dialog").filter(
                            has_not=self.page.locator("[style*='display: none']")
                        ).filter(
                            has_not=self.page.locator("[style*='display:none']")
                        ).locator("visible=true").first
                        download_link = active_dialog.locator("a[href*='download']").filter(has_text="Download").first
                        download_link.wait_for(state="visible", timeout=5000)
                        print("   [UI] Clicking Download...")
                        try:
                            with self.page.expect_download(timeout=5000) as download_info_ctx:
                                download_link.click()
                            download_info = download_info_ctx.value
                        except Exception as e:
                            print(f"   [Error] Download did not start: {e}")
                            self._save_failure(title, f"Download timeout/fail: {e}")
                            failed_titles.add(title)
                            self.page.keyboard.press("Escape")
                            time.sleep(0.5)
                            shorts_tab = self.page.locator("#video-list-shorts-tab[aria-selected='true']")
                            if shorts_tab.is_visible():
                                self.page.mouse.move(0, 0)
                                self.page.mouse.click(0, 0)
                                continue
                            else:
                                navigate_to_shorts(self.page)
                                break
                    except Exception as e:
                        print(f"   [Error] Menu/UI navigation failed: {e}")
                        self._save_failure(title, f"Menu/UI Error: {e}")
                        failed_titles.add(title)
                        self.page.keyboard.press("Escape")
                        time.sleep(0.5)
                        self.page.mouse.move(0, 0)
                        self.page.mouse.click(0, 0)
                        continue

                    if download_info:
                        save_path = self.temp_dir / f"{title[:10]}_{int(time.time())}.mp4"
                        print(f"   [Download] Saving to {save_path}...")
                        download_info.save_as(save_path)
                        self.page.mouse.move(0, 0)
                        self.page.mouse.click(0, 0)
                        time.sleep(0.5)

                        result = self.analyze_with_gemini(save_path, title)
                        if "error" not in result:
                            print("-" * 30)
                            print(f"TITLE: {result.get('new_title')}")
                            print(f"SCORE: {result.get('virality')}/10  — {result.get('virality_reasoning')}")
                            print("-" * 30)
                            self._save_result(result)
                            analyzed_titles.add(title)
                        else:
                            print(f"   [Error] Gemini failed: {result['error']}")

                        if save_path.exists():
                            os.remove(save_path)

                    processed_in_pass += 1

                except Exception as e:
                    print(f"   [Warning] Skipped row due to error: {e}")
                    self.page.keyboard.press("Escape")
                    self.page.mouse.move(0, 0)
                    self.page.mouse.click(0, 0)
                    continue

            if processed_in_pass == 0:
                print(">> No new drafts found on this page. Checking pagination...")
                next_btn = self.page.locator("#navigate-after")
                if next_btn.is_visible() and next_btn.get_attribute("aria-disabled") != "true":
                    next_btn.click()
                    print(">> Navigating to next page... (Waiting 5s)")
                    time.sleep(5)
                else:
                    print(">> Done. All drafts analyzed.")
                    break