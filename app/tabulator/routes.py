from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.exceptions import Forbidden
from flask_wtf import FlaskForm
from wtforms import FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange

from . import tabulator_bp
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


@tabulator_bp.route("/")
@login_required
@role_required("tabulator")
def portal():
    competitions = Competition.query.order_by(Competition.name).all()
    if current_user.competition_id:
        competitions = Competition.query.filter_by(id=current_user.competition_id).all()
    return render_template("tabulator/portal.html", competitions=competitions)


@tabulator_bp.route("/score/<int:competition_id>", methods=["GET", "POST"])
@login_required
@role_required("tabulator")
def score_entry(competition_id):
    if current_user.competition_id and current_user.competition_id != competition_id:
        raise Forbidden("You are not assigned to this competition portal.")
    competition = Competition.query.get_or_404(competition_id)
    judges = Judge.query.filter_by(competition_id=competition_id).order_by(Judge.name).all()
    contestants = (
        Contestant.query.filter_by(competition_id=competition_id)
        .order_by(Contestant.name)
        .all()
    )
    criteria_items = (
        Criteria.query.filter_by(competition_id=competition_id)
        .order_by(Criteria.name)
        .all()
    )

    class DynamicScoreForm(FlaskForm):
        judge_id = SelectField("Judge", coerce=int, validators=[DataRequired()])
        contestant_id = SelectField("Contestant", coerce=int, validators=[DataRequired()])
        submit_save = SubmitField("Save Score")
        submit_lock = SubmitField("Lock Score")

    for criteria_item in criteria_items:
        field_name = f"criteria_{criteria_item.id}"
        field = FloatField(
            f"{criteria_item.name} (max {criteria_item.max_score})",
            validators=[DataRequired(), NumberRange(min=0, max=criteria_item.max_score)],
        )
        setattr(DynamicScoreForm, field_name, field)

    form = DynamicScoreForm()
    form.judge_id.choices = [(j.id, j.name) for j in judges]
    form.contestant_id.choices = [(c.id, c.name) for c in contestants]

    active_event = _get_active_event()
    existing_scores = {}

    if form.validate_on_submit():
        judge_id = form.judge_id.data
        contestant_id = form.contestant_id.data

        locked_exists = (
            Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition_id,
                judge_id=judge_id,
                contestant_id=contestant_id,
                locked=True,
            ).count()
            > 0
        )

        if locked_exists:
            flash("Scores are locked and cannot be edited.", "danger")
            return redirect(url_for("tabulator.score_entry", competition_id=competition_id))

        for criteria_item in criteria_items:
            field_name = f"criteria_{criteria_item.id}"
            score_value = getattr(form, field_name).data
            score_entry = Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition_id,
                judge_id=judge_id,
                contestant_id=contestant_id,
                criteria_id=criteria_item.id,
            ).first()

            if not score_entry:
                score_entry = Score(
                    event_id=active_event.id,
                    competition_id=competition_id,
                    judge_id=judge_id,
                    contestant_id=contestant_id,
                    criteria_id=criteria_item.id,
                    created_by=current_user.id,
                    score=score_value,
                    locked=False,
                )
                db.session.add(score_entry)
            else:
                score_entry.score = score_value

            if form.submit_lock.data:
                score_entry.locked = True

        db.session.commit()
        flash("Scores saved." if form.submit_save.data else "Scores locked.", "success")
        return redirect(
            url_for(
                "tabulator.score_entry",
                competition_id=competition_id,
                judge_id=judge_id,
                contestant_id=contestant_id,
            )
        )

    judge_id = request.args.get("judge_id", type=int)
    contestant_id = request.args.get("contestant_id", type=int)
    if judge_id and contestant_id:
        form.judge_id.data = judge_id
        form.contestant_id.data = contestant_id
        for criteria_item in criteria_items:
            score_entry = Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition_id,
                judge_id=judge_id,
                contestant_id=contestant_id,
                criteria_id=criteria_item.id,
            ).first()
            existing_scores[criteria_item.id] = score_entry
            if score_entry:
                getattr(form, f"criteria_{criteria_item.id}").data = score_entry.score

    return render_template(
        "tabulator/score_entry.html",
        competition=competition,
        form=form,
        criteria=criteria_items,
        judges=judges,
        contestants=contestants,
        existing_scores=existing_scores,
    )
