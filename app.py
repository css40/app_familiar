from flask import Flask, render_template, request, redirect, session , jsonify , abort
import sqlite3
import os
import uuid 
import time
from werkzeug.utils import secure_filename



app = Flask(__name__)
usuarios_activos = set()
app.secret_key = "supersecretkey"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB máximo



def marcar_activo(user_id, estado):
    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET activo = ? WHERE id = ?", (estado, user_id))
        conn.commit()



# Carpeta para subir fotos
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

UPLOAD_SHORTS = os.path.join(app.config['UPLOAD_FOLDER'], 'shorts')
os.makedirs(UPLOAD_SHORTS, exist_ok=True)

ALLOWED_SHORT_EXT = {".mp4", ".webm", ".mov"}


def db():
    return sqlite3.connect("database.db", timeout=20)

def es_miembro(conn, grupo_id, user_id):
    c = conn.cursor()
    c.execute("""
        SELECT 1 FROM grupos_miembros
        WHERE grupo_id=? AND user_id=?
    """, (grupo_id, user_id))
    return c.fetchone() is not None

# carpeta para multimedia del chat
UPLOAD_CHAT = os.path.join(app.config['UPLOAD_FOLDER'], 'chat')
os.makedirs(UPLOAD_CHAT, exist_ok=True)

with sqlite3.connect('database.db') as conn:
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS shorts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grupo_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        video TEXT NOT NULL,
        descripcion TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS short_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        short_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(short_id, user_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS short_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        short_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        texto TEXT NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()


with sqlite3.connect('database.db') as conn:
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS conversaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER NOT NULL,
        user2_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user1_id, user2_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS mensajes_priv (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conv_id INTEGER NOT NULL,
        from_id INTEGER NOT NULL,
        mensaje TEXT,
        media TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        leido INTEGER DEFAULT 0,
        FOREIGN KEY(conv_id) REFERENCES conversaciones(id) ON DELETE CASCADE
    )
    """)

    conn.commit()

UPLOAD_CHAT_PRIV = 'static/uploads/chat_priv'
os.makedirs(UPLOAD_CHAT_PRIV, exist_ok=True)

def conv_pair(a, b):
    a = int(a); b = int(b)
    return (a, b) if a < b else (b, a)

def get_or_create_conv(conn, u1, u2):
    a, b = conv_pair(u1, u2)
    c = conn.cursor()
    c.execute("SELECT id FROM conversaciones WHERE user1_id=? AND user2_id=?", (a, b))
    row = c.fetchone()
    if row:
        return row[0]
    c.execute("INSERT INTO conversaciones (user1_id, user2_id) VALUES (?,?)", (a, b))
    conn.commit()
    return c.lastrowid

def user_in_conv(conn, conv_id, user_id):
    c = conn.cursor()
    c.execute("SELECT 1 FROM conversaciones WHERE id=? AND (user1_id=? OR user2_id=?)", (conv_id, user_id, user_id))
    return c.fetchone() is not None



with sqlite3.connect('database.db') as conn:
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS notificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            ref_id INTEGER,
            mensaje TEXT NOT NULL,
            leida INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(actor_id) REFERENCES users(id)
        )
    """)
    conn.commit()


