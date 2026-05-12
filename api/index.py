import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.app import create_app

app = create_app()

# Vercel serverless handler
handler = app
