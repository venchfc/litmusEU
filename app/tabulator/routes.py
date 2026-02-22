from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.exceptions import Forbidden
from flask_wtf import FlaskForm
from wtforms import FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange

from . import tabulator_bp
from ..extensions import db
from ..models import Competition, Contestant, Criteria, Event, Judge, Score, judge_competitions
from ..utils.decorators import role_required


def _get_active_event():
    event = Event.query.filter_by(status="active").first()
    if event:
        return event
    event = Event(name="Main Event", status="active")
    db.session.add(event)
    db.session.commit()
    return event


def _competition_judges_query(competition_id):
    return (
        Judge.query.outerjoin(
            judge_competitions,
            Judge.id == judge_competitions.c.judge_id,
        )
        .filter(
            (Judge.competition_id == competition_id)
            | (judge_competitions.c.competition_id == competition_id)
        )
        .distinct()
        .order_by(Judge.name)
    )


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
        flash("You are not assigned to this competition portal.", "warning")
        return redirect(url_for("tabulator.portal"))
    competition = Competition.query.get_or_404(competition_id)
    judges = _competition_judges_query(competition_id).all()
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
    form_locked = False

    if form.validate_on_submit():
        judge_id = form.judge_id.data
        contestant_id = form.contestant_id.data

        locked_exists = (
            Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition_id,
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
            expected_scores = len(judges) * len(criteria_items)
            saved_scores = Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition_id,
                contestant_id=contestant_id,
            ).count()
            if saved_scores < expected_scores:
                db.session.commit()
                flash(
                    "Cannot lock yet. Ensure all judges have saved scores for every criteria.",
                    "warning",
                )
                return redirect(
                    url_for(
                        "tabulator.score_entry",
                        competition_id=competition_id,
                        judge_id=judge_id,
                        contestant_id=contestant_id,
                    )
                )

            Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition_id,
                contestant_id=contestant_id,
            ).update({"locked": True})

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

    selected_judge_id = request.args.get("judge_id", type=int)
    selected_contestant_id = request.args.get("contestant_id", type=int)
    if not selected_judge_id and judges:
        selected_judge_id = judges[0].id
    if not selected_contestant_id and contestants:
        selected_contestant_id = contestants[0].id
    if selected_judge_id and selected_contestant_id:
        form.judge_id.data = selected_judge_id
        form.contestant_id.data = selected_contestant_id
        for criteria_item in criteria_items:
            score_entry = Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition_id,
                judge_id=selected_judge_id,
                contestant_id=selected_contestant_id,
                criteria_id=criteria_item.id,
            ).first()
            existing_scores[criteria_item.id] = score_entry
            if score_entry:
                getattr(form, f"criteria_{criteria_item.id}").data = score_entry.score
                if score_entry.locked:
                    form_locked = True

    return render_template(
        "tabulator/score_entry.html",
        competition=competition,
        form=form,
        criteria=criteria_items,
        judges=judges,
        contestants=contestants,
        existing_scores=existing_scores,
        form_locked=form_locked,
    )