with sqlite3.connect('database.db') as conn:
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS post_reacciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('encanta','divierte','enoja')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(post_id, user_id, tipo),
        FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
      )
    """)
    conn.commit()

# tabla mensajes_grupo (por si no existe)
with sqlite3.connect('database.db') as conn:
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS mensajes_grupo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            mensaje TEXT,
            media TEXT,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

# --- Crear tabla user_photos si no existe ---
with sqlite3.connect('database.db') as conn:
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            foto TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()


# =====================
# --- RUTAS LOGIN ---
# =====================
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        with sqlite3.connect('database.db', timeout=20) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
            user = c.fetchone()

        if user:
            session['user_id'] = user[0]
            session['nombre'] = user[1]
            session['email'] = user[3]

            # 🔥 AQUÍ MARCAMOS AL USUARIO COMO ACTIVO
            marcar_activo(user[0], 1)

            if email == 'jhos@admin.com':  # Admin
                return redirect('/admin_home')
            else:
                return redirect('/user_home')
        else:
            return "Usuario o contraseña incorrectos"

    return render_template('login.html')



# =====================
# --- RUTA HOME ADMIN ---
# =====================
@app.route('/admin_home')
def admin_home():
    if 'user_id' not in session:
        return redirect('/login')
    nombre_familia = "Family_web"
    
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE activo=1")
        activos = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users")
        total_miembros = c.fetchone()[0]


    return render_template(
        'admin_home.html',
        nombre=session['nombre'],
        total_miembros=total_miembros,
        activos=activos,
        nombre_familia=nombre_familia
    )

@app.route('/post_tweet', methods=['POST'])
def post_tweet():
    if 'user_id' not in session:
        return redirect('/login')

    contenido = request.form.get('contenido')
    foto = request.files.get('foto')
    foto_path = None

    if foto and foto.filename != "":
        filename = secure_filename(foto.filename)
        foto_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        foto.save(foto_path)
        # Guardamos la ruta relativa para mostrar en HTML
        foto_path = foto_path.replace("\\", "/")

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("INSERT INTO tweets (user_id, contenido, foto) VALUES (?, ?, ?)",
                  (session['user_id'], contenido, foto_path))
        conn.commit()

    return redirect('/user_home')


@app.route('/editar_tweet/<int:id>', methods=['GET', 'POST'])
def editar_tweet(id):
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, contenido FROM tweets WHERE id=?", (id,))
        tweet = c.fetchone()

    if not tweet:
        return "Tweet no encontrado"

    if tweet[0] != session['user_id'] and session['email'] != 'jhos@admin.com':
        return "No tienes permiso para editar este tweet"

    if request.method == 'POST':
        nuevo_contenido = request.form.get('contenido')
        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute("UPDATE tweets SET contenido=? WHERE id=?", (nuevo_contenido, id))
            conn.commit()
        return redirect('/user_home')

    return render_template("editar_tweet.html", contenido=tweet[1])

@app.route('/eliminar_tweet/<int:id>')
def eliminar_tweet(id):
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM tweets WHERE id=?", (id,))
        tweet = c.fetchone()

    if not tweet:
        return "Tweet no encontrado"

    if tweet[0] != session['user_id'] and session['email'] != 'jhos@admin.com':
        return "No tienes permiso para eliminar este tweet"

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM tweets WHERE id=?", (id,))
        conn.commit()

    return redirect('/user_home')

@app.route('/reaccion/<int:tweet_id>/<tipo>')
def reaccion(tweet_id, tipo):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        # Ver si ya reaccionó
        c.execute("SELECT * FROM tweet_reacciones WHERE tweet_id=? AND user_id=?", (tweet_id, user_id))
        existente = c.fetchone()

        if existente:
            # Si ya reaccionó, actualizamos el tipo
            c.execute("UPDATE tweet_reacciones SET tipo=? WHERE id=?", (tipo, existente[0]))
        else:
            # Si no ha reaccionado, insertamos
            c.execute("INSERT INTO tweet_reacciones (tweet_id, user_id, tipo) VALUES (?, ?, ?)", 
                      (tweet_id, user_id, tipo))
        conn.commit()

    return redirect('/user_home')



# =====================
# --- AGREGAR USUARIO ---
# =====================
@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    if 'user_id' not in session:
        return redirect('/login')

    # Solo admin puede agregar usuarios
    if session.get('email') != 'jhos@admin.com':
        return "No tienes permiso para agregar usuarios"

    if request.method == 'POST':
        # Guardar foto
        foto = request.files.get('foto')
        foto_path = None

        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
            foto.save(foto_path)
            foto_path = foto_path.replace("\\", "/")

        # Datos del formulario
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        email = request.form.get('email')
        password = request.form.get('password')
        fecha_nac = request.form.get('fecha_nac')
        municipio = request.form.get('municipio')
        pais = request.form.get('pais')

        # Insertar en DB
        with sqlite3.connect('database.db', timeout=20) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO users (nombre, apellido, email, password, fecha_nac, municipio, pais, foto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, apellido, email, password, fecha_nac, municipio, pais, foto_path))
            conn.commit()

        return redirect('/admin_home')

    return render_template('add_member.html')

@app.route('/reaccion_ajax', methods=['POST'])
def reaccion_ajax():
    if 'user_id' not in session:
        return {"status": "error", "msg": "No logueado"}, 401

    data = request.json
    tweet_id = data.get("tweet_id")
    tipo = data.get("tipo")
    user_id = session['user_id']

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        # Ver si ya reaccionó
        c.execute("SELECT * FROM tweet_reacciones WHERE tweet_id=? AND user_id=?", (tweet_id, user_id))
        existente = c.fetchone()
        if existente:
            c.execute("UPDATE tweet_reacciones SET tipo=? WHERE id=?", (tipo, existente[0]))
        else:
            c.execute("INSERT INTO tweet_reacciones (tweet_id, user_id, tipo) VALUES (?, ?, ?)", (tweet_id, user_id, tipo))
        conn.commit()

        # Contamos de nuevo para devolver al front
        c.execute("SELECT tipo, COUNT(*) FROM tweet_reacciones WHERE tweet_id=? GROUP BY tipo", (tweet_id,))
        reacciones = dict(c.fetchall())

    return {"status": "ok", "reacciones": reacciones}

@app.route('/usuarios_json')
def usuarios_json():
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT nombre FROM users")
        usuarios = [row[0] for row in c.fetchall()]
    return {"usuarios": usuarios}



# =====================
# --- RUTA HOME USUARIO ---
# =====================
@app.route('/user_home')
def user_home():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']  # ✅ ahora sí existe

    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()
        
        # 1️⃣ Traemos todos los tweets
        c.execute("""
            SELECT tweets.id, tweets.contenido, tweets.foto, tweets.fecha,
                   users.nombre, users.foto, tweets.user_id
            FROM tweets
            JOIN users ON tweets.user_id = users.id
            ORDER BY tweets.fecha DESC
        """)
        tweets = c.fetchall()

        # ✅ contador notificaciones no leídas
        c.execute("SELECT COUNT(*) FROM notificaciones WHERE user_id=? AND leida=0", (user_id,))
        notif_count = c.fetchone()[0]  # ✅ ahora se llama igual que en el template

        # 2️⃣ Contamos reacciones para cada tweet
        tweet_reacciones = {}
        for tweet in tweets:
            tweet_id = tweet[0]
            c.execute("""
                SELECT tipo, COUNT(*) FROM tweet_reacciones
                WHERE tweet_id=?
                GROUP BY tipo
            """, (tweet_id,))
            tweet_reacciones[tweet_id] = dict(c.fetchall())

    # 3️⃣ Renderizamos la plantilla
    return render_template(
        "user_home.html",
        nombre=session.get('nombre', ''),
        tweets=tweets,
        user_id=user_id,
        tweet_reacciones=tweet_reacciones,
        notif_count=notif_count
    )


# =====================
# --- LOGOUT ---
# =====================
@app.route('/logout')
def logout():
    user_id = session.get('user_id')

    if user_id:
        marcar_activo(user_id, 0)   # 🔥 lo ponemos inactivo

    session.clear()
    return redirect('/login')



# =====================
# --- VER TODOS LOS USUARIOS (ADMIN) ---
# =====================
@app.route('/members')
def members():
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, apellido, email,  password, foto FROM users WHERE email != 'jhos@admin.com'")
        integrantes = c.fetchall()

    return render_template('members.html', integrantes=integrantes)


# =====================
# --- ELIMINAR USUARIO (ADMIN) ---
# =====================
@app.route('/delete_member/<int:id>')
def delete_member(id):
    if 'user_id' not in session:
        return redirect('/login')

    if session.get('email') != 'jhos@admin.com':
        return "No tienes permiso para eliminar usuarios"

    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id=? AND email != 'jhos@admin.com'", (id,))
        conn.commit()

    return redirect('/members')


# =====================
# --- EDITAR USUARIO ---
# =====================
@app.route('/edit_member/<int:id>', methods=['GET', 'POST'])
def edit_member(id):
    if 'user_id' not in session:
        return redirect('/login')

    if session.get('email') != 'jhos@admin.com':
        return "No tienes permiso para editar otros usuarios"

    if request.method == 'POST':
        foto = request.files.get('foto')
        foto_path = None

        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
            foto.save(foto_path)
            foto_path = foto_path.replace("\\", "/")

        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        email = request.form.get('email')
        password = request.form.get('password')
        fecha_nac = request.form.get('fecha_nac')
        municipio = request.form.get('municipio')
        pais = request.form.get('pais')

        with sqlite3.connect('database.db', timeout=20) as conn:
            c = conn.cursor()

            if foto_path:
                c.execute('''
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?, foto=?
                    WHERE id=?
                ''', (nombre, apellido, email, password, fecha_nac, municipio, pais, foto_path, id))
            else:
                c.execute('''
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?
                    WHERE id=?
                ''', (nombre, apellido, email, password, fecha_nac, municipio, pais, id))

            conn.commit()

        return redirect('/members')

    # GET
    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (id,))
        integrante = c.fetchone()

    return render_template('edit_member.html', integrante=integrante)


# =====================
# --- VER USUARIOS (solo lectura) ---
# =====================
@app.route('/members_view')
def members_view():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nombre, apellido, email, municipio, pais, foto
            FROM users
        """)

        integrantes = c.fetchall()

    return render_template('members_view.html', integrantes=integrantes)



