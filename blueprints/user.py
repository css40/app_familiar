from flask import Blueprint, render_template, request, redirect, session, jsonify
from db import get_db
from helpers import random_filename, safe_save_file

user_bp = Blueprint("user", __name__)


@user_bp.route("/user_home")
def user_home():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT tweets.id, tweets.contenido, tweets.foto, tweets.fecha,
                   users.nombre, users.foto, tweets.user_id
            FROM tweets
            JOIN users ON tweets.user_id = users.id
            ORDER BY tweets.fecha DESC
            """
        )
        tweets = c.fetchall()

        c.execute("SELECT COUNT(*) FROM notificaciones WHERE user_id=? AND leida=0", (user_id,))
        notif_count = c.fetchone()[0]

        tweet_reacciones = {}
        for tweet in tweets:
            tweet_id = tweet[0]
            c.execute(
                """
                SELECT tipo, COUNT(*) FROM tweet_reacciones
                WHERE tweet_id=?
                GROUP BY tipo
                """,
                (tweet_id,),
            )
            tweet_reacciones[tweet_id] = dict(c.fetchall())

    return render_template(
        "user_home.html",
        nombre=session.get("nombre", ""),
        tweets=tweets,
        user_id=user_id,
        tweet_reacciones=tweet_reacciones,
        notif_count=notif_count,
    )


@user_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    if request.method == "POST":
        foto_path = safe_save_file(
            request.files.get("foto"),
            "static/uploads",
            random_filename(),
        )

        fotos_album = request.files.getlist("fotos")
        with get_db() as conn:
            c = conn.cursor()
            for f in fotos_album:
                if f and f.filename:
                    path = safe_save_file(f, "static/uploads", random_filename())
                    c.execute("INSERT INTO user_photos (user_id, foto) VALUES (?, ?)", (user_id, path))
            conn.commit()

        datos = (
            request.form.get("nombre"),
            request.form.get("apellido"),
            request.form.get("email"),
            request.form.get("password"),
            request.form.get("fecha_nac"),
            request.form.get("municipio"),
            request.form.get("pais"),
            request.form.get("telefono"),
            request.form.get("direccion"),
            request.form.get("estado_civil"),
            request.form.get("bio"),
        )

        with get_db() as conn:
            c = conn.cursor()
            if foto_path:
                c.execute(
                    """
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?,
                        telefono=?, direccion=?, estado_civil=?, bio=?, foto=?
                    WHERE id=?
                    """,
                    datos + (foto_path, user_id),
                )
            else:
                c.execute(
                    """
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?,
                        telefono=?, direccion=?, estado_civil=?, bio=?
                    WHERE id=?
                    """,
                    datos + (user_id,),
                )
            conn.commit()

        return redirect("/profile")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (user_id,))
        integrante = c.fetchone()
        c.execute("SELECT foto FROM user_photos WHERE user_id=?", (user_id,))
        fotos = c.fetchall()

    return render_template("profile.html", integrante=integrante, fotos=fotos)


@user_bp.route("/member/<int:id>")
def member_detail(id):
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (id,))
        integrante = c.fetchone()
        c.execute("SELECT foto FROM user_photos WHERE user_id=?", (id,))
        album = c.fetchall()

    return render_template("member_detail.html", integrante=integrante, album=album)


@user_bp.route("/members_view")
def members_view():
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, nombre, apellido, email, municipio, pais, foto FROM users"
        )
        integrantes = c.fetchall()

    return render_template("members_view.html", integrantes=integrantes)


@user_bp.route("/post_tweet", methods=["POST"])
def post_tweet():
    if "user_id" not in session:
        return redirect("/login")

    contenido = request.form.get("contenido")
    foto_path = safe_save_file(
        request.files.get("foto"),
        "static/uploads",
        random_filename(),
    )

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO tweets (user_id, contenido, foto) VALUES (?, ?, ?)",
            (session["user_id"], contenido, foto_path),
        )
        conn.commit()

    return redirect("/user_home")


@user_bp.route("/editar_tweet/<int:id>", methods=["GET", "POST"])
def editar_tweet(id):
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, contenido FROM tweets WHERE id=?", (id,))
        tweet = c.fetchone()

    if not tweet:
        return "Tweet no encontrado"
    if tweet[0] != session["user_id"] and session["email"] != "jhos@admin.com":
        return "No tienes permiso para editar este tweet"

    if request.method == "POST":
        nuevo_contenido = request.form.get("contenido")
        with get_db() as conn:
            c = conn.cursor()
            c.execute("UPDATE tweets SET contenido=? WHERE id=?", (nuevo_contenido, id))
            conn.commit()
        return redirect("/user_home")

    return render_template("editar_tweet.html", contenido=tweet[1])


@user_bp.route("/eliminar_tweet/<int:id>")
def eliminar_tweet(id):
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM tweets WHERE id=?", (id,))
        tweet = c.fetchone()

    if not tweet:
        return "Tweet no encontrado"
    if tweet[0] != session["user_id"] and session["email"] != "jhos@admin.com":
        return "No tienes permiso para eliminar este tweet"

    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM tweets WHERE id=?", (id,))
        conn.commit()

    return redirect("/user_home")


@user_bp.route("/reaccion/<int:tweet_id>/<tipo>")
def reaccion(tweet_id, tipo):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM tweet_reacciones WHERE tweet_id=? AND user_id=?",
            (tweet_id, user_id),
        )
        existente = c.fetchone()

        if existente:
            c.execute(
                "UPDATE tweet_reacciones SET tipo=? WHERE id=?",
                (tipo, existente[0]),
            )
        else:
            c.execute(
                "INSERT INTO tweet_reacciones (tweet_id, user_id, tipo) VALUES (?, ?, ?)",
                (tweet_id, user_id, tipo),
            )
        conn.commit()

    return redirect("/user_home")


@user_bp.route("/reaccion_ajax", methods=["POST"])
def reaccion_ajax():
    if "user_id" not in session:
        return {"status": "error", "msg": "No logueado"}, 401

    data = request.json
    tweet_id = data.get("tweet_id")
    tipo = data.get("tipo")
    user_id = session["user_id"]

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM tweet_reacciones WHERE tweet_id=? AND user_id=?",
            (tweet_id, user_id),
        )
        existente = c.fetchone()
        if existente:
            c.execute(
                "UPDATE tweet_reacciones SET tipo=? WHERE id=?",
                (tipo, existente[0]),
            )
        else:
            c.execute(
                "INSERT INTO tweet_reacciones (tweet_id, user_id, tipo) VALUES (?, ?, ?)",
                (tweet_id, user_id, tipo),
            )
        conn.commit()

        c.execute(
            "SELECT tipo, COUNT(*) FROM tweet_reacciones WHERE tweet_id=? GROUP BY tipo",
            (tweet_id,),
        )
        reacciones = dict(c.fetchall())

    return {"status": "ok", "reacciones": reacciones}


@user_bp.route("/usuarios_json")
def usuarios_json():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT nombre FROM users")
        usuarios = [row[0] for row in c.fetchall()]
    return {"usuarios": usuarios}


@user_bp.route('/tweet/<int:tweet_id>/comments')
def tweet_comments(tweet_id):
    if 'user_id' not in session:
        return jsonify({'status': 'noauth'}), 401

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT pc.id, pc.texto, pc.created_at, u.id, u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,'') "
            "FROM post_comments pc JOIN users u ON u.id = pc.user_id WHERE pc.post_id = ? ORDER BY pc.id ASC",
            (tweet_id,),
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


@user_bp.post('/tweet/<int:tweet_id>/comment')
def tweet_add_comment(tweet_id):
    if 'user_id' not in session:
        return jsonify({'status': 'noauth'}), 401

    user_id = session['user_id']
    texto = (request.form.get('texto') or '').strip()
    if not texto:
        return jsonify({'status': 'empty'}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT user_id FROM tweets WHERE id=?', (tweet_id,))
        row = c.fetchone()
        autor_id = row[0] if row else None

        c.execute('INSERT INTO post_comments (post_id, user_id, texto) VALUES (?, ?, ?)', (tweet_id, user_id, texto))
        notif_id = None
        if autor_id and autor_id != user_id:
            mensaje = 'comentó en tu tweet'
            c.execute(
                "INSERT INTO notificaciones (user_id, actor_id, tipo, ref_id, mensaje) VALUES (?, ?, 'comment', ?, ?)",
                (autor_id, user_id, tweet_id, mensaje),
            )
            notif_id = c.lastrowid

        conn.commit()

        # Emit realtime events
        try:
            from extensions import socketio
            c.execute('SELECT nombre, apellido, foto FROM users WHERE id=?', (user_id,))
            u = c.fetchone()
            actor = {'id': user_id, 'nombre': (u[0] or '') if u else '', 'apellido': (u[1] or '') if u else '', 'foto': (u[2] or '') if u else ''}
            if autor_id and autor_id != user_id:
                payload = {'notif_id': notif_id, 'user_id': autor_id, 'actor': actor, 'tweet_id': tweet_id, 'mensaje': mensaje, 'tipo': 'comment'}
                socketio.emit('new_notification', payload, room=f'user_{autor_id}')

            comment_payload = {'tweet_id': tweet_id, 'texto': texto, 'actor': actor}
            socketio.emit('new_tweet_comment', comment_payload, broadcast=True)
        except Exception:
            pass

    return jsonify({'status': 'ok'})


@user_bp.route("/notificaciones")
def ver_notificaciones():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT n.id, n.mensaje, n.created_at, u.nombre, u.apellido, COALESCE(u.foto, '')
            FROM notificaciones n
            JOIN users u ON u.id = n.actor_id
            WHERE n.user_id = ?
            ORDER BY n.id DESC
            """,
            (user_id,),
        )
        notificaciones = c.fetchall()
        c.execute("UPDATE notificaciones SET leida=1 WHERE user_id=?", (user_id,))
        conn.commit()

    return render_template("notificaciones.html", notificaciones=notificaciones)


