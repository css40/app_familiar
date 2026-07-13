from flask import Blueprint, render_template, request, redirect, session
from db import get_db
from helpers import safe_save_file, random_filename

report_bp = Blueprint("reports", __name__)


@report_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        apellido = request.form.get("apellido")
        email = request.form.get("email")
        password = request.form.get("password")
        foto_path = safe_save_file(
            request.files.get("foto"),
            "static/uploads",
            random_filename(),
        )

        with get_db() as conn:
            c = conn.cursor()
            try:
                c.execute(
                    "INSERT INTO users (nombre, apellido, email, password, foto) VALUES (?, ?, ?, ?, ?)",
                    (nombre, apellido, email, password, foto_path),
                )
                conn.commit()
            except Exception:
                return render_template("register.html", error="El email ya existe.")

        return redirect("/login")

    return render_template("register.html")


@report_bp.route("/reportar", methods=["GET", "POST"])
def reportar():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        titulo = request.form.get("titulo")
        descripcion = request.form.get("descripcion")
        tipo = request.form.get("tipo") or "error"

        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO reportes (user_id, titulo, descripcion, tipo) VALUES (?, ?, ?, ?)",
                (session["user_id"], titulo, descripcion, tipo),
            )
            conn.commit()

        return redirect("/user_home")

    return render_template("reportar.html")
