import os

from flask import Flask

from .config import Config
from .extensions import bcrypt, db, login_manager
from .models import Competition, Event, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    from .tabulator.routes import tabulator_bp
    from .main.routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(tabulator_bp, url_prefix="/tabulator")

    with app.app_context():
        db.create_all()
        _seed_competitions()
        _seed_primary_admin()
        _seed_active_event()

    return app


def _seed_competitions():
    if Competition.query.count() > 0:
        return

    competitions = [
        ("Choir", "choir"),
        ("Vocal Solo", "vocal-solo"),
        ("Vocal Duet", "vocal-duet"),
        ("Hiphop Dance", "hiphop-dance"),
        ("Folkdance", "folkdance"),
    ]

    for name, slug in competitions:
        db.session.add(Competition(name=name, slug=slug))

    db.session.commit()


def _seed_primary_admin():
    if User.query.count() > 0:
        return

    default_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    admin = User(
        username=default_username,
        role="admin",
        is_primary=True,
    )
    admin.set_password(default_password)
    db.session.add(admin)
    db.session.commit()


def _seed_active_event():
    if Event.query.filter_by(status="active").first():
        return

    event = Event(name="Main Event", status="active")
    db.session.add(event)
    db.session.commit()
