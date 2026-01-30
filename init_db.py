import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Crear tabla de usuarios
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
    foto TEXT
)
''')

# Insertar admin
c.execute('''
INSERT OR IGNORE INTO users (nombre, apellido, email, password)
VALUES ('Jhos', 'Admin', 'jhos@admin.com', 'admin123')
''')

conn.commit()
conn.close()
print("Base de datos inicializada con admin.")