# =====================
# --- PERFIL PROPIO ---
# =====================
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if request.method == 'POST':

        # --- Subir foto principal ---
        foto = request.files.get('foto')
        foto_path = None

        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            foto_path = os.path.join(
                app.config['UPLOAD_FOLDER'],
                f"{uuid.uuid4()}_{filename}"
            )
            foto.save(foto_path)
            foto_path = foto_path.replace("\\", "/")

        # --- Subir fotos adicionales (álbum) ---
        fotos_album = request.files.getlist('fotos')
        with sqlite3.connect('database.db', timeout=20) as conn:
            c = conn.cursor()
            for f in fotos_album:
                if f and f.filename != '':
                    filename_album = secure_filename(f.filename)
                    path = os.path.join(
                        app.config['UPLOAD_FOLDER'],
                        f"{uuid.uuid4()}_{filename_album}"
                    )
                    f.save(path)
                    path = path.replace("\\", "/")
                    c.execute(
                        "INSERT INTO user_photos (user_id, foto) VALUES (?, ?)",
                        (user_id, path)
                    )
            conn.commit()

        # --- Datos del formulario ---
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        email = request.form['email']
        password = request.form['password']
        fecha_nac = request.form['fecha_nac']
        municipio = request.form['municipio']
        pais = request.form['pais']
        telefono = request.form['telefono']
        direccion = request.form['direccion']
        estado_civil = request.form['estado_civil']
        bio = request.form['bio']

        # --- Actualizar DB principal ---
        with sqlite3.connect('database.db', timeout=20) as conn:
            c = conn.cursor()
            if foto_path:
                c.execute('''
                    UPDATE users 
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?,
                        telefono=?, direccion=?, estado_civil=?, bio=?, foto=?
                    WHERE id=?
                ''', (
                    nombre, apellido, email, password, fecha_nac, municipio, pais,
                    telefono, direccion, estado_civil, bio, foto_path, user_id
                ))
            else:
                c.execute('''
                    UPDATE users 
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?,
                        telefono=?, direccion=?, estado_civil=?, bio=?
                    WHERE id=?
                ''', (
                    nombre, apellido, email, password, fecha_nac, municipio, pais,
                    telefono, direccion, estado_civil, bio, user_id
                ))
            conn.commit()

        return redirect('/profile')

    # --- GET: mostrar datos actuales ---
    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (user_id,))
        integrante = c.fetchone()

        c.execute("SELECT foto FROM user_photos WHERE user_id=?", (user_id,))
        fotos = c.fetchall()

    return render_template('profile.html', integrante=integrante, fotos=fotos)


