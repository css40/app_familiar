from flask import Blueprint, render_template, request, redirect, session
from db import get_db
from helpers import random_filename, safe_save_file

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin_home")
def admin_home():
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE activo=1")
        activos = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users")
        total_miembros = c.fetchone()[0]

    return render_template(
        "admin_home.html",
        nombre=session["nombre"],
        total_miembros=total_miembros,
        activos=activos,
        nombre_familia="Family_web",
    )


@admin_bp.route("/add_member", methods=["GET", "POST"])
def add_member():
    if "user_id" not in session:
        return redirect("/login")
    if session.get("email") != "jhos@admin.com":
        return "No tienes permiso para agregar usuarios"

    if request.method == "POST":
        foto_path = safe_save_file(
            request.files.get("foto"),
            "static/uploads",
            random_filename(),
        )

        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO users (nombre, apellido, email, password, fecha_nac, municipio, pais, foto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.form.get("nombre"),
                    request.form.get("apellido"),
                    request.form.get("email"),
                    request.form.get("password"),
                    request.form.get("fecha_nac"),
                    request.form.get("municipio"),
                    request.form.get("pais"),
                    foto_path,
                ),
            )
            conn.commit()

        return redirect("/admin_home")

    return render_template("add_member.html")


@admin_bp.route("/members")
def members():
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, apellido, email, password, foto FROM users WHERE email != 'jhos@admin.com'")
        integrantes = c.fetchall()

    return render_template("members.html", integrantes=integrantes)


@admin_bp.route("/delete_member/<int:id>")
def delete_member(id):
    if "user_id" not in session:
        return redirect("/login")
    if session.get("email") != "jhos@admin.com":
        return "No tienes permiso para eliminar usuarios"

    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id=? AND email != 'jhos@admin.com'", (id,))
        conn.commit()

    return redirect("/members")


@admin_bp.route("/edit_member/<int:id>", methods=["GET", "POST"])
def edit_member(id):
    if "user_id" not in session:
        return redirect("/login")
    if session.get("email") != "jhos@admin.com":
        return "No tienes permiso para editar otros usuarios"

    if request.method == "POST":
        foto_path = safe_save_file(
            request.files.get("foto"),
            "static/uploads",
            random_filename(),
        )

        datos = (
            request.form.get("nombre"),
            request.form.get("apellido"),
            request.form.get("email"),
            request.form.get("password"),
            request.form.get("fecha_nac"),
            request.form.get("municipio"),
            request.form.get("pais"),
        )

        with get_db() as conn:
            c = conn.cursor()
            if foto_path:
                c.execute(
                    """
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?, foto=?
                    WHERE id=?
                    """,
                    datos + (foto_path, id),
                )
            else:
                c.execute(
                    """
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?
                    WHERE id=?
                    """,
                    datos + (id,),
                )
            conn.commit()

        return redirect("/members")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (id,))
        integrante = c.fetchone()

    return render_template("edit_member.html", integrante=integrante)
