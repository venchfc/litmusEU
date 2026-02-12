from flask import render_template

from . import main_bp
from ..models import Competition


@main_bp.route("/")
def home():
    competitions = Competition.query.order_by(Competition.name).all()
    return render_template("main/home.html", competitions=competitions)