@app.route('/member/<int:id>')
def member_detail(id):
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE id=?", (id,))
        integrante = c.fetchone()

        c.execute("SELECT foto FROM user_photos WHERE user_id=?", (id,))
        album = c.fetchall()

    return render_template('member_detail.html', integrante=integrante, album=album)

@app.route('/grupos')
def grupos():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        # Traemos todos los grupos donde el usuario es miembro
        c.execute("""
            SELECT g.id, g.nombre, u.nombre, u.apellido, u.foto
            FROM grupos g
            JOIN grupos_miembros gm ON g.id = gm.grupo_id
            JOIN users u ON g.creador_id = u.id
            WHERE gm.user_id = ?
            ORDER BY g.id DESC
        """, (user_id,))

        grupos = c.fetchall()

    return render_template("grupos.html", grupos=grupos)



@app.route('/crear_grupo', methods=['GET', 'POST'])
def crear_grupo():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        miembros = request.form.getlist('miembros')  # lista de user_ids
        roles = []

        # Recolectar roles dinámicamente
        for key in request.form:
            if key.startswith("roles_"):
                roles.append(request.form.get(key))

        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            
            # Crear grupo
            c.execute("INSERT INTO grupos (nombre, creador_id) VALUES (?, ?)", (nombre, user_id))
            grupo_id = c.lastrowid

            # Agregar creador automáticamente
            c.execute("INSERT INTO grupos_miembros (grupo_id, user_id, rol) VALUES (?, ?, ?)",
                      (grupo_id, user_id, "Creador"))

            # Agregar miembros con roles
            for u, r in zip(miembros, roles):
                c.execute("""
                    INSERT INTO grupos_miembros (grupo_id, user_id, rol)
                    VALUES (?, ?, ?)
                """, (grupo_id, int(u), r))

            
            conn.commit()

        return redirect("/grupos")

    # GET → enviar todos los usuarios a JS para búsqueda dinámica
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, apellido, email FROM users WHERE id != ?", (user_id,))
        usuarios = c.fetchall()

    # Pasamos usuarios como JSON para JS
    return render_template("crear_grupo.html", usuarios=usuarios)

