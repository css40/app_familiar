from flask import Blueprint, render_template, request, redirect, session, jsonify
from db import get_db
from helpers import es_miembro, random_filename, safe_save_file

groups_bp = Blueprint("groups", __name__)


@groups_bp.route("/grupos")
def grupos():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT g.id, g.nombre, u.nombre, u.apellido, u.foto
            FROM grupos g
            JOIN grupos_miembros gm ON g.id = gm.grupo_id
            JOIN users u ON g.creador_id = u.id
            WHERE gm.user_id = ?
            ORDER BY g.id DESC
            """,
            (user_id,),
        )
        grupos = c.fetchall()

    return render_template("grupos.html", grupos=grupos)


@groups_bp.route("/crear_grupo", methods=["GET", "POST"])
def crear_grupo():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    if request.method == "POST":
        nombre = request.form.get("nombre")
        miembros = request.form.getlist("miembros")
        roles = [request.form.get(key) for key in request.form if key.startswith("roles_")]

        with get_db() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO grupos (nombre, creador_id) VALUES (?, ?)", (nombre, user_id))
            grupo_id = c.lastrowid
            c.execute(
                "INSERT INTO grupos_miembros (grupo_id, user_id, rol) VALUES (?, ?, ?)",
                (grupo_id, user_id, "Creador"),
            )
            for u, r in zip(miembros, roles):
                c.execute(
                    "INSERT INTO grupos_miembros (grupo_id, user_id, rol) VALUES (?, ?, ?)",
                    (grupo_id, int(u), r),
                )
            conn.commit()

        return redirect("/grupos")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, apellido, email FROM users WHERE id != ?", (user_id,))
        usuarios = c.fetchall()

    return render_template("crear_grupo.html", usuarios=usuarios)


@groups_bp.route("/grupo/<int:grupo_id>")
def detalle_grupo(grupo_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT g.nombre, g.creador_id, u.nombre, u.apellido, u.foto
            FROM grupos g
            JOIN users u ON u.id = g.creador_id
            WHERE g.id = ?
            """,
            (grupo_id,),
        )
        grupo = c.fetchone()
        if not grupo:
            return "Grupo no encontrado"

        grupo_nombre, creador_id, creador_nombre, creador_apellido, creador_foto = grupo
        creador_nombre_texto = f"{(creador_nombre or '')} {(creador_apellido or '')}".strip()

        c.execute(
            """
            SELECT gm.user_id, u.nombre, u.apellido, u.foto, gm.rol
            FROM grupos_miembros gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.grupo_id = ?
            """,
            (grupo_id,),
        )
        miembros = c.fetchall()

        c.execute(
            """
            SELECT gp.id, gp.contenido, gp.foto, gp.fecha,
                   u.id, u.nombre, u.apellido, u.foto
            FROM group_posts gp
            JOIN users u ON u.id = gp.user_id
            WHERE gp.grupo_id = ?
            ORDER BY gp.fecha DESC
            """,
            (grupo_id,),
        )
        posts = c.fetchall()

        c.execute(
            """
            SELECT id, nombre, apellido, email
            FROM users
            WHERE id NOT IN (
                SELECT user_id FROM grupos_miembros WHERE grupo_id=?
            )
            """,
            (grupo_id,),
        )
        usuarios_disponibles = [
            {"id": u[0], "nombre": u[1], "apellido": u[2], "email": u[3]}
            for u in c.fetchall()
        ]

    return render_template(
        "grupo_detalle.html",
        grupo_id=grupo_id,
        grupo_nombre=grupo_nombre,
        creador_id=creador_id,
        creador_nombre=creador_nombre_texto,
        creador_foto=creador_foto,
        miembros=miembros,
        posts=posts,
        usuarios_disponibles=usuarios_disponibles,
        user_id=user_id,
    )


@groups_bp.route("/grupo/<int:grupo_id>/agregar", methods=["POST"])
def agregar_miembro_grupo(grupo_id):
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT creador_id FROM grupos WHERE id=?", (grupo_id,))
        row = c.fetchone()
        if not row:
            return "Grupo no encontrado"
        creador_id = row[0]

    if session["user_id"] != creador_id:
        return "No tienes permiso para agregar miembros"

    user_ids = request.form.getlist("usuario_id")
    roles = request.form.getlist("rol")

    if not user_ids:
        return redirect(f"/grupo/{grupo_id}")

    with get_db() as conn:
        c = conn.cursor()
        for uid, r in zip(user_ids, roles):
            c.execute(
                "INSERT OR IGNORE INTO grupos_miembros (grupo_id, user_id, rol) VALUES (?, ?, ?)",
                (grupo_id, int(uid), r),
            )
        conn.commit()

    return redirect(f"/grupo/{grupo_id}")


@groups_bp.route("/grupo/<int:grupo_id>/eliminar/<int:miembro_id>", methods=["POST"])
def eliminar_miembro_grupo(grupo_id, miembro_id):
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "DELETE FROM grupos_miembros WHERE grupo_id=? AND user_id=?",
            (grupo_id, miembro_id),
        )
        conn.commit()

    return redirect(f"/grupo/{grupo_id}")


@groups_bp.route("/grupo/<int:grupo_id>/post", methods=["POST"])
def post_en_grupo(grupo_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    contenido = (request.form.get("contenido") or "").strip()
    foto_path = safe_save_file(
        request.files.get("foto"),
        "static/uploads",
        random_filename(),
    )

    if not contenido and not foto_path:
        return redirect(f"/grupo/{grupo_id}")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM grupos_miembros WHERE grupo_id=? AND user_id=?",
            (grupo_id, user_id),
        )
        if not c.fetchone():
            return "No perteneces a este grupo"

        c.execute(
            "INSERT INTO group_posts (grupo_id, user_id, contenido, foto) VALUES (?, ?, ?, ?)",
            (grupo_id, user_id, contenido, foto_path),
        )
        conn.commit()

    return redirect(f"/grupo/{grupo_id}")