@user_bp.post("/notificaciones/marcar_todo")
def marcar_todo_notificaciones():
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE notificaciones SET leida=1 WHERE user_id=?", (session["user_id"],))
        conn.commit()

    return redirect("/notificaciones")


@user_bp.post("/notificaciones/<int:noti_id>/eliminar")
def eliminar_notificacion(noti_id):
    if "user_id" not in session:
        return ("noauth", 401)

    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM notificaciones WHERE id=? AND user_id=?", (noti_id, session["user_id"]))
        conn.commit()

    return ("ok", 200)


@user_bp.route('/api/notificaciones/count')
def api_notif_count():
    if 'user_id' not in session:
        return jsonify({'count': 0})

    user_id = session['user_id']
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM notificaciones WHERE user_id=? AND leida=0', (user_id,))
        count = c.fetchone()[0]

    return jsonify({'count': count})


@user_bp.route('/api/notificaciones/latest')
def api_notif_latest():
    if 'user_id' not in session:
        return jsonify({'notificaciones': []})

    user_id = session['user_id']
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT n.id, n.mensaje, n.created_at, u.nombre, u.apellido FROM notificaciones n JOIN users u ON u.id=n.actor_id WHERE n.user_id=? ORDER BY n.id DESC LIMIT 10",
            (user_id,)
        )
        rows = c.fetchall()

    notis = []
    for nid, mensaje, created_at, nombre, apellido in rows:
        notis.append({'id': nid, 'mensaje': mensaje, 'created_at': created_at, 'actor': f"{nombre} {apellido}".strip()})

    return jsonify({'notificaciones': notis})
