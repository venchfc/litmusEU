from datetime import datetime

from flask_login import UserMixin

from .extensions import bcrypt, db, login_manager


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)


class Competition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    judges = db.relationship("Judge", backref="competition", cascade="all, delete-orphan")
    contestants = db.relationship(
        "Contestant", backref="competition", cascade="all, delete-orphan"
    )
    criteria = db.relationship("Criteria", backref="competition", cascade="all, delete-orphan")


class Judge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey("competition.id"), nullable=False)


class Contestant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey("competition.id"), nullable=False)


class Criteria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    max_score = db.Column(db.Float, default=10.0, nullable=False)
    weight = db.Column(db.Float, default=1.0, nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey("competition.id"), nullable=False)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey("competition.id"))

    competition = db.relationship("Competition", backref="tabulators")

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey("competition.id"), nullable=False)
    judge_id = db.Column(db.Integer, db.ForeignKey("judge.id"), nullable=False)
    contestant_id = db.Column(db.Integer, db.ForeignKey("contestant.id"), nullable=False)
    criteria_id = db.Column(db.Integer, db.ForeignKey("criteria.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    locked = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "event_id",
            "competition_id",
            "judge_id",
            "contestant_id",
            "criteria_id",
            name="uq_score_entry",
        ),
    )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
