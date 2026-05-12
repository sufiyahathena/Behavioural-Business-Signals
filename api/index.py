import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.app import create_app

application = create_app()

# Ensure static files are served correctly
application.static_folder = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'ui', 'static'
)
application.template_folder = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'ui', 'templates'
)

handler = application
app = application
