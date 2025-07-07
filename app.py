# app.py

import eventlet # Keep this at the very top
eventlet.monkey_patch() # Keep this at the very top

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
import threading
import time
import random
import uuid

# --- Flask App Initialization ---
# The 'app' variable MUST be defined BEFORE any @app.route decorators use it.
app = Flask(__name__)

# IMPORTANT: Change this secret key to a strong, random value for production
app.config['SECRET_KEY'] = 'your_super_secret_key_12345'

# Initialize SocketIO with your Flask app
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Flask Route Definitions ---
# This is the route for your main page.
# It MUST be defined at the top-level of the file (not inside a function or if block).
@app.route('/')
def index():
    # This renders the index.html from your 'templates' folder
    return render_template('index.html')

# --- SocketIO Event Handlers ---
# These functions handle WebSocket connections and messages.
# They should also be at the top-level of the file.
@socketio.on('connect')
def handle_connect():
    print(f'[CONNECT] Client connected: {request.sid}')
    # ... rest of your connect logic ...

@socketio.on('set_name')
def handle_set_name(data):
    # ... your set_name logic, including admin check ...
    pass

# ... (include all your other @socketio.on functions like handle_message, admin_command, etc.) ...


# --- Main execution block (for Gunicorn/Render deployment) ---
if __name__ == '__main__':
    # This block is for when you run app.py directly or via Gunicorn.
    # It ensures the server starts correctly on Render's port.
    import os
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on http://0.0.0.0:{port}")
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
