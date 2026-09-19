from pathlib import Path
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.schemas import ChatMessage, MessageType, RoomInfo
from app.websocket import manager

app = FastAPI(
    title="FastAPI Real-Time Chat App",
    description="A beginner-friendly yet feature-rich real-time multi-room WebSocket chat application.",
    version="1.0.0"
)

# Resolve path to static files directory
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Mount static files directory (CSS, JS, images)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Default available chat rooms
AVAILABLE_ROOMS: Dict[str, str] = {
    "general": "General discussion room for everyone",
    "python": "Discuss Python code, libraries, and frameworks",
    "tech": "All things tech, AI, hardware, and dev tools",
    "lounge": "Casual off-topic banter and relaxing conversations"
}


@app.get("/", response_class=FileResponse)
async def get_homepage():
    """Serves the main single-page application frontend."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_file)


@app.get("/api/rooms", response_model=List[RoomInfo])
async def get_rooms():
    """Returns a list of active rooms with descriptions and user counts."""
    rooms_list = []
    for name, description in AVAILABLE_ROOMS.items():
        rooms_list.append(
            RoomInfo(
                name=name,
                description=description,
                active_users=manager.get_room_user_count(name)
            )
        )
    return rooms_list


@app.get("/api/history/{room}")
async def get_room_history(room: str):
    """Returns message history for a specified chat room."""
    if room not in AVAILABLE_ROOMS:
        raise HTTPException(status_code=404, detail="Room not found")
    return JSONResponse(content={
        "room": room,
        "history": manager.get_room_history(room)
    })


@app.websocket("/ws/{room}/{username}")
async def websocket_endpoint(websocket: WebSocket, room: str, username: str):
    """
    WebSocket endpoint for real-time messaging.
    Handles user connection, message receiving & broadcasting, and disconnection events.
    """
    # Clean username and room inputs
    username = username.strip()
    room = room.strip().lower()

    if not username:
        await websocket.close(code=4000, reason="Username cannot be empty")
        return

    if room not in AVAILABLE_ROOMS:
        await websocket.close(code=4004, reason="Chat room does not exist")
        return

    # Accept connection and register user
    await manager.connect(websocket, room, username)

    try:
        while True:
            # Receive text data from frontend
            data = await websocket.receive_text()
            
            # Create a structured ChatMessage object
            chat_msg = ChatMessage(
                type=MessageType.CHAT,
                username=username,
                content=data,
                room=room
            )

            # Broadcast message to all users in the room
            await manager.broadcast(room, chat_msg.model_dump())

    except WebSocketDisconnect:
        # Handle client disconnect gracefully
        disconnected_user, room_name = manager.disconnect(websocket)
        if disconnected_user and room_name:
            leave_msg = ChatMessage(
                type=MessageType.USER_LEAVE,
                username="System",
                content=f"{disconnected_user} left the chat.",
                room=room_name
            )
            await manager.broadcast(room_name, leave_msg.model_dump())
