from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
import threading
import time
import random
import uuid # For unique IDs for announcements and private chat rooms

app = Flask(__name__)
# IMPORTANT: Change this secret key to a strong, random value for production
app.config['SECRET_KEY'] = 'your_super_secret_key_12345'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for active users
# Key: Socket ID, Value: {'name': 'username', 'is_admin': False, 'color': '#dcddde', 'coins': 0, 'is_muted': False}
active_users = {}

# In-memory storage for temporarily banned names (resets on server restart)
banned_names = set()

# Define your admin username (case-sensitive)
ADMIN_USERNAME_TRIGGER = "./admin-menu./"

# Shop Items (Ephemeral - reset on server restart)
SHOP_ITEMS = {
    'red_name': {'name': 'Red Name', 'cost': 10, 'type': 'color', 'value': '#FF0000'},
    'blue_name': {'name': 'Blue Name', 'cost': 10, 'type': 'color', 'value': '#0000FF'},
    'green_name': {'name': 'Green Name', 'cost': 10, 'type': 'color', 'value': '#008000'},
    'gold_name': {'name': 'Gold Name', 'cost': 20, 'type': 'color', 'value': '#FFD700'},
    'pink_name': {'name': 'Pink Name', 'cost': 15, 'type': 'color', 'value': '#FF69B4'},
    # Add more items here if you wish
}

# --- Coin Generation Background Task ---
# This function will run in a separate thread
def coin_generation_task():
    while True:
        # Give coins to all active users
        with app.app_context(): # Needed if you access Flask/SocketIO outside request context
            for sid, user_info in list(active_users.items()): # Use list() to iterate a copy
                if user_info: # Ensure user still exists
                    user_info['coins'] += 1
                    # Emit update to just that user
                    socketio.emit('coin_update', {'coins': user_info['coins']}, room=sid)
        time.sleep(60) # Wait for 60 seconds (1 minute)

# Start the coin generation task when the app starts
@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    # Client will send their name via 'set_name' event shortly after connect
    # This also handles initialization of user data for new connections

# This ensures the background task starts only once when the server first runs
# and isn't restarted for every new client connection.
if not hasattr(app, 'coin_task_started'):
    app.coin_task_started = True
    socketio.start_background_task(target=coin_generation_task)
    print("Coin generation background task started.")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('set_name')
def handle_set_name(data):
    client_sid = request.sid
    user_name = data.get('name')
    if not user_name:
        user_name = "Anonymous" # Default if blank
    
    # Check for temporary name ban (case-insensitive)
    if user_name.lower() in banned_names:
        emit('message', {
            'user': 'System',
            'text': f'The name "{user_name}" is temporarily banned. Please choose another name or try again later.',
            'user_type': 'system'
        }, room=client_sid)
        disconnect(sid=client_sid) # Disconnect the banned user
        return

    # Check if name is already in use by another active user (simple check)
    is_name_taken = False
    for sid, user_info in active_users.items():
        if sid != client_sid and user_info['name'] == user_name and not user_info['is_admin']: # Admins can share name trigger
            is_name_taken = True
            break
    
    final_name = user_name
    if is_name_taken:
        # Append a simple suffix if name is taken
        final_name = f"{user_name}_{random.randint(100, 999)}"
        emit('name_taken', {'new_name': final_name}, room=client_sid)

    is_admin = False
    if user_name == ADMIN_USERNAME_TRIGGER:
        is_admin = True
        final_name = "Admin" # Display 'Admin' instead of the trigger name
        print(f"Admin connected: {client_sid}")
        # Emit special event only to admin to trigger rainbow effect and show panel
        emit('admin_status', {'is_admin': True}, room=client_sid)
    
    # Initialize/update user data including coins and mute status
    active_users[client_sid] = {
        'name': final_name,
        'is_admin': is_admin,
        'color': '#dcddde', # Default text color
        'coins': active_users.get(client_sid, {}).get('coins', 0), # Keep coins if reconnecting, else 0
        'is_muted': active_users.get(client_sid, {}).get('is_muted', False) # Keep mute status if reconnecting
    }
    
    # Acknowledge name setting for client
    emit('name_set_ack', {
        'name': final_name,
        'coins': active_users[client_sid]['coins']
    }, room=client_sid)

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

    # Check if user is muted
    if user_info['is_muted']:
        emit('message', {
            'user': 'System',
            'text': 'You are currently muted and cannot send messages.',
            'user_type': 'system'
        }, room=sid)
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


