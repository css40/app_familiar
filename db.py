import os
import sqlite3

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "database.db")


def get_db():
    """Return a SQLite connection to the app database."""
    return sqlite3.connect(DB_PATH, timeout=20)


def init_db():
    """Create required tables if they don't exist yet."""
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                fecha_nac TEXT,
                municipio TEXT,
                pais TEXT,
                foto TEXT,
                telefono TEXT,
                direccion TEXT,
                estado_civil TEXT,
                bio TEXT,
                activo INTEGER DEFAULT 0
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS user_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                foto TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS tweets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                contenido TEXT NOT NULL,
                foto TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS tweet_reacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                FOREIGN KEY (tweet_id) REFERENCES tweets(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(tweet_id, user_id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS grupos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                creador_id INTEGER NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(creador_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS grupos_miembros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rol TEXT NOT NULL,
                FOREIGN KEY(grupo_id) REFERENCES grupos(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS group_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                contenido TEXT,
                foto TEXT,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS post_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS post_reacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('encanta','divierte','enoja')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_id)
            )
        ''')

        # Comentarios en posts (puede referenciar posts o group_posts por convención)
        c.execute('''
            CREATE TABLE IF NOT EXISTS post_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                texto TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS shorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                video TEXT NOT NULL,
                descripcion TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS short_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(short_id, user_id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS short_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                texto TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS conversaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user1_id, user2_id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_priv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conv_id INTEGER NOT NULL,
                from_id INTEGER NOT NULL,
                mensaje TEXT,
                media TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                leido INTEGER DEFAULT 0
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_grupo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mensaje TEXT,
                media TEXT,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS notificaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                ref_id INTEGER,
                mensaje TEXT NOT NULL,
                leida INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            INSERT OR IGNORE INTO users (nombre, apellido, email, password)
            VALUES ('Jhos', 'Admin', 'jhos@admin.com', 'admin123')
        ''')

        conn.commit()
