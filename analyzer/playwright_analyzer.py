import os
import time
import json
import random
import re
from pathlib import Path
from playwright.sync_api import Page
import google.generativeai as genai
from settings import GEMINI_API_KEY

# Copying Safe Word Mapping from your original script
SAFE_WORD_MAPPING = {
    "dick": "MAN PARTS", "dicks": "MAN PARTS", "penis": "MAN PARTS",
    "cock": "ROOSTER", "fuck": "EFF", "fucking": "FREAKING",
    "shit": "CRAP", "bitch": "DUDE", "ass": "BUTT"
}

class PlaywrightAnalyzer:
    def __init__(self, page: Page):
        self.page = page
        self.output_file = "draft_analysis.json"
        # We use a specific temp folder to keep your Downloads clean
        self.temp_dir = Path(os.getcwd()) / "temp_draft_download"
        self.temp_dir.mkdir(exist_ok=True)
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel('models/gemini-2.5-flash')

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

    def analyze_with_gemini(self, video_path, current_title):
        print(f"   [Gemini] Uploading {current_title}...")
        video_file = genai.upload_file(path=str(video_path))
        
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        prompt = f"""
            You are an expert YouTube Shorts strategist and metadata specialist. 
            Analyze the uploaded video and the current title: "{current_title}".

            Return a valid JSON object with the following fields:

            1. "description": A short, vivid summary of what happens in the video. 
            2. "virality": A score from 1-10 (integer). BE EXTREMELY STRICT. 
            - 1-4: Boring, confusing, or bad quality.
            - 5-6: Average, watchable but not shareable. 
            - 7-8: Good hook, funny, or satisfying.
            - 9-10: Viral masterpiece.
            - A lot of videos should be 5-6. Do not inflate scores.
            3. "virality_reasoning": A short explanation of why it will/won't perform well.
            4. "game_name": The name of the game being played. 
            - CRITICAL: If you are not >95% confident, or if it looks like a generic game, return "Unknown". 
            - DO NOT GUESS. It is better to return "Unknown" than the wrong game.
            5. "is_fnaf_game": Boolean (true/false).
            - Set to TRUE ONLY if the game is clearly "Five Nights at Freddy's" OR a fan-game inspired by it.
            - BE STRICT: Generic horror is FALSE. FNAF-style mechanics are TRUE.
            6. "new_title": A click-worthy title (max 60 chars). 
            - STYLE: High energy, punchy. 
            - FORMATTING: Do NOT be afraid to use ALL CAPS for emphasis (e.g., "HE FOUND ME!!" is better than "He found me").
            - You MAY include a single emoji at the end if it seems like it would help.
            7. "youtube_description": A short, engaging caption (1-2 sentences).
            - STYLE: Enthusiastic, story-driven, or funny observation. Use first-person ("I", "Me") if it involves a player reaction.
            - NO: "Watch as...", "In this video...", "Here we see..."
            - YES: "I literally broke the physics engine!", "This is why you never dig straight down in Minecraft.", "WOWWWW A SIMPLE SNOWBALL LAUNCHES THIS DUDE!!"
            - SEO: Include the game name naturally IF KNOWN.
            8. "hashtags": Max 3 hashtags. 
            - CRITICAL: If "is_fnaf_game" is true, the FIRST hashtag MUST be "#fnaf".
            - Otherwise, choose ones to help virality (e.g., #Gaming, #Horror).
            9. "tags": Comma-separated tags to help virality (e.g., "horror, funny moments"). MUST be under 250 characters total.

            Ensure the output is pure JSON.
        """
        
        try:
            response = self.gemini_model.generate_content(
                [video_file, prompt],
                generation_config={"response_mime_type": "application/json"}
            )
            genai.delete_file(video_file.name)
            data = json.loads(response.text)
            
            # Post-processing (RNG Emoji Removal + Safety Filter)
            if random.random() < 0.65:
                data['new_title'] = re.sub(r'[^\x00-\x7F]+', '', data['new_title']).strip()
            
            for bad, safe in SAFE_WORD_MAPPING.items():
                pattern = re.compile(r'\b' + re.escape(bad) + r'\b', re.IGNORECASE)
                data['new_title'] = pattern.sub(safe, data['new_title'])
                
            data['title'] = current_title
            
            # FNAF Safety
            if data.get('is_fnaf_game', False):
                tags = data.get('hashtags', [])
                if not tags or tags[0].lower() != '#fnaf':
                    tags = [t for t in tags if t.lower() != '#fnaf']
                    tags.insert(0, '#fnaf')
                    data['hashtags'] = tags[:3]
                    
            return data
        except Exception as e:
            return {"title": current_title, "error": str(e)}

    def run(self):
        print("\n=== MODE: PLAYWRIGHT ANALYZER ===")
        
        # 1. Setup Filter
        analyzed_titles = self._load_analyzed_titles()
        
        print(f">> Loaded {len(analyzed_titles)} previously analyzed titles.")

        while True:
            # Refresh rows
            self.page.wait_for_selector("ytcp-video-row", state="visible")
            rows = self.page.locator("ytcp-video-row").all()
            
            processed_in_pass = 0
            
            for row in rows:
                try:
                    title_el = row.locator("#video-title").first
                    if not title_el.is_visible(): continue
                    title = title_el.inner_text().strip()
                    
                    if title in analyzed_titles:
                        continue
                        
                    print(f"\n>> Processing: {title}")
                    
                    # --- DOWNLOAD SEQUENCE ---
                    # 1. Hover to trigger 'is-highlighted' and reveal options
                    row.hover()
                    time.sleep(0.5)
                    
                    # 2. Find and Click Options (Three dots)
                    # The button usually has aria-label="Options"
                    options_btn = row.locator("ytcp-icon-button[aria-label='Options']").first
                    options_btn.click()
                    
                    # 3. Wait for the menu to appear
                    # 4. Click the specific Download element user requested
                    download_selector = "yt-formatted-string.item-text.main-text.style-scope.ytcp-text-menu:text('Download')"
                    
                    # Setup Download Listener
                    with self.page.expect_download() as download_info:
                        self.page.locator(download_selector).click()
                        
                    download = download_info.value
                    save_path = self.temp_dir / f"{title[:10]}_{int(time.time())}.mp4"
                    
                    print(f"   [Download] Saving to {save_path}...")
                    download.save_as(save_path)
                    
                    # --- GEMINI ANALYSIS ---
                    result = self.analyze_with_gemini(save_path, title)
                    
                    if "error" not in result:
                        print("-" * 30)
                        print(f"NEW TITLE: {result.get('new_title')}")
                        print(f"SCORE: {result.get('virality')}/10")
                        print("-" * 30)
                        self._save_result(result)
                        analyzed_titles.add(title)
                    else:
                        print(f"   [Error] Gemini failed: {result['error']}")

                    # --- CLEANUP ---
                    if save_path.exists():
                        os.remove(save_path)
                    
                    processed_in_pass += 1
                    # Clean UI (Click away to close any lingering menus)
                    self.page.mouse.move(0, 0)
                    self.page.mouse.click(0, 0)
                    time.sleep(1)

                except Exception as e:
                    print(f"   [Warning] Skipped row due to error: {e}")
                    continue
            
            if processed_in_pass == 0:
                print(">> No new drafts found on this page. Checking pagination...")
                next_btn = self.page.locator("#navigate-after")
                if next_btn.is_visible() and next_btn.get_attribute("aria-disabled") != "true":
                    next_btn.click()
                    time.sleep(3)
                else:
                    print(">> Done. All drafts analyzed.")
                    break