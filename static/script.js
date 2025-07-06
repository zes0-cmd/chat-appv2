// Global variables
let socket;
let myName = '';
let mySid = ''; // To store client's own Socket ID
let isAdmin = false;
const ADMIN_USERNAME_TRIGGER = "./admin-menu./";

document.addEventListener('DOMContentLoaded', () => {
    // Connect to Socket.IO
    socket = io();

    const nameInput = document.getElementById('nameInput');
    const nameSubmitBtn = document.getElementById('nameSubmitBtn');
    const chatInput = document.getElementById('chatInput');
    const messageForm = document.getElementById('messageForm');
    const messagesDiv = document.getElementById('messages');
    const userListDiv = document.getElementById('userList');
    const adminPanelBtn = document.getElementById('adminPanelBtn');
    const adminPanelModal = document.getElementById('adminPanelModal');
    const adminUserListDiv = document.getElementById('adminUserList');
    const adminRefreshUsersBtn = document.getElementById('adminRefreshUsersBtn');
    const adminClearChatBtn = document.getElementById('adminClearChatBtn');
    const closeModalBtn = document.querySelector('.close-button');

    // --- User Name Submission ---
    nameSubmitBtn.addEventListener('click', () => {
        const enteredName = nameInput.value.trim();
        if (enteredName) {
            myName = enteredName;
            socket.emit('set_name', { name: myName });
            document.getElementById('nameSelection').style.display = 'none';
            document.getElementById('chatContainer').style.display = 'flex';
        }
    });

    // --- Message Sending ---
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const messageText = chatInput.value.trim();
        if (messageText && myName) {
            const timestamp = new Date().toLocaleTimeString();
            socket.emit('message', { message: messageText, timestamp: timestamp });
            chatInput.value = '';
        }
    });

    // --- Socket.IO Event Handlers ---

    socket.on('connect', () => {
        console.log('Connected to server!');
        mySid = socket.id; // Store my own SID
    });

    socket.on('admin_status', (data) => {
        if (data.is_admin) {
            isAdmin = true;
            // Apply rainbow effect to myName display
            const myNameDisplay = document.getElementById('myNameDisplay'); // You'll need this element in your HTML
            if (myNameDisplay) {
                myNameDisplay.textContent = 'Admin'; // Change text content
                myNameDisplay.classList.add('rainbow-text'); // Add the CSS class
            }
            adminPanelBtn.style.display = 'block'; // Show admin panel button
            addSystemMessage('You are now an Admin!', 'admin-message');
        }
    });

    socket.on('new_message', (data) => {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');

        const senderNameSpan = document.createElement('span');
        senderNameSpan.classList.add('sender-name');
        senderNameSpan.textContent = data.sender_name;

        // Apply admin rainbow effect if it's an admin message
        if (data.is_admin_message) {
            senderNameSpan.classList.add('rainbow-text');
        } else {
            // Apply specific user color if provided and not admin
            senderNameSpan.style.color = data.color || '#dcddde'; // Fallback to default
        }

        const timestampSpan = document.createElement('span');
        timestampSpan.classList.add('timestamp');
        timestampSpan.textContent = ` ${data.timestamp}`;

        const messageText = document.createElement('p');
        messageText.textContent = data.message_text;

        messageElement.appendChild(senderNameSpan);
        messageElement.appendChild(timestampSpan);
        messageElement.appendChild(messageText);

        messagesDiv.appendChild(messageElement);
        messagesDiv.scrollTop = messagesDiv.scrollHeight; // Auto-scroll to bottom
    });

    socket.on('user_joined', (data) => {
        addSystemMessage(`${data.name} has joined the chat.`);
        // No need to update user list here, admin panel will refresh
    });

    socket.on('user_left', (data) => {
        addSystemMessage(`${data.name} has left the chat.`);
        // No need to update user list here, admin panel will refresh
    });

    socket.on('system_message', (data) => {
        addSystemMessage(data.message, data.type || 'system-message');
    });

    // --- Admin Panel Functionality ---

    adminPanelBtn.addEventListener('click', () => {
        if (isAdmin) {
            adminPanelModal.style.display = 'block';
            // Request user list when opening the panel
            socket.emit('admin_command', { type: 'get_users' });
        }
    });

    closeModalBtn.addEventListener('click', () => {
        adminPanelModal.style.display = 'none';
    });

    window.addEventListener('click', (event) => {
        if (event.target == adminPanelModal) {
            adminPanelModal.style.display = 'none';
        }
    });

    adminRefreshUsersBtn.addEventListener('click', () => {
        if (isAdmin) {
            socket.emit('admin_command', { type: 'get_users' });
        }
    });

    socket.on('admin_users_list', (data) => {
        adminUserListDiv.innerHTML = ''; // Clear previous list
        data.users.forEach(user => {
            if (user.sid === mySid) return; // Don't list myself in kickable users

            const userItem = document.createElement('div');
            userItem.classList.add('admin-user-item');
            userItem.innerHTML = `
                <span>${user.name} (${user.sid.substring(0, 5)}...)</span>
                <button class="kick-btn" data-sid="${user.sid}">Kick</button>
                <input type="color" class="color-picker" value="${user.color}" data-sid="${user.sid}">
            `;
            adminUserListDiv.appendChild(userItem);
        });

        // Add event listeners for kick buttons
        document.querySelectorAll('.kick-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const targetSid = e.target.dataset.sid;
                if (confirm(`Are you sure you want to kick ${active_users[targetSid]?.name || 'this user'}?`)) {
                    socket.emit('admin_command', { type: 'kick_user', target_sid: targetSid });
                }
            });
        });

        // Add event listeners for color pickers
        document.querySelectorAll('.color-picker').forEach(picker => {
            picker.addEventListener('change', (e) => {
                const targetSid = e.target.dataset.sid;
                const newColor = e.target.value;
                socket.emit('admin_command', { type: 'change_user_color', target_sid: targetSid, color: newColor });
            });
        });
    });

    adminClearChatBtn.addEventListener('click', () => {
        if (isAdmin && confirm('Are you sure you want to clear the chat for everyone?')) {
            socket.emit('admin_command', { type: 'refresh_all_chat' });
        }
    });

    socket.on('clear_chat_display', () => {
        messagesDiv.innerHTML = ''; // Clear all messages from the display
    });

    socket.on('user_color_updated', (data) => {
        // Find all messages from this user and update their name color
        document.querySelectorAll(`.message .sender-name`).forEach(span => {
            // This is a simple way, ideally messages would have a data-sid attribute
            // Or you'd rebuild messages if history was involved.
            // For real-time, new messages will have the new color.
            // Old messages won't dynamically update their sender name's color unless you re-render.
            // For now, we'll assume only new messages reflect it easily.
            // If you want old messages to update, you'd need to re-scan messagesDiv and update.
            // For a "no history" chat, this isn't a huge problem.
        });
        // We'll trust the server to send new messages with the correct color
    });


    // Helper function to add system messages
    function addSystemMessage(message, type = 'system-message') {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', type);
        messageElement.innerHTML = `<p>${message}</p>`;
        messagesDiv.appendChild(messageElement);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
});