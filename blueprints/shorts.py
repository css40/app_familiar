from flask import Blueprint, render_template, request, redirect, session, jsonify
from db import get_db
from helpers import allowed_short_extension, es_miembro, random_filename, safe_save_file

shorts_bp = Blueprint("shorts", __name__)


@shorts_bp.route("/shorts")
def shorts_feed():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT grupo_id FROM grupos_miembros WHERE user_id=?", (user_id,))
        mis_grupos = [r[0] for r in c.fetchall()]

        if not mis_grupos:
            shorts = []
        else:
            placeholders = ",".join(["?"] * len(mis_grupos))
            c.execute(
                f"""
                SELECT s.id, s.video, COALESCE(s.descripcion,''), s.fecha,
                       u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,''),
                       g.nombre,
                       (SELECT COUNT(*) FROM short_likes WHERE short_id=s.id) AS likes
                FROM shorts s
                JOIN users u ON u.id = s.user_id
                JOIN grupos g ON g.id = s.grupo_id
                WHERE s.grupo_id IN ({placeholders})
                ORDER BY s.id DESC
                LIMIT 80
                """,
                mis_grupos,
            )
            shorts = c.fetchall()

    return render_template("shorts_feed.html", shorts=shorts)


@shorts_bp.route("/shorts/upload", methods=["GET", "POST"])
def shorts_upload():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT g.id, g.nombre
            FROM grupos g
            JOIN grupos_miembros gm ON gm.grupo_id = g.id
            WHERE gm.user_id=?
            ORDER BY g.id DESC
            """,
            (user_id,),
        )
        mis_grupos = c.fetchall()

    if request.method == "GET":
        return render_template("shorts_upload.html", grupos=mis_grupos)

    grupo_id = int(request.form.get("grupo_id"))
    desc = (request.form.get("descripcion") or "").strip()
    f = request.files.get("video")

    if not f or not f.filename:
        return "Subí un video"
    if not allowed_short_extension(f.filename):
        return "Formato inválido (mp4/webm/mov)"

    with get_db() as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return "No eres miembro de ese grupo", 403

    video_rel = safe_save_file(f, "static/uploads/shorts", random_filename())
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO shorts (grupo_id, user_id, video, descripcion) VALUES (?,?,?,?)",
            (grupo_id, user_id, video_rel, desc),
        )
        conn.commit()

    return redirect("/shorts")


@shorts_bp.post("/shorts/<int:short_id>/like")
def short_like(short_id):
    if "user_id" not in session:
        return jsonify({"status": "noauth"}), 401

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT grupo_id FROM shorts WHERE id=?", (short_id,))
        row = c.fetchone()
        if not row:
            return jsonify({"status": "notfound"}), 404

        grupo_id = row[0]
        if not es_miembro(conn, grupo_id, user_id):
            return jsonify({"status": "forbidden"}), 403

        c.execute("SELECT 1 FROM short_likes WHERE short_id=? AND user_id=?", (short_id, user_id))
        if c.fetchone():
            c.execute("DELETE FROM short_likes WHERE short_id=? AND user_id=?", (short_id, user_id))
            liked = False
        else:
            c.execute(
                "INSERT OR IGNORE INTO short_likes (short_id, user_id) VALUES (?,?)",
                (short_id, user_id),
            )
            liked = True

        c.execute("SELECT COUNT(*) FROM short_likes WHERE short_id=?", (short_id,))
        likes = c.fetchone()[0]
        conn.commit()

    return jsonify({"status": "ok", "liked": liked, "likes": likes})


@shorts_bp.route('/shorts/<int:short_id>/comments')
def short_comments(short_id):
    if 'user_id' not in session:
        return jsonify({'status': 'noauth'}), 401

    with get_db() as conn:
        c = conn.cursor()
        # Some databases may have different timestamp column names (fecha vs created_at).
        c.execute("PRAGMA table_info(short_comments)")
        cols = [r[1] for r in c.fetchall()]
        time_col = None
        if 'fecha' in cols:
            time_col = 'fecha'
        elif 'created_at' in cols:
            time_col = 'created_at'

        select_time = f", sc.{time_col}" if time_col else ""

        query = f"""
            SELECT sc.id, sc.texto{select_time}, u.id, u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,'')
            FROM short_comments sc
            JOIN users u ON u.id = sc.user_id
            WHERE sc.short_id = ?
            ORDER BY sc.id ASC
            """

        c.execute(query, (short_id,))
        rows = c.fetchall()

    comments = []
    for row in rows:
        # row layout: id, texto, [time?], uid, nombre, apellido, foto
        if time_col:
            cid, texto, fecha, uid, nombre, apellido, foto = row
            created_at = fecha
        else:
            cid, texto, uid, nombre, apellido, foto = row
            created_at = None

        comments.append({
            'id': cid,
            'texto': texto,
            'created_at': created_at,
            'user_id': uid,
            'nombre': f"{nombre} {apellido}".strip(),
            'avatar': ('/' + foto.replace('\\','/')) if foto else '/static/default_user.png'
        })

    return jsonify({'comments': comments})


@shorts_bp.post('/shorts/<int:short_id>/comment')
def short_add_comment(short_id):
    if 'user_id' not in session:
        return jsonify({'status': 'noauth'}), 401

    user_id = session['user_id']
    texto = (request.form.get('texto') or '').strip()
    if not texto:
        return jsonify({'status': 'empty'}), 400

    with get_db() as conn:
        c = conn.cursor()
        # verificar miembro del grupo del short
        c.execute('SELECT grupo_id, user_id FROM shorts WHERE id=?', (short_id,))
        row = c.fetchone()
        if not row:
            return jsonify({'status': 'notfound'}), 404
        grupo_id, autor_id = row
        if not es_miembro(conn, grupo_id, user_id):
            return jsonify({'status': 'forbidden'}), 403

        c.execute('INSERT INTO short_comments (short_id, user_id, texto) VALUES (?, ?, ?)', (short_id, user_id, texto))

        notif_id = None
        if autor_id and autor_id != user_id:
            mensaje = 'comentó en tu short'
            c.execute(
                "INSERT INTO notificaciones (user_id, actor_id, tipo, ref_id, mensaje) VALUES (?, ?, 'comment', ?, ?)",
                (autor_id, user_id, short_id, mensaje),
            )
            notif_id = c.lastrowid

        conn.commit()

        # Emit realtime events
        try:
            from extensions import socketio
            c.execute('SELECT nombre, apellido, foto FROM users WHERE id=?', (user_id,))
            u = c.fetchone()
            actor = {'id': user_id, 'nombre': (u[0] or '') if u else '', 'apellido': (u[1] or '') if u else '', 'foto': (u[2] or '') if u else ''}
            payload = {'notif_id': notif_id, 'user_id': autor_id, 'actor': actor, 'short_id': short_id, 'mensaje': mensaje, 'tipo': 'comment'}
            socketio.emit('new_notification', payload, room=f'user_{autor_id}')
            comment_payload = {'short_id': short_id, 'texto': texto, 'actor': actor}
            socketio.emit('new_short_comment', comment_payload, broadcast=True)
        except Exception:
            pass

    return jsonify({'status': 'ok'})
