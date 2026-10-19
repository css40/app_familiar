from flask import Flask
from db import init_db
from blueprints import auth_bp, admin_bp, user_bp, groups_bp, chat_bp, shorts_bp, report_bp
from extensions import socketio
import socket_events  # register socket handlers

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

# Upload folders
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Initialize Socket.IO with the Flask app
socketio.init_app(app)

init_db()

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)
app.register_blueprint(groups_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(shorts_bp)
app.register_blueprint(report_bp)

# Envuelve tu aplicación Flask con el middleware WSGI/ASGI de socketio para Uvicorn
# Esto crea una aplicación compatible que Uvicorn puede ejecutar correctamente:
app_asgi = socketio.WSGIApp(socketio, app)

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000)