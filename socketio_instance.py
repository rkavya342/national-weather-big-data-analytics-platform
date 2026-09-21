from flask_socketio import SocketIO

"""
Shared Flask-SocketIO Instance & Broadcast Helpers
---------------------------------------------------
Maintains a global SocketIO instance and provides helper functions to emit
real-time event updates ('weather_update', 'new_report') to connected dashboard clients.
"""

socketio = SocketIO(cors_allowed_origins="*")

def broadcast_weather_update(data=None):
    """
    Broadcast 'weather_update' event to all connected dashboard SocketIO clients.
    """
    try:
        payload = data if isinstance(data, dict) else {"status": "updated"}
        socketio.emit("weather_update", payload)
        print("SocketIO: Emitted 'weather_update' event.")
    except Exception as e:
        print("SocketIO emit weather_update error:", e)

def broadcast_new_report(data=None):
    """
    Broadcast 'new_report' event to all connected dashboard SocketIO clients.
    """
    try:
        payload = data if isinstance(data, dict) else {"status": "new_report_submitted"}
        socketio.emit("new_report", payload)
        print("SocketIO: Emitted 'new_report' event.")
    except Exception as e:
        print("SocketIO emit new_report error:", e)

def broadcast_weather_alert(data=None):
    """
    Broadcast 'weather_alert' event to all connected SocketIO clients.
    """
    try:
        payload = data if isinstance(data, dict) else {"status": "alert_triggered"}
        socketio.emit("weather_alert", payload)
        print("SocketIO: Emitted 'weather_alert' event.")
    except Exception as e:
        print("SocketIO emit weather_alert error:", e)

