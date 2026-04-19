import os
import time
import json
import random
import re
from pathlib import Path
from playwright.sync_api import Page
from config.navigation import navigate_to_shorts
import google.generativeai as genai
from settings import (
    GEMINI_API_KEY,
    GEMINI_MODEL_OBSERVE,
    GEMINI_MODEL_CRITIQUE,
    GEMINI_MODEL_METADATA,
)

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


def _extract_json(raw_text: str) -> dict:
    """
    Robustly parse a JSON object from a Gemini response.

    Handles common failure modes:
    - Plain json.loads succeeds (happy path)
    - Markdown fences around the JSON (```json ... ```)
    - Trailing explanation text after the closing brace ("Extra data" error)
    - Leading preamble before the opening brace

    Raises ValueError with the raw text snippet if nothing parseable is found.
    """
    text = raw_text.strip()

    # Fast path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # Brace-walk: find the first { and match its closing brace, ignoring braces inside strings
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in response. Raw start: {text[:200]!r}")

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Matched brace-range failed to parse: {e}. "
                        f"Candidate start: {candidate[:200]!r}"
                    )

    raise ValueError(f"Unbalanced braces in response. Raw start: {text[:200]!r}")


class PlaywrightAnalyzer:
    def __init__(self, page: Page):
        self.page = page
        self.output_file = "draft_analysis.json"
        self.failed_file = "failed_shorts_data.json"
        self.temp_dir = Path(os.getcwd()) / "temp_draft_download"
        self.temp_dir.mkdir(exist_ok=True)
        genai.configure(api_key=GEMINI_API_KEY)
        # Three models — split by task per the pipeline design
        self.model_observe  = genai.GenerativeModel(GEMINI_MODEL_OBSERVE)
        self.model_critique = genai.GenerativeModel(GEMINI_MODEL_CRITIQUE)
        self.model_metadata = genai.GenerativeModel(GEMINI_MODEL_METADATA)

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

    def _pass_one_observe(self, video_file) -> str:
        """
        Pass 1: Watch the video and produce hook-focused observation notes.
        No game guessing — only a FNAF-or-not check.
        """
        prompt = """
        Watch this video carefully. Your job is purely observation — no formatting, no JSON.
        A YouTube Short lives or dies on ONE sharp moment. Your job is to identify it.

        Write a short analytical breakdown covering these points, in order:

        1. THE HOOK. What is the single most surprising, funny, satisfying, or rewatchable
           moment in this clip? Pinpoint it. If possible, quote exactly what's said at that
           moment. If there's no clear hook, say so directly — don't invent one.

        2. THE REACTION. At the moment of the hook, how does the streamer react? Be specific:
           "screams, drops the controller, laughs hysterically for 3 seconds" is useful.
           "reacts" is not.

        3. CONTEXT FOR A STRANGER. Does the hook work for someone who has never watched this
           streamer and doesn't know the game? If yes, explain why. If no, explain what would
           be missing for them.

        4. REWATCH VALUE. Is there a reason to watch this clip a second time? (A detail that
           only lands on replay, an unbelievable sequence, a perfect piece of timing?) Or is
           this a once-and-done clip?

        5. FNAF CHECK. Is this clip from Five Nights at Freddy's or a direct FNAF fan-game?
           Answer YES only if you see unmistakable FNAF visual signatures: the animatronic
           characters (Freddy, Bonnie, Chica, Foxy, Springtrap, etc.), the security office
           setup with cameras and doors, or the distinctive FNAF art style. Otherwise answer
           NO. Do NOT try to identify any other game — ignore all non-FNAF game identification.

        6. ON-SCREEN / CHAT. Is there any chat message, on-screen text, or subtitle worth
           noting? If not, skip.

        Be honest and specific. If the clip is slow, boring, or doesn't have a clear hook,
        say so plainly. A weak clip getting called weak here saves us from a bad title later.
        """
        print("  [Pass 1 / Observe] Watching video and identifying hook...")
        response = self.model_observe.generate_content([video_file, prompt])
        notes = response.text.strip()
        print(f"  [Pass 1 / Observe] Done. ({len(notes)} chars)")
        return notes

    def _pass_one_five_critique(self, observation_notes: str) -> str:
        """
        Pass 1.5: Self-critique and rewrite. Text-only (no video re-upload).
        Forces the hook to be specific and tight before metadata generation.
        """
        prompt = f"""
        You are a ruthless editor. Another analyst just watched a YouTube Short and wrote these
        notes:

        --- ORIGINAL NOTES ---
        {observation_notes}
        --- END NOTES ---

        Your job: critique these notes honestly, then rewrite them tighter and sharper.

        CHECK FOR THESE WEAKNESSES:
        - Is the HOOK specific enough? "The streamer laughs" is vague. "The streamer laughs
          for 4 seconds straight after realizing the ghost ate their sandwich" is specific.
          If the hook is vague, sharpen it or say the clip genuinely lacks a clear hook.
        - Is the analyst padding or hyping? If they say something is "hilarious" or
          "insane" without proof, strip the hype and keep only what actually happened.
        - Is the stranger-context answer honest? Many gaming clips only work for viewers
          who know the game. Don't let the analyst pretend otherwise.
        - Is rewatch value real, or invented to fill the section?

        OUTPUT FORMAT: Write the REWRITTEN notes using the same 6-section structure
        (HOOK, REACTION, CONTEXT FOR A STRANGER, REWATCH VALUE, FNAF CHECK, ON-SCREEN / CHAT).
        No preamble, no "here is my critique" — just the clean rewritten notes.

        If the clip is genuinely weak, the rewritten notes should reflect that. A weak clip
        honestly described is more useful than a mediocre clip dressed up as great.
        """
        print("  [Pass 1.5 / Critique] Tightening observation notes...")
        response = self.model_critique.generate_content(prompt)
        refined = response.text.strip()
        print(f"  [Pass 1.5 / Critique] Done. ({len(refined)} chars)")
        return refined

    def _pass_two_metadata(self, refined_notes: str, current_title: str) -> dict:
        """
        Pass 2: Convert refined notes into structured metadata JSON.
        Text-only — video is not re-uploaded.
        """
        prompt = f"""
        You are an expert YouTube Shorts strategist. A video analyst watched a clip and
        then an editor refined the notes. Here are the final refined notes:

        --- REFINED NOTES ---
        {refined_notes}
        --- END NOTES ---

        The clip's current working title is: "{current_title}"

        Using ONLY the refined notes above, return a valid JSON object with these fields:

        1. "description": A short, vivid summary of what happens (1-2 sentences). Do NOT
           name any specific game — describe the moment itself, not the game it's from.

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

           CALIBRATION EXAMPLES:
           - A clip where the streamer dies dramatically, screams, and laughs at themselves = 6-7.
             (One strong reaction, but the death only really lands if you play the game.)
           - A clip where the streamer reacts quietly to something only gamers would find funny = 4-5.
             (No strong reaction, no context for strangers.)
           - A clip where a pet jumps on the streamer mid-scream, causing visible chaos = 7-8.
             (Works without game context, strong reaction, memorable enough to rewatch.)
           - A clip that's just someone playing well with mild commentary = 4-5. No real hook.
           - A clip where the game physics breaks in a visually absurd way, streamer wheezes = 7.

        3. "virality_reasoning": One sentence. Name the specific signal(s) that moved the score up OR
           the specific weakness(es) that held it down.

        4. "rewatch_hook": One sentence. What SPECIFICALLY would make someone replay this clip?
           A detail they'd miss the first time, a perfect piece of timing, an unbelievable sequence?
           If there's no clear rewatch reason, write "None — once-and-done clip." An honest
           "None" here should usually correlate with a lower virality score.

        5. "is_fnaf_game": Boolean. Set TRUE if and only if the refined notes' FNAF CHECK section
           confirmed YES. Otherwise FALSE. Do NOT infer from any other signal.

        6. "title_candidates": An array of 3 title options, each ≤ 60 chars. Each must take a
           DIFFERENT angle on the clip:
           - Candidate A: REACTION-driven. Lead with the streamer's reaction or emotion.
             Example: "I Can't Stop Laughing at This"
           - Candidate B: QUESTION or CURIOSITY-driven. Make the viewer need to find out.
             Example: "Why Did The Game Do That?!"
           - Candidate C: PUNCHLINE-driven. Lead with the absurd or surprising thing itself.
             Example: "My Dog JUMPED ME Mid-Scream"

           RULES for every candidate:
           - STYLE: Punchy, conversational. Written the way a person naturally talks.
           - CAPS RULE: AT MOST 2-3 key words in ALL CAPS. Do NOT write full sentences in caps.
           - FLAGGING: Avoid phrasing that sounds sexual, violent toward real people, or drug-related.
           - One emoji allowed at the end if it genuinely fits.
           - Do NOT name a specific game in the title.

        7. "new_title": Pick the strongest of the three candidates. This is the one that gets used.

        8. "new_title_reasoning": One short sentence explaining why that candidate beats the other two.

        9. "youtube_description": 1-2 sentences. Enthusiastic, first-person, story-driven.
           - NO: "Watch as...", "In this video..."
           - YES: "I literally broke the physics engine!", "My dog picked the worst possible moment."
           - Do NOT name a specific game. Focus on the moment.

        10. "hashtags": Exactly 3 hashtags, chosen for DIVERSITY, not redundancy:
            - Hashtag #1 (BROAD DISCOVERY): A large, well-traveled tag. E.g., #gaming,
              #gamingshorts, #funnymoments, #horrorgaming.
            - Hashtag #2 (SPECIFIC GENRE/VIBE): Narrower and descriptive of the clip's
              flavor. E.g., #jumpscare, #coop, #speedrun, #ragemoment, #wholesome.
            - Hashtag #3 (TRENDING/FORMAT): A tag tied to Shorts format or current trends.
              E.g., #shorts, #clip, #viral, #fyp.
            Do NOT pick three near-duplicates. If is_fnaf_game is true, REPLACE hashtag #1
            with "#fnaf" (the others stay as-is).

        11. "tags": Comma-separated. Under 250 characters total. Mix of broad and specific.

        Return pure JSON only. Do not wrap in markdown fences. Do not add any
        explanation before or after the JSON object. Your entire response must
        be a single valid JSON object and nothing else.
        """
        print("  [Pass 2 / Metadata] Generating structured metadata...")

        last_error = None
        for attempt in range(2):
            response = self.model_metadata.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            raw = response.text or ""
            try:
                data = _extract_json(raw)
                print("  [Pass 2 / Metadata] Done.")
                return data
            except (ValueError, json.JSONDecodeError) as e:
                last_error = e
                if attempt == 0:
                    print(f"  [Pass 2 / Metadata] Parse failed ({e}). Retrying once...")
                    time.sleep(1)
                    continue
                # Second failure — log a preview to make debugging easy
                preview = raw[:300].replace("\n", " ")
                print(f"  [Pass 2 / Metadata] Parse failed twice. Raw preview: {preview!r}")

        raise ValueError(f"Pass 2 JSON parse failed after retry: {last_error}")

    def analyze_with_gemini(self, video_path, current_title):
        print(f"   [Gemini] Uploading {current_title}...")
        video_file = genai.upload_file(path=str(video_path))
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)
        try:
            # Pass 1: watch video, produce hook-focused notes
            raw_notes = self._pass_one_observe(video_file)
            # Video no longer needed after Pass 1
            genai.delete_file(video_file.name)

            # Pass 1.5: critique and tighten
            refined_notes = self._pass_one_five_critique(raw_notes)

            # Pass 2: structured metadata
            data = self._pass_two_metadata(refined_notes, current_title)

            # Stash the refined notes so you can audit the pipeline output
            data['refined_notes'] = refined_notes

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

            # 5. FNAF hashtag safety — ensure #fnaf is first if applicable
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
        print(f">> Observe model:  {GEMINI_MODEL_OBSERVE}")
        print(f">> Critique model: {GEMINI_MODEL_CRITIQUE}")
        print(f">> Metadata model: {GEMINI_MODEL_METADATA}")
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
                            print(f"FNAF?: {result.get('is_fnaf_game')}")
                            print(f"TITLE: {result.get('new_title')}")
                            print(f"  (why: {result.get('new_title_reasoning')})")
                            print(f"SCORE: {result.get('virality')}/10  — {result.get('virality_reasoning')}")
                            print(f"REWATCH: {result.get('rewatch_hook')}")
                            print("-" * 30)
                            self._save_result(result)
                            analyzed_titles.add(title)
                        else:
                            print(f"   [Error] Gemini failed: {result['error']}")
                            self._save_failure(title, f"Gemini Error: {result['error']}")
                            failed_titles.add(title)

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