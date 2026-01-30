from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import uuid 
from werkzeug.utils import secure_filename

app = Flask(__name__)
usuarios_activos = set()
app.secret_key = "supersecretkey"


def marcar_activo(user_id, estado):
    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET activo = ? WHERE id = ?", (estado, user_id))
        conn.commit()


# Carpeta para subir fotos
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

    # Marcar usuario como activo
    usuarios_activos.add(session['user_id'])

    total_miembros = 4  # después lo sacamos de tu BD
    activos = len(usuarios_activos)
    nombre_familia = "Mi Familia"

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
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], str(uuid.uuid4()) + "_" + foto.filename)
            foto.save(foto_path)

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

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        
        # ------------------ 1️⃣ Traemos todos los tweets ------------------
        c.execute("""
            SELECT tweets.id, tweets.contenido, tweets.foto, tweets.fecha,
                   users.nombre, users.foto, tweets.user_id
            FROM tweets
            JOIN users ON tweets.user_id = users.id
            ORDER BY tweets.fecha DESC
        """)
        tweets = c.fetchall()

        # ------------------ 2️⃣ Contamos reacciones para cada tweet ------------------
        tweet_reacciones = {}
        for tweet in tweets:
            tweet_id = tweet[0]
            c.execute("""
                SELECT tipo, COUNT(*) FROM tweet_reacciones
                WHERE tweet_id=?
                GROUP BY tipo
            """, (tweet_id,))
            tweet_reacciones[tweet_id] = dict(c.fetchall())

    # ------------------ 3️⃣ Renderizamos la plantilla ------------------
    return render_template(
        "user_home.html",
        nombre=session['nombre'],
        tweets=tweets,
        user_id=session['user_id'],
        tweet_reacciones=tweet_reacciones
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
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], str(uuid.uuid4()) + "_" + foto.filename)
            foto.save(foto_path)

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
                    UPDATE users SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?, foto=?
                    WHERE id=?
                ''', (nombre, apellido, email, password, fecha_nac, municipio, pais, foto_path, id))
            else:
                c.execute('''
                    UPDATE users SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?
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
        import uuid

        # --- Subir foto principal ---
        foto = request.files.get('foto')
        foto_path = None
        if foto and foto.filename != '':
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], str(uuid.uuid4()) + "_" + foto.filename)
            foto.save(foto_path)

        # --- Subir fotos adicionales (álbum) ---
        fotos_album = request.files.getlist('fotos')
        with sqlite3.connect('database.db', timeout=20) as conn:
            c = conn.cursor()
            for f in fotos_album:
                if f and f.filename != '':
                    path = os.path.join(app.config['UPLOAD_FOLDER'], str(uuid.uuid4()) + "_" + f.filename)
                    f.save(path)
                    c.execute("INSERT INTO user_photos (user_id, foto) VALUES (?, ?)", (user_id, path))
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
                ''', (nombre, apellido, email, password, fecha_nac, municipio, pais,
                      telefono, direccion, estado_civil, bio, foto_path, user_id))
            else:
                c.execute('''
                    UPDATE users 
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?,
                        telefono=?, direccion=?, estado_civil=?, bio=?
                    WHERE id=?
                ''', (nombre, apellido, email, password, fecha_nac, municipio, pais,
                      telefono, direccion, estado_civil, bio, user_id))
            conn.commit()

        return redirect('/profile')

    # --- GET: mostrar datos actuales ---
    with sqlite3.connect('database.db', timeout=20) as conn:
        c = conn.cursor()
        # Datos del usuario
        c.execute("SELECT * FROM users WHERE id=?", (user_id,))
        integrante = c.fetchone()

        # Fotos del álbum
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
            SELECT g.id, g.nombre, u.nombre, u.apellido
            FROM grupos g
            JOIN grupos_miembros gm ON g.id = gm.grupo_id
            JOIN users u ON g.creador_id = u.id
         
        """, )
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
                c.execute("INSERT INTO grupos_miembros (grupo_id, user_id, rol) VALUES (?, ?, ?)",
                          (u, r))
            
            conn.commit()

        return redirect("/grupos")

    # GET → enviar todos los usuarios a JS para búsqueda dinámica
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, apellido, email FROM users WHERE id != ?", (user_id,))
        usuarios = c.fetchall()

    # Pasamos usuarios como JSON para JS
    return render_template("crear_grupo.html", usuarios=usuarios)

@app.route("/grupo/<int:grupo_id>")
def ver_grupo(grupo_id):
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        # Info del grupo
        c.execute("SELECT nombre, creador_id FROM grupos WHERE id=?", (grupo_id,))
        grupo = c.fetchone()

        # Miembros del grupo
        c.execute("""
            SELECT gm.user_id, u.nombre, u.apellido, u.foto, gm.rol
            FROM grupos_miembros gm
            JOIN users u ON gm.user_id = u.id
       
        """, )
        miembros = c.fetchall()

        # Para agregar miembros: solo usuarios que NO estén ya en el grupo
        c.execute("""
            SELECT id, nombre, apellido
            FROM users
            WHERE id NOT IN (
                SELECT user_id FROM grupos_miembros WHERE grupo_id=?
            )
        """, (grupo_id,))
        usuarios_disponibles = c.fetchall()  # <-- esto faltaba

    return render_template("grupo_detalle.html", grupo=grupo, miembros=miembros,
                           usuarios_disponibles=usuarios_disponibles)

@app.route('/grupo/<int:grupo_id>', methods=['GET', 'POST'])
def detalle_grupo(grupo_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()

        # Información del grupo
        c.execute("SELECT nombre, creador_id FROM grupos WHERE id=?", (grupo_id,))
        grupo = c.fetchone()
        if not grupo:
            return "Grupo no encontrado"

        grupo_nombre, creador_id = grupo

        # Obtener miembros del grupo
        c.execute("""
            SELECT gm.user_id, u.nombre, u.apellido, u.email, gm.rol
            FROM grupos_miembros gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.grupo_id=?
        """, (grupo_id,))
        miembros = c.fetchall()

        # GET: usuarios existentes para añadir
        c.execute("SELECT id, nombre, apellido, email FROM users WHERE id NOT IN (SELECT user_id FROM grupos_miembros WHERE grupo_id=?)", (grupo_id,))
        usuarios_disponibles = c.fetchall()

    return render_template("detalle_grupo.html",
                           grupo_id=grupo_id,
                           grupo_nombre=grupo_nombre,
                           creador_id=creador_id,
                           miembros=miembros,
                           usuarios_disponibles=usuarios_disponibles,
                           user_id=user_id)

@app.route('/grupo/<int:grupo_id>/agregar', methods=['POST'])
def agregar_miembro_grupo(grupo_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = request.form.get('usuario_id')
    rol = request.form.get('rol')

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("INSERT INTO grupos_miembros (grupo_id, user_id, rol) VALUES (?, ?, ?)",
                  (grupo_id, user_id, rol))
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






# =====================
# --- INICIAR SERVIDOR ---
# =====================
if __name__ == '__main__':
    app.run(debug=False)  # DEBUG DESACTIVADO para evitar bloqueos
