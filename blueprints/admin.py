from flask import Blueprint, render_template, request, redirect, session
from db import get_db
from helpers import random_filename, safe_save_file

admin_bp = Blueprint("admin", __name__)


def admin_required():
    if "user_id" not in session or session.get("is_admin") != 1:
        return False
    return True


@admin_bp.route("/admin_home")
def admin_home():
    if not admin_required():
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE activo=1")
        activos = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users")
        total_miembros = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reportes")
        total_reports = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM grupos")
        total_groups = c.fetchone()[0]

    return render_template(
        "admin_home.html",
        nombre=session["nombre"],
        total_miembros=total_miembros,
        activos=activos,
        total_reports=total_reports,
        total_groups=total_groups,
        nombre_familia="Family_web",
    )


@admin_bp.route("/admin/config")
def admin_config():
    if not admin_required():
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE activo=1")
        active_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reportes")
        total_reports = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM grupos")
        total_groups = c.fetchone()[0]
        c.execute(
            "SELECT id, nombre, apellido, email, is_admin, activo FROM users ORDER BY id DESC LIMIT 5"
        )
        recent_users = c.fetchall()
        c.execute(
            "SELECT titulo, estado, creado FROM reportes ORDER BY creado DESC LIMIT 5"
        )
        recent_reports = c.fetchall()

    return render_template(
        "admin_config.html",
        total_users=total_users,
        active_users=active_users,
        total_reports=total_reports,
        total_groups=total_groups,
        recent_users=recent_users,
        recent_reports=recent_reports,
    )


@admin_bp.route("/admin/reports")
def admin_reports():
    if not admin_required():
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT r.id, r.titulo, r.descripcion, r.tipo, r.estado, r.creado, u.nombre || ' ' || u.apellido "
            "FROM reportes r JOIN users u ON u.id = r.user_id ORDER BY r.creado DESC"
        )
        reportes = c.fetchall()
        c.execute("SELECT COUNT(*) FROM reportes WHERE estado='pendiente'")
        pendientes = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reportes WHERE estado='en_progreso'")
        en_progreso = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reportes WHERE estado='resuelto'")
        resueltos = c.fetchone()[0]

    return render_template(
        "admin_reports.html",
        reportes=reportes,
        pendientes=pendientes,
        en_progreso=en_progreso,
        resueltos=resueltos,
    )


@admin_bp.route("/admin/reporte/<int:report_id>/<estado>")
def update_reporte_estado(report_id, estado):
    if not admin_required():
        return redirect("/login")

    if estado not in ("pendiente", "en_progreso", "resuelto"):
        return redirect("/admin/reports")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE reportes SET estado=?, actualizado=CURRENT_TIMESTAMP WHERE id=?",
            (estado, report_id),
        )
        conn.commit()

    return redirect("/admin/reports")


@admin_bp.route("/add_member", methods=["GET", "POST"])
def add_member():
    if not admin_required():
        return redirect("/login")

    if request.method == "POST":
        foto_path = safe_save_file(
            request.files.get("foto"),
            "static/uploads",
            random_filename(),
        )

        is_admin = 1 if request.form.get("is_admin") == "on" else 0
        activo = 1 if request.form.get("activo") == "on" else 0

        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO users (nombre, apellido, email, password, fecha_nac, municipio, pais, foto, telefono, estado_civil, bio, activo, is_admin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    request.form.get("telefono"),
                    request.form.get("estado_civil"),
                    request.form.get("bio"),
                    activo,
                    is_admin,
                ),
            )
            conn.commit()

        return redirect("/admin_home")

    return render_template("add_member.html")


@admin_bp.route("/members")
def members():
    if not admin_required():
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, nombre, apellido, email, password, foto, is_admin, activo FROM users ORDER BY is_admin DESC, nombre ASC"
        )
        integrantes = c.fetchall()

    return render_template("members.html", integrantes=integrantes)


@admin_bp.route("/delete_member/<int:id>")
def delete_member(id):
    if not admin_required():
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id=? AND is_admin=0", (id,))
        conn.commit()

    return redirect("/members")


@admin_bp.route("/edit_member/<int:id>", methods=["GET", "POST"])
def edit_member(id):
    if not admin_required():
        return redirect("/login")

    if request.method == "POST":
        foto_path = safe_save_file(
            request.files.get("foto"),
            "static/uploads",
            random_filename(),
        )

        is_admin = 1 if request.form.get("is_admin") == "on" else 0
        activo = 1 if request.form.get("activo") == "on" else 0

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
            is_admin,
            activo,
        )

        with get_db() as conn:
            c = conn.cursor()
            if foto_path:
                c.execute(
                    """
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?, telefono=?, direccion=?, estado_civil=?, bio=?, is_admin=?, activo=?, foto=?
                    WHERE id=?
                    """,
                    datos + (foto_path, id),
                )
            else:
                c.execute(
                    """
                    UPDATE users
                    SET nombre=?, apellido=?, email=?, password=?, fecha_nac=?, municipio=?, pais=?, telefono=?, direccion=?, estado_civil=?, bio=?, is_admin=?, activo=?
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
