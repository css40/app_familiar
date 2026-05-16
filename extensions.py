from flask_socketio import SocketIO

# Force the standard Python threading async mode to avoid Eventlet warnings.
# If you want, later we can switch to gevent or asyncio as a more scalable option.
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
