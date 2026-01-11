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

    def analyze_with_gemini(self, video_path, title):
        prompt = f"""You are an expert YouTube editor reviewing a DRAFT video before publication.
        
Video Title: "{title}"

Please provide a critique:
1. **Hook Check**: Does the first 3 seconds grab attention?
2. **Pacing**: Is it too slow or too fast?
3. **Title Relevance**: Does the video deliver on the title?
4. **Viral Potential**: Rating 1-10 and one specific fix to improve it.
"""
        print("  Uploading to Gemini...")
        video_file = genai.upload_file(path=str(video_path))
        
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)
            
        response = self.gemini_model.generate_content([video_file, prompt])
        genai.delete_file(video_file.name)
        return response.text

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
                print(f"Loaded {len(results)} existing analyses from {self.output_file}")
            except (json.JSONDecodeError, IOError):
                print(f"Warning: Could not read {self.output_file}. Starting fresh.")
                results = []

        drafts = self.fetch_my_drafts()
        
        for i, draft in enumerate(drafts, 1):
            if IGNORE_ANALYZED_TITLES and draft['title'] in analyzed_titles:
                print(f"\n[{i}/{len(drafts)}] Skipping (Already Analyzed): {draft['title']}")
                continue

            print(f"\n[{i}/{len(drafts)}] Analyzing Draft: {draft['title']} ({draft['status_label']})")
            
            video_path = self.download_private_video(draft['url'], draft['video_id'])
            
            if video_path and video_path.exists():
                analysis = self.analyze_with_gemini(video_path, draft['title'])
                print("\n" + ">" * 20 + " GEMINI FEEDBACK " + "<" * 20)
                print(analysis)
                print(">" * 57)
                
                results.append({
                    'title': draft['title'],
                    'status': draft['status_label'],
                    'analysis': analysis
                })
                
                analyzed_titles.add(draft['title'])
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