from flask_socketio import emit, join_room, leave_room
from extensions import socketio
from flask import request


@socketio.on('connect')
def handle_connect():
    pass


@socketio.on('identify')
def handle_identify(data):
    try:
        user_id = int(data.get('user_id'))
    except Exception:
        return
    room = f'user_{user_id}'
    join_room(room)


@socketio.on('disconnect')
def handle_disconnect():
    pass
