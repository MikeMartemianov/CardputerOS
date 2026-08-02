import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from youtube_proxy import app

# This is the entry point for Vercel
