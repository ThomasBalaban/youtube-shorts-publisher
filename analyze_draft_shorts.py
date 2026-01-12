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

class DraftShortsAnalyzer:
    def __init__(self, output_file="draft_analysis.json", max_videos=50):
        self.output_file = output_file
        self.max_videos = max_videos
        self.temp_dir = Path("temp_draft_download")
        self.temp_dir.mkdir(exist_ok=True)

        self.youtube = self._authenticate_youtube()
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel('models/gemini-2.5-flash')

    def _authenticate_youtube(self):
        """Authenticates the user via OAuth."""
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
        """Fetches videos, strictly ignoring Scheduled items."""
        print(f"Fetching up to {self.max_videos} Draft/Unlisted shorts (Ignoring Scheduled)...")
        
        try:
            uploads_playlist_id = self.get_uploads_playlist_id()
        except Exception as e:
            print(f"Error fetching channel details: {e}")
            return []

        draft_shorts = []
        next_page_token = None
        
        try:
            while len(draft_shorts) < self.max_videos:
                # Get videos from Uploads playlist
                request = self.youtube.playlistItems().list(
                    part="snippet",
                    playlistId=uploads_playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                response = request.execute()
                
                video_ids = [item['snippet']['resourceId']['videoId'] for item in response.get('items', [])]
                
                if not video_ids:
                    print("No more videos found.")
                    break

                # Get status details
                videos_response = self.youtube.videos().list(
                    part='snippet,contentDetails,status',
                    id=','.join(video_ids)
                ).execute()

                for video in videos_response.get('items', []):
                    if len(draft_shorts) >= self.max_videos:
                        break

                    duration = video['contentDetails']['duration']
                    privacy = video['status']['privacyStatus']
                    publish_at = video['status'].get('publishAt') # Exists only if scheduled
                    title = video['snippet']['title']
                    
                    is_short = self._is_short_duration(duration)
                    is_scheduled = publish_at is not None
                    is_hidden = privacy in ['private', 'unlisted']
                    
                    # LOGIC CHANGE HERE: Strict exclusion of scheduled videos
                    if is_short and is_hidden and not is_scheduled:
                        draft_shorts.append({
                            'video_id': video['id'],
                            'title': title,
                            'status_label': privacy.capitalize(), 
                            'published_date': video['snippet']['publishedAt'],
                            'url': f"https://www.youtube.com/watch?v={video['id']}"
                        })
                    elif is_scheduled:
                        # Optional: Print that we are skipping a scheduled video so you know it's working
                        # print(f"Skipping Scheduled: {title}")
                        pass

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                    
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

    def analyze_with_gemini(self, video_path, current_title):
        # We pass the current title so Gemini has context, but we will strictly 
        # use the API's title in the final object to ensure accuracy.
        
        SAFE_WORD_MAPPING = {
            "dick": "MAN PARTS",
            "dicks": "MAN PARTS",
            "penis": "MAN PARTS",
            "cock": "ROOSTER",
            "fuck": "EFF",
            "fucking": "FREAKING",
            "shit": "CRAP",
            "bitch": "DUDE",
            "ass": "BUTT"
        }
        
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
        
        print(f"  Uploading to Gemini (Title: {current_title})...")
        video_file = genai.upload_file(path=str(video_path))
        
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)
            
        try:
            response = self.gemini_model.generate_content(
                [video_file, prompt],
                generation_config={"response_mime_type": "application/json"}
            )
            
            genai.delete_file(video_file.name)
            data = json.loads(response.text)
            
            # --- 1. HANDLE RNG EMOJI REMOVAL ---
            # 65% chance to strip emojis from the title
            if random.random() < 0.65:
                # Regex matches any character NOT in the basic ASCII range (removes emojis)
                # and then .strip() cleans up any trailing spaces left behind.
                clean_title = re.sub(r'[^\x00-\x7F]+', '', data['new_title']).strip()
                data['new_title'] = clean_title

            # --- 2. SAFETY FILTER (Replace Bad Words) ---
            # We iterate over your mapping and replace matches, preserving case-insensitivity
            for bad_word, safe_word in SAFE_WORD_MAPPING.items():
                # \b ensures we match "dick" but not "predictable"
                # re.IGNORECASE ensures we catch "DICKS", "Dicks", and "dicks"
                pattern = re.compile(r'\b' + re.escape(bad_word) + r'\b', re.IGNORECASE)
                data['new_title'] = pattern.sub(safe_word, data['new_title'])

            # --- 3. RESTORE ORIGINAL DATA ---
            data['title'] = current_title 

            # --- 4. FNAF SAFETY CHECK ---
            if data.get('is_fnaf_game', False):
                tags = data.get('hashtags', [])
                if not tags or tags[0].lower() != '#fnaf':
                    tags = [t for t in tags if t.lower() != '#fnaf']
                    tags.insert(0, '#fnaf')
                    data['hashtags'] = tags[:3]
            
            return data
            
        except Exception as e:
            print(f"  Gemini Error: {e}")
            return {"title": current_title, "error": str(e)}

    def run(self):
        print("--- Draft Shorts Analyzer ---")
        
        results = []
        analyzed_titles = set()
        
        # Load existing
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    file_content = json.load(f)
                    if isinstance(file_content, list):
                        results = file_content
                        for item in results:
                            # Add original title to ignore list
                            if 'title' in item:
                                analyzed_titles.add(item['title'])
                            # Add the generated new_title to ignore list (in case you renamed the file on YouTube)
                            if 'new_title' in item:
                                analyzed_titles.add(item['new_title'])
                                
                print(f"Loaded {len(results)} existing analyses (checking against {len(analyzed_titles)} unique titles).")
            except (json.JSONDecodeError, IOError):
                results = []

        drafts = self.fetch_my_drafts()
        
        for i, draft in enumerate(drafts, 1):
            # This check now validates against both the old title AND the potential new title
            if IGNORE_ANALYZED_TITLES and draft['title'] in analyzed_titles:
                print(f"\n[{i}/{len(drafts)}] Skipping (Already Analyzed): {draft['title']}")
                continue

            print(f"\n[{i}/{len(drafts)}] Analyzing: {draft['title']}")
            
            video_path = self.download_private_video(draft['url'], draft['video_id'])
            
            if video_path and video_path.exists():
                # Get the structured analysis dictionary
                analysis_dict = self.analyze_with_gemini(video_path, draft['title'])
                
                # Print a clean summary to console so you can see progress
                if "error" not in analysis_dict:
                    print("-" * 40)
                    print(f"Game: {analysis_dict.get('game_name')}")
                    print(f"Score: {analysis_dict.get('virality')}/10")
                    print(f"Idea: {analysis_dict.get('new_title')}")
                    print("-" * 40)
                    
                    # Add to local lists immediately so we don't process duplicates within the same run
                    analyzed_titles.add(analysis_dict.get('title'))
                    if analysis_dict.get('new_title'):
                        analyzed_titles.add(analysis_dict.get('new_title'))
                else:
                    print(f"Analysis Failed: {analysis_dict['error']}")

                results.append(analysis_dict)
                video_path.unlink()
                
                # Save after every video so you don't lose progress
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