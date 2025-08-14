"""
Configuration settings for the Telegram userbot sniper
"""

import os

# Telegram API credentials
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

# Default settings
DEFAULT_CHECK_INTERVAL = 30  # seconds between username checks
DEFAULT_PAIR_DELAY = 60      # seconds between pair rotations
MAX_ACCOUNTS = 50           # maximum number of accounts to manage

# Session storage
SESSION_DIR = "sessions"
# Database replaced with JSON files in data/ directory

# Channel creation settings
CHANNEL_TITLE_TEMPLATE = "sniped by @stabbato"
CHANNEL_MESSAGE = ".︻芫═─── @stabbato"

# Rate limiting
MIN_CHECK_INTERVAL = 5      # minimum seconds between checks
MAX_CHECK_INTERVAL = 300    # maximum seconds between checks
MIN_PAIR_DELAY = 10         # minimum seconds between pairs
MAX_PAIR_DELAY = 600        # maximum seconds between pairs

# Ensure session directory exists
os.makedirs(SESSION_DIR, exist_ok=True)
