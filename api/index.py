import sys
import os

# Add project root to path
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from flask import send_from_directory
from ui.app import create_app

app = create_app()

# Override static folder to absolute path
app.static_folder = os.path.join(root, 'ui', 'static')
app.static_url_path = '/static'
app.template_folder = os.path.join(root, 'ui', 'templates')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

handler = app
