from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, disconnect

app = Flask(__name__)
# IMPORTANT: Change this secret key to a strong, random value for production
app.config['SECRET_KEY'] = 'your_super_secret_key_12345'
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
    # Client will send their name via 'set_name' event shortly after connect

@socketio.on('set_name')
def handle_set_name(data):
    client_sid = request.sid
    user_name = data.get('name')
    if not user_name:
        user_name = "Anonymous" # Default if blank
    
    # Check if name is already in use by another active user (simple check)
    is_name_taken = False
    for sid, user_info in active_users.items():
        if sid != client_sid and user_info['name'] == user_name and not user_info['is_admin']: # Admins can share name trigger
            is_name_taken = True
            break
    
    final_name = user_name
    if is_name_taken:
        # Append a simple suffix if name is taken
        import random
        final_name = f"{user_name}_{random.randint(100, 999)}"
        emit('name_taken', {'new_name': final_name}, room=client_sid)


    is_admin = False
    if user_name == ADMIN_USERNAME_TRIGGER:
        is_admin = True
        final_name = "Admin" # Display 'Admin' instead of the trigger name
        print(f"Admin connected: {client_sid}")
        # Emit special event only to admin to trigger rainbow effect and show panel
        emit('admin_status', {'is_admin': True}, room=client_sid)

    active_users[client_sid] = {
        'name': final_name,
        'is_admin': is_admin,
        'color': '#dcddde' # Default text color
    }
    
    # Acknowledge name setting for client
    emit('name_set_ack', {'name': final_name}, room=client_sid)

    # Join a default 'general' room, or allow clients to choose rooms
    join_room('general')
    # Announce user joined to all in the room
    emit('message', {
        'user': 'System',
        'text': f'{active_users[client_sid]["name"]} has joined the chat.',
        'user_type': 'system'
    }, room='general')


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in active_users:
        user_name = active_users[sid]['name']
        is_admin = active_users[sid]['is_admin']
        del active_users[sid]
        print(f'Client disconnected: {sid} (Name: {user_name}, Admin: {is_admin})')
        # Announce user left to all in the room
        emit('message', {
            'user': 'System',
            'text': f'{user_name} has left the chat.',
            'user_type': 'system'
        }, room='general')

@socketio.on('send_message')
def handle_message(data):
    sid = request.sid
    if sid not in active_users:
        return # User not properly set up
    
    user_info = active_users[sid]
    message_text = data.get('text')

    if not message_text:
        return

    message_data = {
        'sender_sid': sid, # The SID of the sender
        'user': user_info['name'], # Display name
        'text': message_text,
        'user_type': 'chat', # Indicate it's a regular chat message
        'is_admin_message': user_info['is_admin'], # Flag for rainbow effect
        'color': user_info['color'] # User's current color
    }
    emit('message', message_data, room='general') # Broadcast to all in 'general' room
    print(f"Message from {user_info['name']}: {message_text}")


@socketio.on('admin_command')
def handle_admin_command(data):
    sid = request.sid
    if sid not in active_users or not active_users[sid]['is_admin']:
        emit('message', {
            'user': 'System',
            'text': 'You are not authorized to use admin commands.',
            'user_type': 'system'
        }, room=sid)
        return

    command_type = data.get('type')
    target_sid = data.get('target_sid')
    new_color = data.get('color')

    admin_name = active_users[sid]['name']

    if command_type == 'get_users':
        users_list = []
        for s, info in active_users.items():
            users_list.append({
                'sid': s,
                'name': info['name'],
                'is_admin': info['is_admin'],
                'color': info['color']
            })
        emit('admin_users_list', {'users': users_list}, room=sid)
        print(f"Admin {admin_name} requested user list.")

    elif command_type == 'kick_user':
        if target_sid and target_sid in active_users:
            kicked_name = active_users[target_sid]['name']
            
            # Use a try-except block for disconnect in case target already disconnected
            try:
                disconnect(sid=target_sid) 
                print(f"Admin {admin_name} kicked {kicked_name} ({target_sid}).")
                # Announce kick to everyone
                emit('message', {
                    'user': 'System',
                    'text': f'{kicked_name} has been kicked by Admin.',
                    'user_type': 'system'
                }, room='general')
                # Message back to admin
                emit('message', {
                    'user': 'System',
                    'text': f'You kicked {kicked_name}.',
                    'user_type': 'system'
                }, room=sid)
            except KeyError:
                emit('message', {
                    'user': 'System',
                    'text': 'User not found or already disconnected.',
                    'user_type': 'system'
                }, room=sid)

        else:
            emit('message', {
                'user': 'System',
                'text': 'Invalid user SID to kick.',
                'user_type': 'system'
            }, room=sid)

    elif command_type == 'refresh_all_chat':
        emit('clear_chat_display', room='general') # Emit to all clients to clear their display
        emit('message', {
            'user': 'System',
            'text': 'Admin cleared the chat history for everyone.',
            'user_type': 'system'
        }, room='general')
        print(f"Admin {admin_name} cleared chat for all.")

    elif command_type == 'change_user_color':
        if target_sid and new_color:
            target_user_info = active_users.get(target_sid)
            if target_user_info:
                target_user_info['color'] = new_color
                # Notify clients that a user's color has changed (for future messages)
                emit('user_color_updated', {'sid': target_sid, 'new_color': new_color}, room='general')
                emit('message', {
                    'user': 'System',
                    'text': f'Admin changed {target_user_info["name"]}\'s color to {new_color}.',
                    'user_type': 'system'
                }, room='general')
                print(f"Admin {admin_name} changed {target_user_info['name']}'s color.")
            else:
                emit('message', {
                    'user': 'System',
                    'text': 'Invalid user SID to change color.',
                    'user_type': 'system'
                }, room=sid)
        else:
            emit('message', {
                'user': 'System',
                'text': 'Missing target SID or color for change_user_color.',
                'user_type': 'system'
            }, room=sid)
    else:
        emit('message', {
            'user': 'System',
            'text': 'Unknown admin command.',
            'user_type': 'system'
        }, room=sid)


if __name__ == '__main__':
    # For Render, you often need to get the port from the environment
    import os
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)
