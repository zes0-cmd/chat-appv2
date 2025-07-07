# app.py

import eventlet # <<< ADD THIS LINE FIRST
eventlet.monkey_patch() # <<< ADD THIS LINE SECOND

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
import threading
import time
import random
import uuid

# ... the rest of your app.py code remains the same ...

app = Flask(__name__)
# IMPORTANT: Change this secret key to a strong, random value for production
app.config['SECRET_KEY'] = 'your_super_secret_key_12345'
socketio = SocketIO(app, cors_allowed_origins="*")

# ... rest of your code ...

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on http://0.0.0.0:{port}")
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
