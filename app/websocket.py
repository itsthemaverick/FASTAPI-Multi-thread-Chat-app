from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import WebSocket
from app.schemas import ChatMessage, MessageType


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by chat rooms,
    handles broadcasting messages, and stores recent room message history.
    """

    def __init__(self, max_history: int = 50):
        # Maps room_name -> List of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = defaultdict(list)
        # Maps WebSocket -> (username, room_name)
        self.user_registry: Dict[WebSocket, Tuple[str, str]] = {}
        # Stores recent history per room
        self.room_history: Dict[str, List[dict]] = defaultdict(list)
        self.max_history = max_history

    async def connect(self, websocket: WebSocket, room: str, username: str):
        """Accepts a new WebSocket connection and registers the user."""
        await websocket.accept()
        self.active_connections[room].append(websocket)
        self.user_registry[websocket] = (username, room)

        # Notify the room that a new user joined
        join_msg = ChatMessage(
            type=MessageType.USER_JOIN,
            username="System",
            content=f"{username} joined the chat.",
            room=room
        )
        
        # Send history to the newly connected user first
        await websocket.send_json({
            "type": "history",
            "messages": self.room_history[room],
            "active_users": self.get_room_user_count(room)
        })

        # Broadcast user join notification to everyone in the room
        await self.broadcast(room, join_msg.model_dump())

    def disconnect(self, websocket: WebSocket) -> Tuple[str, str]:
        """Removes a WebSocket connection and cleans up registry."""
        if websocket in self.user_registry:
            username, room = self.user_registry.pop(websocket)
            if websocket in self.active_connections[room]:
                self.active_connections[room].remove(websocket)
            return username, room
        return "", ""

    async def broadcast(self, room: str, data: dict):
        """Broadcasts a JSON message to all connected clients in a specific room."""
        # Save chat messages to room history
        if data.get("type") in [MessageType.CHAT.value, MessageType.USER_JOIN.value, MessageType.USER_LEAVE.value]:
            self._add_to_history(room, data)

        # Attach active count to all broadcast messages
        data["active_users"] = self.get_room_user_count(room)

        # Broadcast to all active connections in the room
        disconnected_sockets = []
        for connection in self.active_connections.get(room, []):
            try:
                await connection.send_json(data)
            except Exception:
                disconnected_sockets.append(connection)

        # Clean up any stale sockets
        for dead_socket in disconnected_sockets:
            self.disconnect(dead_socket)

    def get_room_user_count(self, room: str) -> int:
        """Returns the number of active users in a given room."""
        return len(self.active_connections.get(room, []))

    def get_room_users(self, room: str) -> List[str]:
        """Returns a list of active usernames in a room."""
        users = []
        for ws in self.active_connections.get(room, []):
            if ws in self.user_registry:
                users.append(self.user_registry[ws][0])
        return users

    def get_room_history(self, room: str) -> List[dict]:
        """Returns stored message history for a room."""
        return self.room_history.get(room, [])

    def _add_to_history(self, room: str, message: dict):
        """Adds a message to history, maintaining the max history buffer size."""
        self.room_history[room].append(message)
        if len(self.room_history[room]) > self.max_history:
            self.room_history[room].pop(0)


# Instantiate a global connection manager
manager = ConnectionManager()
