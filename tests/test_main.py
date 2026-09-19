from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_homepage_endpoint():
    """Test that the homepage serves index.html with 200 OK status."""
    response = client.get("/")
    assert response.status_code == 200
    assert "FastAPI Real-Time Chat" in response.text


def test_get_rooms_endpoint():
    """Test retrieving available chat rooms via REST API."""
    response = client.get("/api/rooms")
    assert response.status_code == 200
    rooms = response.json()
    assert isinstance(rooms, list)
    assert len(rooms) == 4
    room_names = [r["name"] for r in rooms]
    assert "general" in room_names
    assert "python" in room_names


def test_get_room_history_endpoint():
    """Test retrieving history for a valid room."""
    response = client.get("/api/history/general")
    assert response.status_code == 200
    data = response.json()
    assert data["room"] == "general"
    assert isinstance(data["history"], list)


def test_get_invalid_room_history():
    """Test retrieving history for a non-existent room returns 404."""
    response = client.get("/api/history/nonexistentroom")
    assert response.status_code == 404


def test_websocket_chat_flow():
    """Test WebSocket connection, history payload, and message broadcast."""
    with client.websocket_connect("/ws/general/TesterBot") as websocket:
        # First message sent upon connect is the history payload
        data = websocket.receive_json()
        assert data["type"] == "history"
        assert "active_users" in data

        # Send a chat message
        websocket.send_text("Hello from pytest!")

        # Next message received should be the broadcasted chat message
        broadcast = websocket.receive_json()
        assert broadcast["type"] == "chat"
        assert broadcast["username"] == "TesterBot"
        assert broadcast["content"] == "Hello from pytest!"
        assert broadcast["room"] == "general"
