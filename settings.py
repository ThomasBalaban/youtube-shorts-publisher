from gemjam import GEMJAM

PROCESS_SINGLE_VIDEO = False  # Set to False to scrape all drafts
ENABLE_SCRAPING_MODE = False # If this is True, the bot will ONLY scrape  videos and output to JSON.
ENABLE_ANALYSIS_MODE = True  # Run the Analyzer
VIDEOS_TO_PROCESS_COUNT = 50  # How many videos to schedule in a row
TEST_MODE = False # Will only process a single video, will not save 
GEMINI_API_KEY = GEMJAM