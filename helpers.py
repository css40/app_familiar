import os
import uuid
from werkzeug.utils import secure_filename
from db import get_db

ALLOWED_SHORT_EXT = {".mp4", ".webm", ".mov"}


def safe_save_file(file, folder, prefix=None):
    """Save an uploaded file and return a normalized relative path."""
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)
    if prefix:
        filename = f"{prefix}_{filename}"

    os.makedirs(folder, exist_ok=True)
    save_path = os.path.join(folder, filename)
    file.save(save_path)
    return save_path.replace("\\", "/")


def conv_pair(a, b):
    """Return a deterministic order for a 1-to-1 conversation pair."""
    a = int(a)
    b = int(b)
    return (a, b) if a < b else (b, a)


def es_miembro(conn, grupo_id, user_id):
    """Return True if the user belongs to the group."""
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM grupos_miembros WHERE grupo_id=? AND user_id=?",
        (grupo_id, user_id),
    )
    return c.fetchone() is not None


def get_or_create_conv(conn, u1, u2):
    """Return the conversation id for two users, creating it if needed."""
    a, b = conv_pair(u1, u2)
    c = conn.cursor()
    c.execute(
        "SELECT id FROM conversaciones WHERE user1_id=? AND user2_id=?",
        (a, b),
    )
    row = c.fetchone()
    if row:
        return row[0]

    c.execute(
        "INSERT INTO conversaciones (user1_id, user2_id) VALUES (?, ?)",
        (a, b),
    )
    conn.commit()
    return c.lastrowid


def user_in_conv(conn, conv_id, user_id):
    """Return True if the user is participant in the conversation."""
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM conversaciones WHERE id=? AND (user1_id=? OR user2_id=? )",
        (conv_id, user_id, user_id),
    )
    return c.fetchone() is not None


def marcar_activo(user_id, estado):
    """Update the active flag for a user."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET activo = ? WHERE id = ?", (estado, user_id))
        conn.commit()


def allowed_short_extension(filename):
    """Return True if the uploaded short has an allowed video extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_SHORT_EXT


def random_filename(prefix=None):
    """Return a safe random filename prefix."""
    return uuid.uuid4().hex if prefix is None else f"{prefix}_{uuid.uuid4().hex}"
