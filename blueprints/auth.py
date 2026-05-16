from flask import Blueprint, render_template, request, redirect, session
from db import get_db
from helpers import marcar_activo

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET", "POST"])
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
            user = c.fetchone()

        if user:
            session["user_id"] = user[0]
            session["nombre"] = user[1]
            session["email"] = user[3]
            marcar_activo(user[0], 1)

            if email == "jhos@admin.com":
                return redirect("/admin_home")
            return redirect("/user_home")

        return "Usuario o contraseña incorrectos"

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    if user_id:
        marcar_activo(user_id, 0)
    session.clear()
    return redirect("/login")
