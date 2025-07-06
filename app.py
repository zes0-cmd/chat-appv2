from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # IMPORTANT: Change this!
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for active users
# Key: Socket ID, Value: {'name': 'username', 'is_admin': False, 'color': '#dcddde'}
active_users = {}

# Define your admin username (case-sensitive)
ADMIN_USERNAME_TRIGGER = "./admin-menu./"

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    # Client will send their name shortly after connect

@socketio.on('set_name')
def handle_set_name(data):
    user_name = data.get('name')
    if not user_name:
        return # Or disconnect them

    is_admin = False
    display_name = user_name

    if user_name == ADMIN_USERNAME_TRIGGER:
        is_admin = True
        display_name = "Admin" # Display 'Admin' instead of the trigger
        print(f"Admin connected: {request.sid}")
        # Emit special event only to admin to trigger rainbow effect
        emit('admin_status', {'is_admin': True}, room=request.sid)

    active_users[request.sid] = {
        'name': display_name,
        'is_admin': is_admin,
        'color': '#dcddde' # Default color for users
    }
    # Join a default 'general' room, or allow clients to choose rooms
    join_room('general')
    emit('user_joined', {'name': display_name, 'sid': request.sid, 'color': active_users[request.sid]['color']}, room='general')
    emit('system_message', {'message': f'{display_name} has joined the chat.'}, room='general')


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in active_users:
        user_name = active_users[sid]['name']
        is_admin = active_users[sid]['is_admin']
        del active_users[sid]
        print(f'Client disconnected: {sid} (Name: {user_name}, Admin: {is_admin})')
        emit('user_left', {'name': user_name, 'sid': sid}, room='general')
        emit('system_message', {'message': f'{user_name} has left the chat.'}, room='general')

@socketio.on('message')
def handle_message(data):
    sid = request.sid
    if sid not in active_users:
        return # User not properly set up

    user_info = active_users[sid]
    message_text = data.get('message')

    if not message_text:
        return

    message_data = {
        'sender_sid': sid,
        'sender_name': user_info['name'],
        'message_text': message_text,
        'timestamp': request.event['args'][0]['timestamp'] if 'timestamp' in request.event['args'][0] else 'Now', # Get timestamp from client if sent
        'is_admin_message': user_info['is_admin'],
        'color': user_info['color']
    }
    emit('new_message', message_data, room='general')
    print(f"Message from {user_info['name']}: {message_text}")


@socketio.on('admin_command')
def handle_admin_command(data):
    sid = request.sid
    if sid not in active_users or not active_users[sid]['is_admin']:
        emit('system_message', {'message': 'You are not authorized to use admin commands.'}, room=sid)
        return

    command_type = data.get('type')
    target_sid = data.get('target_sid')
    new_color = data.get('color')

    if command_type == 'get_users':
        users_list = []
        for s, info in active_users.items():
            users_list.append({'sid': s, 'name': info['name'], 'is_admin': info['is_admin'], 'color': info['color']})
        emit('admin_users_list', {'users': users_list}, room=sid)
        print(f"Admin {active_users[sid]['name']} requested user list.")

    elif command_type == 'kick_user':
        if target_sid and target_sid in active_users:
            kicked_name = active_users[target_sid]['name']
            socketio.disconnect(sid=target_sid, silent=False) # Disconnect the target
            emit('system_message', {'message': f'{kicked_name} has been kicked by Admin.'}, room='general')
            emit('system_message', {'message': f'You kicked {kicked_name}.'}, room=sid)
            print(f"Admin {active_users[sid]['name']} kicked {kicked_name} ({target_sid}).")
        else:
            emit('system_message', {'message': 'Invalid user SID to kick.'}, room=sid)

    elif command_type == 'refresh_all_chat':
        emit('clear_chat_display', room='general') # Emit to all clients
        emit('system_message', {'message': 'Admin cleared the chat history for everyone.'}, room='general')
        print(f"Admin {active_users[sid]['name']} refreshed chat for all.")

    elif command_type == 'change_user_color':
        if target_sid and new_color:
            target_user_info = active_users.get(target_sid)
            if target_user_info:
                target_user_info['color'] = new_color
                emit('user_color_updated', {'sid': target_sid, 'new_color': new_color}, room='general')
                emit('system_message', {'message': f'Admin changed {target_user_info["name"]}\'s color to {new_color}.'}, room='general')
                print(f"Admin {active_users[sid]['name']} changed {target_user_info['name']}'s color.")
            else:
                emit('system_message', {'message': 'Invalid user SID to change color.'}, room=sid)
        else:
            emit('system_message', {'message': 'Missing target SID or color for change_user_color.'}, room=sid)
    else:
        emit('system_message', {'message': 'Unknown admin command.'}, room=sid)


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8080) # Or your Render port
