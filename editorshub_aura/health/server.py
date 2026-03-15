import os
import threading
from flask import Flask
from config import PORT

app = Flask(__name__)

@app.route('/')
def health_check():
    return "EditorsHub-AURA running", 200

def run_server():
    # Use 0.0.0.0 to bind to all interfaces, which is required for Render
    app.run(host='0.0.0.0', port=PORT, use_reloader=False)

def start_health_server():
    """Starts the Flask health server in a background daemon thread."""
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread
