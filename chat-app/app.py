# app.py - Your main application file

import eventlet # Necessary for Socket.IO's 'eventlet' async mode
eventlet.monkey_patch() # IMPORTANT: Apply patches as early as possible in your script

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import os

app = Flask(__name__)
# Set a strong secret key. For production, use an environment variable.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_super_secret_key_here') # <<< CHANGE THIS!
socketio = SocketIO(app, cors_allowed_origins="*") # Allows connections from any origin (important for dev)

# --- Your Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html') # Assuming you have an index.html

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('chat.html', username=session['username']) # Assuming you have a chat.html

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    if username:
        session['username'] = username
        return redirect(url_for('chat'))
    return redirect(url_for('index'))

# --- Your Socket.IO Event Handlers ---

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit('status', {'msg': f'{username} has entered the room {room}.'}, room=room)
    print(f"{username} has entered the room {room}")

@socketio.on('message')
def handle_message(data):
    msg = data['msg']
    username = data['username']
    room = data['room']
    print(f"Message from {room} by {username}: {msg}")
    emit('message', {'msg': msg, 'username': username}, room=room)

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('status', {'msg': f'{username} has left the room {room}.'}, room=room)
    print(f"{username} has left the room {room}")

# This block is only for local development. Render (Gunicorn) will ignore it.
if __name__ == '__main__':
    # Use 0.0.0.0 to make it accessible from your network during local testing
    # Port 5000 is standard for Flask development
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)