from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from . import auth_bp
from .forms import LoginForm
from ..models import User


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data):
            if user.role == "tabulator" and not user.competition_id:
                flash("Tabulator account is not assigned to a competition.", "danger")
                return redirect(url_for("auth.login"))
            login_user(user)
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            if user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("tabulator.portal"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("main.home"))
