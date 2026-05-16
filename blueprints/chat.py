from flask import Blueprint, render_template, request, redirect, session, jsonify
from db import get_db
from helpers import es_miembro, get_or_create_conv, random_filename, safe_save_file, user_in_conv

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/buscar_usuario")
def buscar_usuario():
    if "user_id" not in session:
        return redirect("/login")

    q = (request.args.get("q") or "").strip()
    user_id = session["user_id"]
    resultados = []

    if q:
        like = f"%{q}%"
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT id, nombre, apellido, COALESCE(email,''), COALESCE(foto,'')
                FROM users
                WHERE id != ?
                  AND (nombre LIKE ? OR apellido LIKE ? OR email LIKE ?)
                ORDER BY nombre ASC
                LIMIT 30
                """,
                (user_id, like, like, like),
            )
            resultados = c.fetchall()

    return render_template("buscar_usuario.html", q=q, resultados=resultados)


@chat_bp.route("/dm/<int:other_id>")
def dm_chat(other_id):
    if "user_id" not in session:
        return redirect("/login")

    me = session["user_id"]
    if me == other_id:
        return redirect("/inbox")

    with get_db() as conn:
        conv_id = get_or_create_conv(conn, me, other_id)
        c = conn.cursor()
        c.execute("SELECT nombre, apellido FROM users WHERE id=?", (other_id,))
        row = c.fetchone()
        other_name = (f"{row[0]} {row[1]}".strip()) if row else "Usuario"

    return render_template("dm_chat.html", conv_id=conv_id, other_id=other_id, other_name=other_name)


@chat_bp.route("/api/dm/<int:conv_id>/mensajes")
def api_dm_mensajes(conv_id):
    if "user_id" not in session:
        return jsonify({"error": "no_login"}), 401

    me = session["user_id"]
    after_id = int(request.args.get("after_id", 0))

    with get_db() as conn:
        if not user_in_conv(conn, conv_id, me):
            return jsonify({"error": "no_access"}), 403

        c = conn.cursor()
        c.execute(
            """
            SELECT m.id, m.from_id, COALESCE(m.mensaje,''), COALESCE(m.media,''), m.fecha,
                   u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,'')
            FROM mensajes_priv m
            JOIN users u ON u.id = m.from_id
            WHERE m.conv_id=? AND m.id>?
            ORDER BY m.id ASC
            LIMIT 200
            """,
            (conv_id, after_id),
        )
        msgs = [
            {
                "id": mid,
                "from_id": from_id,
                "nombre": f"{nom} {ape}".strip(),
                "mensaje": msg,
                "media": ("/" + media.replace("\\", "/")) if media else "",
                "avatar": ("/" + foto.replace("\\", "/")) if foto else "/static/default_user.png",
                "fecha": fecha,
            }
            for mid, from_id, msg, media, fecha, nom, ape, foto in c.fetchall()
        ]

    return jsonify({"messages": msgs, "me": me})


@chat_bp.route("/api/dm/<int:conv_id>/enviar", methods=["POST"])
def api_dm_enviar(conv_id):
    if "user_id" not in session:
        return jsonify({"error": "no_login"}), 401

    me = session["user_id"]
    mensaje = (request.form.get("mensaje") or "").strip()
    media_path = None
    file = request.files.get("media")

    if file and file.filename:
        media_path = safe_save_file(file, "static/uploads/chat_priv", random_filename())

    if not mensaje and not media_path:
        return jsonify({"status": "empty"}), 200

    with get_db() as conn:
        if not user_in_conv(conn, conv_id, me):
            return jsonify({"error": "no_access"}), 403

        c = conn.cursor()
        c.execute(
            "INSERT INTO mensajes_priv (conv_id, from_id, mensaje, media) VALUES (?,?,?,?)",
            (conv_id, me, mensaje, media_path),
        )
        conn.commit()

    return jsonify({"status": "ok"})


@chat_bp.route("/inbox")
def inbox():
    if "user_id" not in session:
        return redirect("/login")

    me = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT
              conv.id,
              CASE WHEN conv.user1_id=? THEN conv.user2_id ELSE conv.user1_id END as other_id,
              u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,''),
              (SELECT COALESCE(mensaje,'') FROM mensajes_priv mp WHERE mp.conv_id=conv.id ORDER BY mp.id DESC LIMIT 1) as last_msg,
              (SELECT fecha FROM mensajes_priv mp WHERE mp.conv_id=conv.id ORDER BY mp.id DESC LIMIT 1) as last_time
            FROM conversaciones conv
            JOIN users u ON u.id = other_id
            WHERE conv.user1_id=? OR conv.user2_id=?
            ORDER BY COALESCE(last_time, conv.created_at) DESC
            """,
            (me, me, me),
        )
        chats = c.fetchall()

    return render_template("inbox.html", chats=chats)


@chat_bp.route("/api/grupo/<int:grupo_id>/mensajes")
def api_chat_grupo(grupo_id):
    if "user_id" not in session:
        return jsonify({"error": "no_login"}), 401

    user_id = session["user_id"]
    after_id = int(request.args.get("after_id", 0))

    with get_db() as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return jsonify({"error": "no_member"}), 403

        c = conn.cursor()
        c.execute(
            """
            SELECT mg.id, mg.user_id, mg.mensaje, mg.media, mg.fecha,
                   u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,'')
            FROM mensajes_grupo mg
            JOIN users u ON u.id = mg.user_id
            WHERE mg.grupo_id=? AND mg.id>?
            ORDER BY mg.id ASC
            LIMIT 200
            """,
            (grupo_id, after_id),
        )
        msgs = []
        for r in c.fetchall():
            mid, uid, msg, media, fecha, nom, ape, foto = r
            msgs.append({
                "id": mid,
                "user_id": uid,
                "nombre": f"{nom} {ape}".strip(),
                "mensaje": msg or "",
                "media": ("/" + media.replace("\\", "/")) if media else "",
                "avatar": ("/" + foto.replace("\\", "/")) if foto else "/static/default_user.png",
                "fecha": fecha,
            })

    return jsonify({"messages": msgs, "me": user_id})


@chat_bp.route("/api/grupo/<int:grupo_id>/enviar", methods=["POST"])
def api_enviar_grupo(grupo_id):
    if "user_id" not in session:
        return jsonify({"error": "no_login"}), 401

    user_id = session["user_id"]
    mensaje = (request.form.get("mensaje") or "").strip()
    media_path = None
    file = request.files.get("media")

    if file and file.filename:
        media_path = safe_save_file(file, "static/uploads/chat", random_filename())

    if not mensaje and not media_path:
        return jsonify({"status": "empty"}), 200

    with get_db() as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return jsonify({"error": "no_member"}), 403

        c = conn.cursor()
        c.execute(
            "INSERT INTO mensajes_grupo (grupo_id, user_id, mensaje, media) VALUES (?, ?, ?, ?)",
            (grupo_id, user_id, mensaje, media_path),
        )
        conn.commit()

    return jsonify({"status": "ok"})


@chat_bp.route("/grupo/<int:grupo_id>/chat")
def vista_chat_grupo(grupo_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return "No eres miembro de este grupo", 403

        c = conn.cursor()
        c.execute("SELECT nombre FROM grupos WHERE id=?", (grupo_id,))
        g = c.fetchone()
        grupo_nombre = g[0] if g else "Grupo"

    return render_template("chat_grupo.html", grupo_id=grupo_id, grupo_nombre=grupo_nombre)
