from .auth import auth_bp
from .admin import admin_bp
from .user import user_bp
from .groups import groups_bp
from .chat import chat_bp
from .shorts import shorts_bp

__all__ = [
    "auth_bp",
    "admin_bp",
    "user_bp",
    "groups_bp",
    "chat_bp",
    "shorts_bp",
]