@socketio.on('buy_item')
def handle_buy_item(data):
    sid = request.sid
    if sid not in active_users:
        return # User not found
    
    user_info = active_users[sid]
    item_id = data.get('item_id')
    item = SHOP_ITEMS.get(item_id)

    if not item:
        emit('purchase_feedback', {'success': False, 'message': 'Item not found.'}, room=sid)
        return

    if user_info['coins'] < item['cost']:
        emit('purchase_feedback', {'success': False, 'message': 'Not enough coins!'}, room=sid)
        return
    
    # Process purchase
    user_info['coins'] -= item['cost']
    
    if item['type'] == 'color':
        user_info['color'] = item['value']
        emit('purchase_feedback', {
            'success': True,
            'message': f'You bought {item["name"]} for {item["cost"]} coins!',
            'type': 'color_update',
            'value': item['value'],
            'new_coins': user_info['coins']
        }, room=sid)
        # Announce color change to everyone
        emit('message', {
            'user': 'System',
            'text': f'{user_info["name"]} changed their name color.',
            'user_type': 'system'
        }, room='general')
    else:
        # Handle other item types here if you add them later
        emit('purchase_feedback', {
            'success': True,
            'message': f'You bought {item["name"]} for {item["cost"]} coins!',
            'new_coins': user_info['coins']
        }, room=sid)

    # Always send coin update after purchase
    emit('coin_update', {'coins': user_info['coins']}, room=sid)
    print(f"{user_info['name']} bought {item['name']}. Coins remaining: {user_info['coins']}")


# --- Private Chat Handling ---
@socketio.on('start_private_chat')
def handle_start_private_chat(data):
    initiator_sid = request.sid
    target_sid = data.get('target_sid')

    if initiator_sid not in active_users or target_sid not in active_users:
        emit('message', {
            'user': 'System',
            'text': 'User not found for private chat.',
            'user_type': 'system'
        }, room=initiator_sid)
        return
    
    if initiator_sid == target_sid:
        emit('message', {
            'user': 'System',
            'text': 'You cannot start a private chat with yourself.',
            'user_type': 'system'
        }, room=initiator_sid)
        return

    initiator_info = active_users[initiator_sid]
    target_info = active_users[target_sid]

    # Create a unique room name for the private chat (sorted SIDs for consistency)
    room_name_parts = sorted([initiator_sid, target_sid])
    private_room_id = f"dm_{room_name_parts[0]}_{room_name_parts[1]}"

    # Join both users to the private room
    join_room(private_room_id, sid=initiator_sid)
    join_room(private_room_id, sid=target_sid)

    # Notify both clients about the private chat initiation
    emit('private_chat_initiated', {
        'room_id': private_room_id,
        'other_user_name': target_info['name'],
        'other_user_sid': target_sid
    }, room=initiator_sid)
    
    emit('private_chat_initiated', {
        'room_id': private_room_id,
        'other_user_name': initiator_info['name'],
        'other_user_sid': initiator_sid
    }, room=target_sid)
    
    print(f"{initiator_info['name']} ({initiator_sid}) started private chat with {target_info['name']} ({target_sid}) in room {private_room_id}")