@app.route("/grupo/<int:grupo_id>/ver")
def ver_grupo(grupo_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()

        # ✅ Info del grupo
        c.execute("SELECT nombre, creador_id FROM grupos WHERE id=?", (grupo_id,))
        grupo = c.fetchone()
        if not grupo:
            return redirect("/grupos")

        grupo_nombre, creador_id = grupo

        # ✅ Miembros del grupo (id, nombre, apellido, foto, rol)
        c.execute("""
            SELECT
                u.id,
                u.nombre,
                u.apellido,
                COALESCE(u.foto, '') AS foto,
                COALESCE(gm.rol, 'miembro') AS rol
            FROM grupos_miembros gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.grupo_id = ?
            ORDER BY
              CASE WHEN u.id = ? THEN 0 ELSE 1 END,
              CASE WHEN u.id = ? THEN 0 ELSE 1 END,
              u.nombre ASC
        """, (grupo_id, creador_id, user_id))
        miembros = c.fetchall()

        # ✅ Feed del grupo (posts)
        c.execute("""
            SELECT
                p.id,
                p.contenido,
                COALESCE(p.foto, '') AS foto_post,
                p.fecha,
                u.nombre,
                u.apellido,
                COALESCE(u.foto, '') AS foto_user
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE p.grupo_id = ?
            ORDER BY p.id DESC
        """, (grupo_id,))
        posts = c.fetchall()

        # ✅ Reacciones por post (dict igual que tweet_reacciones)
        c.execute("""
            SELECT pr.post_id, pr.tipo, COUNT(*) as cnt
            FROM post_reacciones pr
            JOIN posts p ON p.id = pr.post_id
            WHERE p.grupo_id = ?
            GROUP BY pr.post_id, pr.tipo
        """, (grupo_id,))
        rows = c.fetchall()

        post_reacciones = {}
        for post_id, tipo, cnt in rows:
            post_reacciones.setdefault(post_id, {})[tipo] = cnt

        # ✅ Usuarios disponibles para agregar al grupo
        c.execute("""
            SELECT id, nombre, apellido, COALESCE(email,'') as email
            FROM users
            WHERE id NOT IN (
                SELECT user_id FROM grupos_miembros WHERE grupo_id=?
            )
        """, (grupo_id,))
        usuarios_disponibles = c.fetchall()

    return render_template(
        "grupo_detalle.html",
        grupo_id=grupo_id,
        grupo_nombre=grupo_nombre,
        creador_id=creador_id,
        user_id=user_id,
        miembros=miembros,
        posts=posts,
        usuarios_disponibles=usuarios_disponibles,
        post_reacciones=post_reacciones
    )


@app.route('/grupo/<int:grupo_id>', methods=['GET', 'POST'])
def detalle_grupo(grupo_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()

        # ✅ Grupo + datos del creador (incluye foto)
        c.execute("""
            SELECT g.nombre, g.creador_id, u.nombre, u.apellido, u.foto
            FROM grupos g
            JOIN users u ON u.id = g.creador_id
            WHERE g.id = ?
        """, (grupo_id,))
        grupo = c.fetchone()

        if not grupo:
            return "Grupo no encontrado"

        grupo_nombre = grupo[0]
        creador_id = grupo[1]
        creador_nombre = f"{(grupo[2] or '')} {(grupo[3] or '')}".strip()
        creador_foto = grupo[4]

        # ✅ Miembros del grupo (incluye foto)
        c.execute("""
            SELECT gm.user_id, u.nombre, u.apellido, u.foto, gm.rol
            FROM grupos_miembros gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.grupo_id = ?
        """, (grupo_id,))
        miembros = c.fetchall()

        # ✅ POSTS DEL GRUPO (FEED)  <<<<<< AQUÍ VA
        c.execute("""
            SELECT gp.id, gp.contenido, gp.foto, gp.fecha,
                   u.id, u.nombre, u.apellido, u.foto
            FROM group_posts gp
            JOIN users u ON u.id = gp.user_id
            WHERE gp.grupo_id = ?
            ORDER BY gp.fecha DESC
        """, (grupo_id,))
        posts = c.fetchall()

        # ✅ Usuarios disponibles para agregar
        c.execute("""
            SELECT id, nombre, apellido, email
            FROM users
            WHERE id NOT IN (
                SELECT user_id FROM grupos_miembros WHERE grupo_id=?
            )
        """, (grupo_id,))
        usuarios_disponibles = c.fetchall()

        usuarios_disponibles = [
            {"id": u[0], "nombre": u[1], "apellido": u[2], "email": u[3]}
            for u in usuarios_disponibles
        ]

    print("DEBUG grupo =>", grupo)
    print("DEBUG creador_foto =>", creador_foto)

    return render_template(
        "grupo_detalle.html",
        grupo_id=grupo_id,
        grupo_nombre=grupo_nombre,
        creador_id=creador_id,
        creador_nombre=creador_nombre,
        creador_foto=creador_foto,
        miembros=miembros,
        posts=posts,  # ✅ AQUI VA EN EL TEMPLATE
        usuarios_disponibles=usuarios_disponibles,
        user_id=user_id
    )


@app.route('/grupo/<int:grupo_id>/agregar', methods=['POST'])
def agregar_miembro_grupo(grupo_id):
    if 'user_id' not in session:
        return redirect('/login')

    # ✅ Solo el creador puede agregar (opcional pero recomendado)
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT creador_id FROM grupos WHERE id=?", (grupo_id,))
        row = c.fetchone()
        if not row:
            return "Grupo no encontrado"
        creador_id = row[0]

    if session['user_id'] != creador_id:
        return "No tienes permiso para agregar miembros"

    # ✅ Leer TODOS los seleccionados
    user_ids = request.form.getlist('usuario_id')
    roles = request.form.getlist('rol')

    if not user_ids:
        return redirect(f"/grupo/{grupo_id}")

    # ✅ Insertar (evita duplicados)
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        for uid, r in zip(user_ids, roles):
            c.execute("""
                INSERT OR IGNORE INTO grupos_miembros (grupo_id, user_id, rol)
                VALUES (?, ?, ?)
            """, (grupo_id, int(uid), r))
        conn.commit()

    return redirect(f"/grupo/{grupo_id}")


@app.route('/grupo/<int:grupo_id>/eliminar/<int:miembro_id>', methods=['POST'])
def eliminar_miembro_grupo(grupo_id, miembro_id):
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM grupos_miembros WHERE grupo_id=? AND user_id=?", (grupo_id, miembro_id))
        conn.commit()

    return redirect(f"/grupo/{grupo_id}")

@app.route('/grupo/<int:grupo_id>/post', methods=['POST'])
def post_en_grupo(grupo_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    contenido = (request.form.get('contenido') or "").strip()
    foto = request.files.get('foto')

    foto_path = None
    if foto and foto.filename != '':
        filename = secure_filename(foto.filename)
        foto_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
        foto.save(foto_path)
        foto_path = foto_path.replace("\\", "/")  # guardas tipo static/uploads/...

    # Validación mínima: que no publique vacío (sin texto y sin foto)
    if not contenido and not foto_path:
        return redirect(f"/grupo/{grupo_id}")

    # (Opcional pero recomendado) verificar que el usuario sea miembro del grupo
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 1 FROM grupos_miembros
            WHERE grupo_id=? AND user_id=?
        """, (grupo_id, user_id))
        es_miembro = c.fetchone()
        if not es_miembro:
            return "No perteneces a este grupo"

        c.execute("""
            INSERT INTO group_posts (grupo_id, user_id, contenido, foto)
            VALUES (?, ?, ?, ?)
        """, (grupo_id, user_id, contenido, foto_path))
        conn.commit()

    return redirect(f"/grupo/{grupo_id}")


@app.post("/post/<int:post_id>/like")
def like_post(post_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()

        c.execute("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?", (post_id, user_id))
        existe = c.fetchone()

        if existe:
            c.execute("DELETE FROM post_likes WHERE post_id=? AND user_id=?", (post_id, user_id))
        else:
            c.execute("INSERT OR IGNORE INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, user_id))

        conn.commit()

    return redirect(request.referrer or "/grupos")



@app.post("/reaccion_post_ajax")
def reaccion_post_ajax():
    if "user_id" not in session:
        return jsonify({"status": "noauth"}), 401

    data = request.get_json(force=True)
    post_id = int(data.get("post_id"))
    tipo = data.get("tipo")

    if tipo not in ("encanta", "divierte", "enoja"):
        return jsonify({"status": "bad"}), 400

    user_id = session["user_id"]

    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()

        # 🔎 Autor del post
        c.execute("SELECT user_id FROM posts WHERE id=?", (post_id,))
        autor = c.fetchone()
        autor_id = autor[0] if autor else None

        # 🔹 ¿ya reaccionó a este post?
        c.execute("""
            SELECT tipo
            FROM post_reacciones
            WHERE post_id=? AND user_id=?
        """, (post_id, user_id))
        row = c.fetchone()

        accion = None  # para saber si notificamos

        if row:
            if row[0] == tipo:
                # mismo emoji → quitar reacción
                c.execute("""
                    DELETE FROM post_reacciones
                    WHERE post_id=? AND user_id=?
                """, (post_id, user_id))
                accion = "quitó"
            else:
                # emoji distinto → actualizar
                c.execute("""
                    UPDATE post_reacciones
                    SET tipo=?
                    WHERE post_id=? AND user_id=?
                """, (tipo, post_id, user_id))
                accion = "cambió"
        else:
            # no había reacción → insertar
            c.execute("""
                INSERT INTO post_reacciones (post_id, user_id, tipo)
                VALUES (?, ?, ?)
            """, (post_id, user_id, tipo))
            accion = "reaccionó"

        # 🔔 CREAR NOTIFICACIÓN (solo si aplica)
        if autor_id and autor_id != user_id and accion == "reaccionó":
            mensaje = f"reaccionó {tipo} a tu publicación"

            c.execute("""
                INSERT INTO notificaciones (user_id, actor_id, tipo, ref_id, mensaje)
                VALUES (?, ?, 'reaccion', ?, ?)
            """, (autor_id, user_id, post_id, mensaje))

        conn.commit()

        # 🔢 Conteos actualizados
        c.execute("""
            SELECT tipo, COUNT(*)
            FROM post_reacciones
            WHERE post_id=?
            GROUP BY tipo
        """, (post_id,))
        rows = c.fetchall()

    conteos = {"encanta": 0, "divierte": 0, "enoja": 0}
    for t, n in rows:
        conteos[t] = n

    return jsonify({
        "status": "ok",
        "reacciones": conteos
    })


@app.route("/notificaciones")
def ver_notificaciones():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("""
            SELECT
                n.id,
                n.mensaje,
                n.created_at,
                u.nombre,
                u.apellido,
                COALESCE(u.foto, '')
            FROM notificaciones n
            JOIN users u ON u.id = n.actor_id
            WHERE n.user_id = ?
            ORDER BY n.id DESC
        """, (user_id,))
        notificaciones = c.fetchall()

        # marcar como leídas
        c.execute("UPDATE notificaciones SET leida=1 WHERE user_id=?", (user_id,))
        conn.commit()

    return render_template("notificaciones.html", notificaciones=notificaciones)

# =====================
# --- MENSAJES ---
# =====================
@app.route("/api/grupo/<int:grupo_id>/mensajes")
def api_chat_grupo(grupo_id):
    if "user_id" not in session:
        return jsonify({"error": "no_login"}), 401

    user_id = session["user_id"]
    after_id = int(request.args.get("after_id", 0))

    with db() as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return jsonify({"error": "no_member"}), 403

        c = conn.cursor()
        c.execute("""
            SELECT mg.id, mg.user_id, mg.mensaje, mg.media, mg.fecha,
                   u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,'')
            FROM mensajes_grupo mg
            JOIN users u ON u.id = mg.user_id
            WHERE mg.grupo_id=? AND mg.id>?
            ORDER BY mg.id ASC
            LIMIT 200
        """, (grupo_id, after_id))

        msgs = []
        for r in c.fetchall():
            mid, uid, msg, media, fecha, nom, ape, foto = r
            msgs.append({
                "id": mid,
                "user_id": uid,
                "nombre": f"{nom} {ape}".strip(),
                "mensaje": msg or "",
                "media": ("/" + media.replace("\\","/")) if media else "",
                "avatar": ("/" + foto.replace("\\","/")) if foto else "/static/default_user.png",
                "fecha": fecha
            })

    return jsonify({"messages": msgs, "me": user_id})


@app.route("/api/grupo/<int:grupo_id>/enviar", methods=["POST"])
def api_enviar_grupo(grupo_id):
    if "user_id" not in session:
        return jsonify({"error": "no_login"}), 401

    user_id = session["user_id"]

    with db() as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return jsonify({"error": "no_member"}), 403

        mensaje = (request.form.get("mensaje") or "").strip()

        media_path = None
        file = request.files.get("media")
        if file and file.filename:
            filename = secure_filename(file.filename)
            final_name = f"g{grupo_id}_u{user_id}_{int(time.time())}_{filename}"
            save_path = os.path.join(UPLOAD_CHAT, final_name)
            file.save(save_path)

            # GUARDAR RUTA RELATIVA tipo static/uploads/chat/...
            media_path = save_path.replace("\\", "/")

        if not mensaje and not media_path:
            return jsonify({"status": "empty"}), 200

        c = conn.cursor()
        c.execute("""
            INSERT INTO mensajes_grupo (grupo_id, user_id, mensaje, media)
            VALUES (?, ?, ?, ?)
        """, (grupo_id, user_id, mensaje, media_path))
        conn.commit()

    return jsonify({"status": "ok"})



@app.route("/grupo/<int:grupo_id>/chat")
def vista_chat_grupo(grupo_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    with db() as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return "No eres miembro de este grupo", 403

        c = conn.cursor()
        c.execute("SELECT nombre FROM grupos WHERE id=?", (grupo_id,))
        g = c.fetchone()
        grupo_nombre = g[0] if g else "Grupo"

    return render_template("chat_grupo.html", grupo_id=grupo_id, grupo_nombre=grupo_nombre)

@app.post("/notificaciones/marcar_todo")
def marcar_todo_notificaciones():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("UPDATE notificaciones SET leida=1 WHERE user_id=?", (user_id,))
        conn.commit()
    return redirect("/notificaciones")


@app.post("/notificaciones/<int:noti_id>/eliminar")
def eliminar_notificacion(noti_id):
    if "user_id" not in session:
        return ("noauth", 401)

    user_id = session["user_id"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        # seguridad: solo borrar la noti del dueño
        c.execute("DELETE FROM notificaciones WHERE id=? AND user_id=?", (noti_id, user_id))
        conn.commit()
    return ("ok", 200)

@app.route("/buscar_usuario")
def buscar_usuario():
    if "user_id" not in session:
        return redirect("/login")

    q = (request.args.get("q") or "").strip()
    user_id = session["user_id"]

    resultados = []
    if q:
        like = f"%{q}%"
        with sqlite3.connect("database.db", timeout=20) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, nombre, apellido, COALESCE(email,''), COALESCE(foto,'')
                FROM users
                WHERE id != ?
                  AND (nombre LIKE ? OR apellido LIKE ? OR email LIKE ?)
                ORDER BY nombre ASC
                LIMIT 30
            """, (user_id, like, like, like))
            resultados = c.fetchall()

    return render_template("buscar_usuario.html", q=q, resultados=resultados)
@app.route("/dm/<int:other_id>")
def dm_chat(other_id):
    if "user_id" not in session:
        return redirect("/login")

    me = session["user_id"]
    if me == other_id:
        return redirect("/inbox")

    with sqlite3.connect("database.db", timeout=20) as conn:
        conv_id = get_or_create_conv(conn, me, other_id)

        c = conn.cursor()
        c.execute("SELECT nombre, apellido FROM users WHERE id=?", (other_id,))
        row = c.fetchone()
        other_name = (f"{row[0]} {row[1]}".strip()) if row else "Usuario"

    return render_template("dm_chat.html", conv_id=conv_id, other_id=other_id, other_name=other_name)

@app.route("/api/dm/<int:conv_id>/mensajes")
def api_dm_mensajes(conv_id):
    if "user_id" not in session:
        return jsonify({"error":"no_login"}), 401

    me = session["user_id"]
    after_id = int(request.args.get("after_id", 0))

    with sqlite3.connect("database.db", timeout=20) as conn:
        if not user_in_conv(conn, conv_id, me):
            return jsonify({"error":"no_access"}), 403

        c = conn.cursor()
        c.execute("""
            SELECT m.id, m.from_id, COALESCE(m.mensaje,''), COALESCE(m.media,''), m.fecha,
                   u.nombre, COALESCE(u.apellido,''), COALESCE(u.foto,'')
            FROM mensajes_priv m
            JOIN users u ON u.id = m.from_id
            WHERE m.conv_id=? AND m.id>?
            ORDER BY m.id ASC
            LIMIT 200
        """, (conv_id, after_id))

        msgs = []
        for r in c.fetchall():
            mid, from_id, msg, media, fecha, nom, ape, foto = r
            msgs.append({
                "id": mid,
                "from_id": from_id,
                "nombre": f"{nom} {ape}".strip(),
                "mensaje": msg,
                "media": ("/" + media.replace("\\","/")) if media else "",
                "avatar": ("/" + foto.replace("\\","/")) if foto else "/static/default_user.png",
                "fecha": fecha
            })

    return jsonify({"messages": msgs, "me": me})
@app.route("/api/dm/<int:conv_id>/enviar", methods=["POST"])
def api_dm_enviar(conv_id):
    if "user_id" not in session:
        return jsonify({"error":"no_login"}), 401

    me = session["user_id"]
    mensaje = (request.form.get("mensaje") or "").strip()

    file = request.files.get("media")
    media_path = ""

    if file and file.filename:
        filename = secure_filename(file.filename)
        final_name = f"dm{conv_id}_u{me}_{uuid.uuid4().hex}_{filename}"
        save_path = os.path.join(UPLOAD_CHAT_PRIV, final_name)
        file.save(save_path)
        media_path = save_path.replace("\\","/")

    if not mensaje and not media_path:
        return jsonify({"status":"empty"}), 200

    with sqlite3.connect("database.db", timeout=20) as conn:
        if not user_in_conv(conn, conv_id, me):
            return jsonify({"error":"no_access"}), 403

        c = conn.cursor()
        c.execute("""
            INSERT INTO mensajes_priv (conv_id, from_id, mensaje, media)
            VALUES (?,?,?,?)
        """, (conv_id, me, mensaje, media_path))
        conn.commit()

    return jsonify({"status":"ok"})

@app.route("/inbox")
def inbox():
    if "user_id" not in session:
        return redirect("/login")

    me = session["user_id"]
    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()
        c.execute("""
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
        """, (me, me, me))
        chats = c.fetchall()

    return render_template("inbox.html", chats=chats)


@app.route("/shorts")
def shorts_feed():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()

        # grupos donde soy miembro
        c.execute("SELECT grupo_id FROM grupos_miembros WHERE user_id=?", (user_id,))
        mis_grupos = [r[0] for r in c.fetchall()]

        if not mis_grupos:
            shorts = []
        else:
            placeholders = ",".join(["?"] * len(mis_grupos))

            c.execute(f"""
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
            """, mis_grupos)

            shorts = c.fetchall()

    return render_template("shorts_feed.html", shorts=shorts)
   
@app.route("/shorts/upload", methods=["GET", "POST"])
def shorts_upload():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()

        # traer grupos donde soy miembro (para elegir)
        c.execute("""
            SELECT g.id, g.nombre
            FROM grupos g
            JOIN grupos_miembros gm ON gm.grupo_id = g.id
            WHERE gm.user_id=?
            ORDER BY g.id DESC
        """, (user_id,))
        mis_grupos = c.fetchall()

    if request.method == "GET":
        return render_template("shorts_upload.html", grupos=mis_grupos)

    grupo_id = int(request.form.get("grupo_id"))
    desc = (request.form.get("descripcion") or "").strip()
    f = request.files.get("video")

    if not f or f.filename == "":
        return "Subí un video"

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_SHORT_EXT:
        return "Formato inválido (mp4/webm/mov)"

    # seguridad: verificar que sea miembro del grupo
    with sqlite3.connect("database.db", timeout=20) as conn:
        if not es_miembro(conn, grupo_id, user_id):
            return "No eres miembro de ese grupo", 403

    # guardar archivo
    filename = secure_filename(f"{uuid.uuid4().hex}{ext}")
    save_path = os.path.join(UPLOAD_SHORTS, filename)
    f.save(save_path)

    video_rel = save_path.replace("\\", "/")  # "static/uploads/shorts/..."

    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO shorts (grupo_id, user_id, video, descripcion)
            VALUES (?,?,?,?)
        """, (grupo_id, user_id, video_rel, desc))
        conn.commit()

    return redirect("/shorts")
@app.post("/shorts/<int:short_id>/like")
def short_like(short_id):
    if "user_id" not in session:
        return jsonify({"status":"noauth"}), 401

    user_id = session["user_id"]

    with sqlite3.connect("database.db", timeout=20) as conn:
        c = conn.cursor()

        # seguridad: el short debe ser de un grupo donde soy miembro
        c.execute("SELECT grupo_id FROM shorts WHERE id=?", (short_id,))
        row = c.fetchone()
        if not row:
            return jsonify({"status":"notfound"}), 404

        grupo_id = row[0]
        if not es_miembro(conn, grupo_id, user_id):
            return jsonify({"status":"forbidden"}), 403

        c.execute("SELECT 1 FROM short_likes WHERE short_id=? AND user_id=?", (short_id, user_id))
        if c.fetchone():
            c.execute("DELETE FROM short_likes WHERE short_id=? AND user_id=?", (short_id, user_id))
            liked = False
        else:
            c.execute("INSERT OR IGNORE INTO short_likes (short_id, user_id) VALUES (?,?)", (short_id, user_id))
            liked = True

        c.execute("SELECT COUNT(*) FROM short_likes WHERE short_id=?", (short_id,))
        likes = c.fetchone()[0]

        conn.commit()

    return jsonify({"status":"ok", "liked": liked, "likes": likes})

# =====================
# --- INICIAR SERVIDOR ---
# =====================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
    #app.run(debug=False)   DEBUG DESACTIVADO para evitar bloqueos
