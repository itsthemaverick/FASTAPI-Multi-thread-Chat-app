/**
 * FastAPI Real-Time Chat Application JavaScript Client
 */

// Application State
let currentUser = "";
let currentRoom = "general";
let socket = null;
let roomsData = [];

// DOM Elements
const joinModal = document.getElementById("joinModal");
const usernameInput = document.getElementById("usernameInput");
const roomSelect = document.getElementById("roomSelect");
const currentUserDisplay = document.getElementById("currentUserDisplay");
const userAvatar = document.getElementById("userAvatar");
const roomList = document.getElementById("roomList");
const currentRoomTitle = document.getElementById("currentRoomTitle");
const currentRoomDesc = document.getElementById("currentRoomDesc");
const connectionStatus = document.getElementById("connectionStatus");
const statusText = document.getElementById("statusText");
const activeCount = document.getElementById("activeCount");
const chatFeed = document.getElementById("chatFeed");
const messageInput = document.getElementById("messageInput");

// Web Audio API Notification Sound Synthesizer (No external audio files required!)
function playNotificationSound() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5 note
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.1); // A5 note

        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + 0.25);
    } catch (e) {
        // Silently ignore audio errors if blocked by browser autoplay policies
    }
}

// Initial Page Load Setup
document.addEventListener("DOMContentLoaded", () => {
    fetchRooms();
});

// Fetch list of available rooms from REST API
async function fetchRooms() {
    try {
        const res = await fetch("/api/rooms");
        if (res.ok) {
            roomsData = await res.json();
            renderSidebarRooms();
        }
    } catch (err) {
        console.error("Error fetching rooms:", err);
    }
}

// Render Room Items in Sidebar
function renderSidebarRooms() {
    roomList.innerHTML = "";
    roomsData.forEach(r => {
        const li = document.createElement("li");
        li.className = `room-item ${r.name === currentRoom ? 'active' : ''}`;
        li.onclick = () => switchRoom(r.name);
        li.innerHTML = `
            <span class="room-name"># ${r.name}</span>
            <span class="room-user-count" id="count-${r.name}">${r.active_users || 0}</span>
        `;
        roomList.appendChild(li);
    });
}

// Join Form Submission Handler
function handleJoin(e) {
    e.preventDefault();
    const name = usernameInput.value.trim();
    const selectedRoom = roomSelect.value;

    if (!name) return;

    currentUser = name;
    currentRoom = selectedRoom;

    // Update Profile UI
    currentUserDisplay.textContent = currentUser;
    userAvatar.textContent = currentUser.charAt(0).toUpperCase();

    // Hide Join Modal
    joinModal.classList.add("hidden");

    // Render rooms list and initialize WebSocket connection
    renderSidebarRooms();
    updateRoomHeaderInfo();
    connectWebSocket();
}

// Connect to WebSocket Server
function connectWebSocket() {
    // Construct WebSocket URL dynamically matching current protocol (ws or wss)
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${currentRoom}/${encodeURIComponent(currentUser)}`;

    updateConnectionStatus("Connecting...", false);

    if (socket) {
        socket.close();
    }

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        updateConnectionStatus("Connected", true);
        chatFeed.innerHTML = ""; // Clear existing feed on fresh connect
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleIncomingMessage(data);
    };

    socket.onclose = (event) => {
        updateConnectionStatus("Disconnected", false);
        if (!joinModal.classList.contains("hidden")) return;
        
        appendSystemMessage("Connection lost. Reconnecting in 3s...");
        setTimeout(() => {
            if (currentUser && !joinModal.classList.contains("hidden")) {
                connectWebSocket();
            }
        }, 3000);
    };

    socket.onerror = (err) => {
        console.error("WebSocket error:", err);
        updateConnectionStatus("Error", false);
    };
}

// Handle Incoming WebSocket Messages
function handleIncomingMessage(data) {
    // Update active count if provided in payload
    if (data.active_users !== undefined) {
        updateActiveUserCount(data.active_users);
    }

    if (data.type === "history") {
        chatFeed.innerHTML = "";
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => appendMessageToFeed(msg, false));
        } else {
            appendSystemMessage(`Welcome to #${currentRoom}! Start the conversation.`);
        }
        scrollToBottom();
        return;
    }

    if (data.type === "chat") {
        const isMyMsg = data.username === currentUser;
        appendMessageToFeed(data, true);
        if (!isMyMsg) {
            playNotificationSound();
        }
    } else if (data.type === "user_join" || data.type === "user_leave") {
        appendSystemMessage(data.content);
        fetchRooms(); // Refresh room user counts
    }
}

// Append Chat Message Bubble to Feed
function appendMessageToFeed(msg, autoScroll = true) {
    const isMe = msg.username === currentUser;
    const row = document.createElement("div");
    row.className = `message-row ${isMe ? 'me' : 'others'}`;

    const initial = msg.username ? msg.username.charAt(0).toUpperCase() : '?';
    const timestamp = msg.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    row.innerHTML = `
        ${!isMe ? `<div class="msg-avatar">${initial}</div>` : ''}
        <div class="msg-content-wrapper">
            <div class="msg-meta">
                <span class="msg-sender">${escapeHtml(msg.username)}</span>
                <span class="msg-time">${timestamp}</span>
            </div>
            <div class="msg-bubble">${escapeHtml(msg.content)}</div>
        </div>
        ${isMe ? `<div class="msg-avatar" style="background: var(--primary-gradient);">${initial}</div>` : ''}
    `;

    chatFeed.appendChild(row);

    if (autoScroll) {
        scrollToBottom();
    }
}

// Append System Notification Pill
function appendSystemMessage(text) {
    const div = document.createElement("div");
    div.className = "system-notification";
    div.innerHTML = `<i class="fa-solid fa-info-circle"></i> <span>${escapeHtml(text)}</span>`;
    chatFeed.appendChild(div);
    scrollToBottom();
}

// Send Message Handler
function sendMessage(e) {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || !socket || socket.readyState !== WebSocket.OPEN) return;

    socket.send(text);
    messageInput.value = "";
    messageInput.focus();
}

// Switch Chat Rooms
function switchRoom(newRoom) {
    if (newRoom === currentRoom) return;

    currentRoom = newRoom;
    renderSidebarRooms();
    updateRoomHeaderInfo();

    if (currentUser) {
        connectWebSocket();
    }
}

// Update Room Header UI
function updateRoomHeaderInfo() {
    currentRoomTitle.textContent = `# ${currentRoom}`;
    const found = roomsData.find(r => r.name === currentRoom);
    if (found) {
        currentRoomDesc.textContent = found.description;
    }
}

// Update Connection Status Badge
function updateConnectionStatus(text, isConnected) {
    statusText.textContent = text;
    if (isConnected) {
        connectionStatus.classList.add("connected");
    } else {
        connectionStatus.classList.remove("connected");
    }
}

// Update Active Users Count Pill
function updateActiveUserCount(count) {
    activeCount.textContent = `${count} ${count === 1 ? 'user' : 'users'}`;
    const badge = document.getElementById(`count-${currentRoom}`);
    if (badge) {
        badge.textContent = count;
    }
}

// Auto-scroll chat feed to latest message
function scrollToBottom() {
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

// Helper: Escape HTML to prevent XSS injection
function escapeHtml(text) {
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
}

// Leave Chat Handler
function leaveChat() {
    if (socket) {
        socket.close();
    }
    joinModal.classList.remove("hidden");
    usernameInput.value = "";
    usernameInput.focus();
}