@socketio.on('send_private_message')
def handle_private_message(data):
    sender_sid = request.sid
    room_id = data.get('room_id')
    message_text = data.get('text')

    if sender_sid not in active_users or not message_text or not room_id:
        return

    sender_info = active_users[sender_sid]

    message_data = {
        'sender_sid': sender_sid,
        'user': sender_info['name'],
        'text': message_text,
        'user_type': 'private_chat',
        'is_admin_message': sender_info['is_admin'],
        'color': sender_info['color']
    }
    # Emit only to the specific private room
    emit('private_message', message_data, room=room_id)
    print(f"Private message in {room_id} from {sender_info['name']}: {message_text}")


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
    target_name = data.get('target_name') # For ban/unban
    new_color = data.get('color')
    announcement_message = data.get('message') # For announcement command
    mute_status = data.get('mute_status') # For mute/unmute

    admin_name = active_users[sid]['name']

    if command_type == 'get_users':
        users_list = []
        for s, info in active_users.items():
            users_list.append({
                'sid': s,
                'name': info['name'],
                'is_admin': info['is_admin'],
                'color': info['color'],
                'is_muted': info['is_muted'] # Include mute status
            })
        emit('admin_users_list', {
            'users': users_list,
            'total_users': len(active_users) # Send total count
        }, room=sid)
        print(f"Admin {admin_name} requested user list and stats.")

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
                # Emit to all clients that this user's color has been updated
                emit('user_color_updated', {
                    'sid': target_sid,
                    'new_color': new_color,
                    'user_name': target_user_info['name']
                }, room='general')
                emit('message', {
                    'user': 'System',
                    'text': f'Admin changed {target_user_info["name"]}\'s name color to {new_color}.',
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

    elif command_type == 'send_announcement':
        if announcement_message:
            emit('message', {
                'user': 'Admin Announcement',
                'text': announcement_message,
                'user_type': 'announcement', # New type for distinct styling
                'id': str(uuid.uuid4()) # Unique ID for potential future features
            }, room='general')
            print(f"Admin {admin_name} sent announcement: {announcement_message}")
        else:
            emit('message', {
                'user': 'System',
                'text': 'Announcement message cannot be empty.',
                'user_type': 'system'
            }, room=sid)
    
    elif command_type == 'mute_user' or command_type == 'unmute_user':
        if target_sid and target_sid in active_users:
            active_users[target_sid]['is_muted'] = (command_type == 'mute_user')
            action = "muted" if command_type == 'mute_user' else "unmuted"
            target_user_name = active_users[target_sid]['name']
            
            emit('message', {
                'user': 'System',
                'text': f'Admin {action} {target_user_name}.',
                'user_type': 'system'
            }, room='general')
            
            # Notify the muted/unmuted user privately
            emit('message', {
                'user': 'System',
                'text': f'You have been {action} by an Admin.',
                'user_type': 'system'
            }, room=target_sid)
            print(f"Admin {admin_name} {action} {target_user_name}.")
        else:
            emit('message', {
                'user': 'System',
                'text': 'Invalid user SID for mute/unmute.',
                'user_type': 'system'
            }, room=sid)

    elif command_type == 'ban_name' or command_type == 'unban_name':
        if target_name:
            target_name_lower = target_name.lower() # Case-insensitive ban
            if command_type == 'ban_name':
                banned_names.add(target_name_lower)
                action = "banned"
                # If the user with this name is currently connected, disconnect them
                for s, info in list(active_users.items()):
                    if info['name'].lower() == target_name_lower:
                        try:
                            socketio.emit('disconnect_client', {'reason': 'banned'}, room=s)
                            socketio.sleep(0.1)
                            # Remove from active_users if not already handled by disconnect
                            if s in active_users:
                                del active_users[s]
                        except Exception as e:
                            print(f"Error disconnecting banned user {info['name']}: {e}")
                
            else: # unban_name
                if target_name_lower in banned_names:
                    banned_names.remove(target_name_lower)
                action = "unbanned"
            
            emit('message', {
                'user': 'System',
                'text': f'Admin {action} the name "{target_name}".',
                'user_type': 'system'
            }, room='general')
            emit('message', {
                'user': 'System',
                'text': f'You {action} the name "{target_name}".',
                'user_type': 'system'
            }, room=sid)
            print(f"Admin {admin_name} {action} name: {target_name}")
        else:
            emit('message', {
                'user': 'System',
                'text': 'Target name cannot be empty for ban/unban.',
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
    socketio.run(app, debug=False, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True) # allow_unsafe_werkzeug needed if you run directly
