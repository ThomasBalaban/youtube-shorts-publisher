"""
Analyze Draft YouTube Shorts (Strictly Drafts/Unlisted)
This script fetches your own uploaded videos, IGNORING Scheduled content,
and analyzes only true drafts or unlisted videos with Gemini.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from settings import GEMINI_API_KEY
import re
import random


# Third-party imports
try:
    from googleapiclient.discovery import build # type: ignore
    from googleapiclient.errors import HttpError # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow # type: ignore
    from google.auth.transport.requests import Request # type: ignore
    from google.oauth2.credentials import Credentials # type: ignore
    import yt_dlp # type: ignore
    import google.generativeai as genai # type: ignore
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 yt-dlp google-generativeai")
    sys.exit(1)

# Configuration
CLIENT_SECRETS_FILE = "client_secret.json"
COOKIES_FILE = "cookies.txt"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# -----------------------------------------------------------------------------
# Script Settings
# -----------------------------------------------------------------------------
GEMINI_API_KEY = GEMINI_API_KEY
IGNORE_ANALYZED_TITLES = True
# -----------------------------------------------------------------------------

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


class DraftShortsAnalyzer:
    def __init__(self, output_file="draft_analysis.json", max_videos=50):
        self.output_file = output_file
        self.max_videos = max_videos
        self.temp_dir = Path("temp_draft_download")
        self.temp_dir.mkdir(exist_ok=True)
        self.youtube = self._authenticate_youtube()
        genai.configure(api_key=GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel('models/gemini-2.5-pro')

    def _authenticate_youtube(self):
        creds = None
        token_path = 'token.json'
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CLIENT_SECRETS_FILE):
                    print(f"ERROR: {CLIENT_SECRETS_FILE} not found.")
                    sys.exit(1)
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        return build('youtube', 'v3', credentials=creds)

    def get_uploads_playlist_id(self):
        response = self.youtube.channels().list(part="contentDetails", mine=True).execute()
        if not response['items']:
            raise Exception("No channel found for authenticated user.")
        return response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    def fetch_my_drafts(self):
        print(f"Fetching up to {self.max_videos} Draft/Unlisted shorts (via Search)...")
        draft_shorts = []
        next_page_token = None
        page_count = 0
        MAX_PAGES = 10
        try:
            while len(draft_shorts) < self.max_videos and page_count < MAX_PAGES:
                page_count += 1
                request = self.youtube.search().list(
                    part="id", forMine=True, type="video",
                    maxResults=50, order="date", pageToken=next_page_token
                )
                response = request.execute()
                video_ids = [item['id']['videoId'] for item in response.get('items', [])]
                if not video_ids:
                    print("No more videos found.")
                    break
                videos_response = self.youtube.videos().list(
                    part='snippet,contentDetails,status',
                    id=','.join(video_ids)
                ).execute()
                for video in videos_response.get('items', []):
                    if len(draft_shorts) >= self.max_videos:
                        break
                    duration = video['contentDetails']['duration']
                    privacy = video['status']['privacyStatus']
                    upload_status = video['status'].get('uploadStatus')
                    publish_at = video['status'].get('publishAt')
                    title = video['snippet']['title']
                    is_short = self._is_short_duration(duration)
                    is_scheduled = publish_at is not None
                    if not is_short:
                        continue
                    if privacy == 'public' or is_scheduled:
                        continue
                    if privacy in ['private', 'unlisted']:
                        draft_shorts.append({
                            'video_id': video['id'],
                            'title': title,
                            'status_label': f"{privacy.capitalize()} ({upload_status})",
                            'published_date': video['snippet']['publishedAt'],
                            'url': f"https://www.youtube.com/watch?v={video['id']}"
                        })
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            if not draft_shorts:
                print(f"Checked {page_count} pages but found no eligible Draft Shorts.")
            else:
                print(f"Found {len(draft_shorts)} shorts to analyze.")
            return draft_shorts
        except HttpError as e:
            print(f"YouTube API Error: {e}")
            return draft_shorts

    def _is_short_duration(self, duration_str):
        if 'H' in duration_str: return False
        duration = duration_str.replace('PT', '')
        minutes = 0
        seconds = 0
        if 'M' in duration:
            parts = duration.split('M')
            minutes = int(parts[0])
            if len(parts) > 1 and 'S' in parts[1]:
                seconds = int(parts[1].replace('S', ''))
        elif 'S' in duration:
            seconds = int(duration.replace('S', ''))
        return (minutes * 60 + seconds) <= 61

    def download_private_video(self, video_url, video_id):
        if not os.path.exists(COOKIES_FILE):
            raise FileNotFoundError(f"Missing {COOKIES_FILE}. Cannot download private videos without cookies.")
        output_path = self.temp_dir / f"{video_id}.mp4"
        ydl_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': str(output_path),
            'quiet': True,
            'cookiefile': COOKIES_FILE,
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            return output_path
        except Exception as e:
            print(f"Error downloading {video_id} (Check your cookies.txt?): {e}")
            return None

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
        print(f"  Uploading to Gemini (Title: {current_title})...")
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
            for bad_word, safe_word in sorted(SAFE_WORD_MAPPING.items(), key=lambda x: -len(x[0])):
                pattern = re.compile(r'\b' + re.escape(bad_word) + r'\b', re.IGNORECASE)
                data['new_title'] = pattern.sub(safe_word, data['new_title'])

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
        print("--- Draft Shorts Analyzer ---")
        results = []
        analyzed_titles = set()
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    file_content = json.load(f)
                    if isinstance(file_content, list):
                        results = file_content
                        for item in results:
                            if 'title' in item:
                                analyzed_titles.add(item['title'])
                            if 'new_title' in item:
                                analyzed_titles.add(item['new_title'])
                print(f"Loaded {len(results)} existing analyses (checking against {len(analyzed_titles)} unique titles).")
            except (json.JSONDecodeError, IOError):
                results = []

        drafts = self.fetch_my_drafts()
        for i, draft in enumerate(drafts, 1):
            if IGNORE_ANALYZED_TITLES and draft['title'] in analyzed_titles:
                print(f"\n[{i}/{len(drafts)}] Skipping (Already Analyzed): {draft['title']}")
                continue
            print(f"\n[{i}/{len(drafts)}] Analyzing: {draft['title']}")
            video_path = self.download_private_video(draft['url'], draft['video_id'])
            if video_path and video_path.exists():
                analysis_dict = self.analyze_with_gemini(video_path, draft['title'])
                if "error" not in analysis_dict:
                    print("-" * 40)
                    print(f"Game:  {analysis_dict.get('game_name')}")
                    print(f"Score: {analysis_dict.get('virality')}/10  — {analysis_dict.get('virality_reasoning')}")
                    print(f"Title: {analysis_dict.get('new_title')}")
                    print("-" * 40)
                    analyzed_titles.add(analysis_dict.get('title'))
                    if analysis_dict.get('new_title'):
                        analyzed_titles.add(analysis_dict.get('new_title'))
                else:
                    print(f"Analysis Failed: {analysis_dict['error']}")
                results.append(analysis_dict)
                video_path.unlink()
                with open(self.output_file, 'w') as f:
                    json.dump(results, f, indent=2)

    def cleanup(self):
        if self.temp_dir.exists():
            for file in self.temp_dir.glob('*'):
                file.unlink()
            self.temp_dir.rmdir()


if __name__ == "__main__":
    analyzer = DraftShortsAnalyzer()
    try:
        analyzer.run()
    finally:
        analyzer.cleanup()