from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import FloatField, HiddenField, SubmitField
from wtforms.validators import DataRequired, NumberRange

from . import judge_bp
from ..extensions import db
from ..models import Competition, Contestant, Criteria, Event, Judge, Score
from ..utils.decorators import role_required


def _get_active_event():
    event = Event.query.filter_by(status="active").first()
    if event:
        return event
    event = Event(name="Main Event", status="active")
    db.session.add(event)
    db.session.commit()
    return event


def _judge_competition_ids(judge):
    if not judge:
        return set()
    competition_ids = {competition.id for competition in judge.competitions}
    if judge.competition_id:
        competition_ids.add(judge.competition_id)
    return competition_ids


@judge_bp.route("/")
@login_required
@role_required("judge")
def portal():
    competitions = []
    judge = Judge.query.get(current_user.judge_id) if current_user.judge_id else None
    competition_ids = _judge_competition_ids(judge)
    if competition_ids:
        competitions = (
            Competition.query.filter(Competition.id.in_(competition_ids))
            .order_by(Competition.name)
            .all()
        )
    elif current_user.competition_id:
        competition = Competition.query.get(current_user.competition_id)
        competitions = [competition] if competition else []
    return render_template("judge/portal.html", competitions=competitions)


@judge_bp.route("/score/<int:competition_id>", methods=["GET", "POST"])
@login_required
@role_required("judge")
def score(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    judge = Judge.query.get(current_user.judge_id) if current_user.judge_id else None
    if competition_id not in _judge_competition_ids(judge):
        flash("Judge account is not linked to this competition.", "warning")
        return redirect(url_for("judge.portal"))

    criteria_items = Criteria.query.filter_by(competition_id=competition.id).order_by(Criteria.name).all()
    contestants = (
        Contestant.query.filter_by(competition_id=competition.id)
        .order_by(Contestant.name)
        .all()
    )
    active_event = _get_active_event()

    class JudgeScoreForm(FlaskForm):
        contestant_id = HiddenField(validators=[DataRequired()])
        submit = SubmitField("Submit Score")

    for criteria_item in criteria_items:
        field_name = f"criteria_{criteria_item.id}"
        field = FloatField(
            f"{criteria_item.name} (max {criteria_item.max_score})",
            validators=[DataRequired(), NumberRange(min=0, max=criteria_item.max_score)],
        )
        setattr(JudgeScoreForm, field_name, field)

    score_form = JudgeScoreForm()

    scored_contestants = set()
    if criteria_items and contestants:
        scores = Score.query.filter_by(
            event_id=active_event.id,
            competition_id=competition.id,
            judge_id=judge.id,
        ).all()
        score_counts = {}
        for score in scores:
            score_counts[score.contestant_id] = score_counts.get(score.contestant_id, 0) + 1
        for contestant in contestants:
            if score_counts.get(contestant.id) == len(criteria_items):
                scored_contestants.add(contestant.id)

    if score_form.validate_on_submit():
        try:
            contestant_id = int(score_form.contestant_id.data)
        except (TypeError, ValueError):
            flash("Invalid contestant selection.", "warning")
            return redirect(url_for("judge.score", competition_id=competition.id))
        if contestant_id not in {c.id for c in contestants}:
            flash("Invalid contestant selection.", "warning")
            return redirect(url_for("judge.score", competition_id=competition.id))
        if contestant_id in scored_contestants:
            flash("Scores already submitted for this contestant.", "warning")
            return redirect(url_for("judge.score", competition_id=competition.id))

        existing_count = Score.query.filter_by(
            event_id=active_event.id,
            competition_id=competition.id,
            judge_id=judge.id,
            contestant_id=contestant_id,
        ).count()
        if existing_count > 0:
            flash("Scores already submitted for this contestant.", "warning")
            return redirect(url_for("judge.score", competition_id=competition.id))

        for criteria_item in criteria_items:
            field_name = f"criteria_{criteria_item.id}"
            score_value = getattr(score_form, field_name).data
            score_entry = Score(
                event_id=active_event.id,
                competition_id=competition.id,
                judge_id=judge.id,
                contestant_id=contestant_id,
                criteria_id=criteria_item.id,
                created_by=current_user.id,
                score=score_value,
                locked=True,
            )
            db.session.add(score_entry)

        db.session.commit()
        flash("Scores submitted.", "success")
        return redirect(url_for("judge.score", competition_id=competition.id))
    elif request.method == "POST":
        flash("Please provide valid scores for all criteria.", "warning")

    return render_template(
        "judge/scoring.html",
        competition=competition,
        criteria_items=criteria_items,
        contestants=contestants,
        scored_contestants=scored_contestants,
        score_form=score_form,
    )