@groups_bp.post("/post/<int:post_id>/like")
def like_post(post_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?", (post_id, user_id))
        existe = c.fetchone()
        if existe:
            c.execute("DELETE FROM post_likes WHERE post_id=? AND user_id=?", (post_id, user_id))
        else:
            c.execute(
                "INSERT OR IGNORE INTO post_likes (post_id, user_id) VALUES (?, ?)",
                (post_id, user_id),
            )
        conn.commit()

    return redirect(request.referrer or "/grupos")


@groups_bp.post("/reaccion_post_ajax")
def reaccion_post_ajax():
    if "user_id" not in session:
        return jsonify({"status": "noauth"}), 401

    data = request.get_json(force=True)
    post_id = int(data.get("post_id"))
    tipo = data.get("tipo")
    if tipo not in ("encanta", "divierte", "enoja"):
        return jsonify({"status": "bad"}), 400

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM group_posts WHERE id=?", (post_id,))
        autor = c.fetchone()
        autor_id = autor[0] if autor else None

        c.execute(
            "SELECT tipo FROM post_reacciones WHERE post_id=? AND user_id=?",
            (post_id, user_id),
        )
        row = c.fetchone()
        accion = None

        if row:
            if row[0] == tipo:
                c.execute(
                    "DELETE FROM post_reacciones WHERE post_id=? AND user_id=?",
                    (post_id, user_id),
                )
                accion = "quitó"
            else:
                c.execute(
                    "UPDATE post_reacciones SET tipo=? WHERE post_id=? AND user_id=?",
                    (tipo, post_id, user_id),
                )
                accion = "cambió"
        else:
            c.execute(
                "INSERT INTO post_reacciones (post_id, user_id, tipo) VALUES (?, ?, ?)",
                (post_id, user_id, tipo),
            )
            accion = "reaccionó"

        if autor_id and autor_id != user_id and accion == "reaccionó":
            mensaje = f"reaccionó {tipo} a tu publicación"
            c.execute(
                "INSERT INTO notificaciones (user_id, actor_id, tipo, ref_id, mensaje) VALUES (?, ?, 'reaccion', ?, ?)",
                (autor_id, user_id, post_id, mensaje),
            )

        conn.commit()
        c.execute(
            "SELECT tipo, COUNT(*) FROM post_reacciones WHERE post_id=? GROUP BY tipo",
            (post_id,),
        )
        rows = c.fetchall()

    conteos = {"encanta": 0, "divierte": 0, "enoja": 0}
    for t, n in rows:
        conteos[t] = n

    return jsonify({"status": "ok", "reacciones": conteos})


@groups_bp.route('/group_post/<int:post_id>/comments')
def group_post_comments(post_id):
    """Return comments for a group post as JSON."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT pc.id, pc.texto, pc.created_at, u.id, u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,'')
            FROM post_comments pc
            JOIN users u ON u.id = pc.user_id
            WHERE pc.post_id = ?
            ORDER BY pc.id ASC
            """,
            (post_id,),
        )
        rows = c.fetchall()

    comments = []
    for cid, texto, created_at, uid, nombre, apellido, foto in rows:
        comments.append({
            'id': cid,
            'texto': texto,
            'created_at': created_at,
            'user_id': uid,
            'nombre': f"{nombre} {apellido}".strip(),
            'avatar': ('/' + foto.replace('\\','/')) if foto else '/static/default_user.png'
        })

    return jsonify({'comments': comments})


@groups_bp.post('/group_post/<int:post_id>/comment')
def group_post_add_comment(post_id):
    if 'user_id' not in session:
        return jsonify({'status': 'noauth'}), 401

    user_id = session['user_id']
    texto = (request.form.get('texto') or '').strip()
    if not texto:
        return jsonify({'status': 'empty'}), 400

    with get_db() as conn:
        c = conn.cursor()
        # insertar comentario
        c.execute(
            "INSERT INTO post_comments (post_id, user_id, texto) VALUES (?, ?, ?)",
            (post_id, user_id, texto),
        )

        # notificar al autor del post si no es el mismo
        c.execute('SELECT user_id FROM group_posts WHERE id=?', (post_id,))
        row = c.fetchone()
        autor_id = row[0] if row else None
        notif_id = None
        if autor_id and autor_id != user_id:
            mensaje = 'comentó en tu publicación'
            c.execute(
                "INSERT INTO notificaciones (user_id, actor_id, tipo, ref_id, mensaje) VALUES (?, ?, 'comment', ?, ?)",
                (autor_id, user_id, post_id, mensaje),
            )
            notif_id = c.lastrowid

        conn.commit()

        # Emit realtime event to the post author
        try:
            from extensions import socketio
            c.execute('SELECT nombre, apellido, foto FROM users WHERE id=?', (user_id,))
            u = c.fetchone()
            actor = {'id': user_id, 'nombre': (u[0] or '') if u else '', 'apellido': (u[1] or '') if u else '', 'foto': (u[2] or '') if u else ''}
            payload = {'notif_id': notif_id, 'user_id': autor_id, 'actor': actor, 'post_id': post_id, 'mensaje': mensaje, 'tipo': 'comment'}
            # send to room of the author
            socketio.emit('new_notification', payload, room=f'user_{autor_id}')

            # emit new_comment to all clients (they will filter by post_id)
            comment_payload = {'post_id': post_id, 'texto': texto, 'actor': actor}
            socketio.emit('new_comment', comment_payload, broadcast=True)
        except Exception:
            pass

    return jsonify({'status': 'ok'})
