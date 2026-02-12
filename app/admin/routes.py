from datetime import datetime

from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import admin_bp
from .forms import (
    AccountForm,
    ChangePasswordForm,
    CompetitionForm,
    ContestantForm,
    CriteriaForm,
    JudgeForm,
    ResetDatabaseForm,
)
from ..extensions import db
from ..models import Competition, Contestant, Criteria, Event, Judge, Score, User
from ..utils.decorators import role_required
from ..utils.pdf import render_results_pdf


def _get_active_event():
    event = Event.query.filter_by(status="active").first()
    if event:
        return event
    event = Event(name="Main Event", status="active")
    db.session.add(event)
    db.session.commit()
    return event


@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    active_event = _get_active_event()
    stats = {
        "competitions": Competition.query.count(),
        "judges": Judge.query.count(),
        "contestants": Contestant.query.count(),
        "criteria": Criteria.query.count(),
        "tabulators": User.query.filter_by(role="tabulator").count(),
    }
    return render_template("admin/dashboard.html", stats=stats, active_event=active_event)


@admin_bp.route("/competitions", methods=["GET", "POST"])
@login_required
@role_required("admin")
def competitions():
    form = CompetitionForm()
    if form.validate_on_submit():
        slug = form.slug.data.strip().lower().replace(" ", "-")
        if Competition.query.filter_by(slug=slug).first():
            flash("Slug already exists.", "warning")
        else:
            db.session.add(Competition(name=form.name.data.strip(), slug=slug))
            db.session.commit()
            flash("Competition added.", "success")
        return redirect(url_for("admin.competitions"))

    competitions_list = Competition.query.order_by(Competition.name).all()
    return render_template(
        "admin/competitions.html", competitions=competitions_list, form=form
    )


@admin_bp.route("/competitions/delete/<int:competition_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_competition(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    db.session.delete(competition)
    db.session.commit()
    flash("Competition deleted.", "success")
    return redirect(url_for("admin.competitions"))


@admin_bp.route("/judges", methods=["GET", "POST"])
@login_required
@role_required("admin")
def judges():
    form = JudgeForm()
    competitions_list = Competition.query.order_by(Competition.name).all()
    form.competition_id.choices = [(c.id, c.name) for c in competitions_list]

    if form.validate_on_submit():
        db.session.add(
            Judge(name=form.name.data.strip(), competition_id=form.competition_id.data)
        )
        db.session.commit()
        flash("Judge added.", "success")
        return redirect(url_for("admin.judges", competition_id=form.competition_id.data))

    competition_id = request.args.get("competition_id", type=int)
    if not competition_id and competitions_list:
        competition_id = competitions_list[0].id

    judges_list = (
        Judge.query.filter_by(competition_id=competition_id).order_by(Judge.name).all()
        if competition_id
        else []
    )
    return render_template(
        "admin/judges.html",
        form=form,
        competitions=competitions_list,
        judges=judges_list,
        selected_competition=competition_id,
    )


@admin_bp.route("/judges/delete/<int:judge_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_judge(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    db.session.delete(judge)
    db.session.commit()
    flash("Judge deleted.", "success")
    return redirect(url_for("admin.judges", competition_id=judge.competition_id))


@admin_bp.route("/contestants", methods=["GET", "POST"])
@login_required
@role_required("admin")
def contestants():
    form = ContestantForm()
    competitions_list = Competition.query.order_by(Competition.name).all()
    form.competition_id.choices = [(c.id, c.name) for c in competitions_list]

    if form.validate_on_submit():
        db.session.add(
            Contestant(
                name=form.name.data.strip(), competition_id=form.competition_id.data
            )
        )
        db.session.commit()
        flash("Contestant added.", "success")
        return redirect(
            url_for("admin.contestants", competition_id=form.competition_id.data)
        )

    competition_id = request.args.get("competition_id", type=int)
    if not competition_id and competitions_list:
        competition_id = competitions_list[0].id

    contestants_list = (
        Contestant.query.filter_by(competition_id=competition_id)
        .order_by(Contestant.name)
        .all()
        if competition_id
        else []
    )
    return render_template(
        "admin/contestants.html",
        form=form,
        competitions=competitions_list,
        contestants=contestants_list,
        selected_competition=competition_id,
    )


@admin_bp.route("/contestants/delete/<int:contestant_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_contestant(contestant_id):
    contestant = Contestant.query.get_or_404(contestant_id)
    db.session.delete(contestant)
    db.session.commit()
    flash("Contestant deleted.", "success")
    return redirect(url_for("admin.contestants", competition_id=contestant.competition_id))


@admin_bp.route("/criteria", methods=["GET", "POST"])
@login_required
@role_required("admin")
def criteria():
    form = CriteriaForm()
    competitions_list = Competition.query.order_by(Competition.name).all()
    form.competition_id.choices = [(c.id, c.name) for c in competitions_list]

    if form.validate_on_submit():
        existing_total = (
            db.session.query(db.func.coalesce(db.func.sum(Criteria.weight), 0.0))
            .filter(Criteria.competition_id == form.competition_id.data)
            .scalar()
        )
        if existing_total + form.weight.data > 100.0:
            flash("Total criteria weight cannot exceed 100%.", "warning")
            return redirect(url_for("admin.criteria", competition_id=form.competition_id.data))
        db.session.add(
            Criteria(
                name=form.name.data.strip(),
                max_score=form.max_score.data,
                weight=form.weight.data,
                competition_id=form.competition_id.data,
            )
        )
        db.session.commit()
        flash("Criteria added.", "success")
        return redirect(url_for("admin.criteria", competition_id=form.competition_id.data))

    competition_id = request.args.get("competition_id", type=int)
    if not competition_id and competitions_list:
        competition_id = competitions_list[0].id

    criteria_list = (
        Criteria.query.filter_by(competition_id=competition_id).order_by(Criteria.name).all()
        if competition_id
        else []
    )
    current_weight_total = (
        db.session.query(db.func.coalesce(db.func.sum(Criteria.weight), 0.0))
        .filter(Criteria.competition_id == competition_id)
        .scalar()
        if competition_id
        else 0.0
    )
    return render_template(
        "admin/criteria.html",
        form=form,
        competitions=competitions_list,
        criteria=criteria_list,
        selected_competition=competition_id,
        current_weight_total=current_weight_total,
    )


@admin_bp.route("/criteria/delete/<int:criteria_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_criteria(criteria_id):
    criteria_item = Criteria.query.get_or_404(criteria_id)
    db.session.delete(criteria_item)
    db.session.commit()
    flash("Criteria deleted.", "success")
    return redirect(url_for("admin.criteria", competition_id=criteria_item.competition_id))


@admin_bp.route("/accounts", methods=["GET", "POST"])
@login_required
@role_required("admin")
def accounts():
    form = AccountForm()
    competitions_list = Competition.query.order_by(Competition.name).all()
    form.competition_id.choices = [(c.id, c.name) for c in competitions_list]
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash("Username already exists.", "warning")
        else:
            user = User(
                username=form.username.data.strip(),
                role=form.role.data,
                is_primary=False,
            )
            if form.role.data == "tabulator":
                user.competition_id = form.competition_id.data
                if not user.competition_id:
                    flash("Select a competition for tabulator accounts.", "warning")
                    return redirect(url_for("admin.accounts"))
            else:
                user.competition_id = None
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash("Account created.", "success")
        return redirect(url_for("admin.accounts"))

    users = User.query.order_by(User.username).all()
    return render_template(
        "admin/accounts.html",
        form=form,
        users=users,
        competitions=competitions_list,
    )


@admin_bp.route("/accounts/delete/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_account(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_primary:
        flash("Primary admin account cannot be deleted.", "danger")
        return redirect(url_for("admin.accounts"))

    db.session.delete(user)
    db.session.commit()
    flash("Account deleted.", "success")
    return redirect(url_for("admin.accounts"))


@admin_bp.route("/password", methods=["GET", "POST"])
@login_required
@role_required("admin")
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("admin.change_password"))

        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Password updated successfully.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/change_password.html", form=form)


@admin_bp.route("/results")
@login_required
@role_required("admin")
def results():
    competitions_list = Competition.query.order_by(Competition.name).all()
    event_id = request.args.get("event_id", type=int)
    if event_id:
        event = Event.query.get_or_404(event_id)
    else:
        event = _get_active_event()

    competition_id = request.args.get("competition_id", type=int)
    if not competition_id and competitions_list:
        competition_id = competitions_list[0].id

    competition = Competition.query.get(competition_id) if competition_id else None
    criteria_items = []
    results_rows = []
    judge_breakdown = []
    if competition:
        criteria_items = Criteria.query.filter_by(competition_id=competition.id).order_by(Criteria.name).all()
        results_rows = _calculate_results(event.id, competition.id)
        judges = Judge.query.filter_by(competition_id=competition.id).order_by(Judge.name).all()
        contestants = (
            Contestant.query.filter_by(competition_id=competition.id)
            .order_by(Contestant.name)
            .all()
        )
        scores = Score.query.filter_by(
            event_id=event.id,
            competition_id=competition.id,
        ).all()

        score_lookup = {}
        for score in scores:
            score_lookup[(score.judge_id, score.contestant_id, score.criteria_id)] = score.score

        for judge in judges:
            rows = []
            for contestant in contestants:
                criteria_scores = {}
                total_weighted = 0.0
                for criteria_item in criteria_items:
                    raw_score = score_lookup.get(
                        (judge.id, contestant.id, criteria_item.id)
                    )
                    criteria_scores[criteria_item.id] = raw_score
                    if raw_score is not None and criteria_item.max_score:
                        total_weighted += (
                            raw_score / criteria_item.max_score
                        ) * criteria_item.weight
                rows.append(
                    {
                        "contestant": contestant.name,
                        "criteria_scores": criteria_scores,
                        "total": min(total_weighted, 100.0),
                    }
                )
            judge_breakdown.append({"judge": judge, "rows": rows})

    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template(
        "admin/results.html",
        competitions=competitions_list,
        events=events,
        event=event,
        competition=competition,
        results=results_rows,
        criteria_items=criteria_items,
        judge_breakdown=judge_breakdown,
    )


@admin_bp.route("/results/pdf")
@login_required
@role_required("admin")
def results_pdf():
    event_id = request.args.get("event_id", type=int)
    competition_id = request.args.get("competition_id", type=int)
    event = Event.query.get_or_404(event_id)
    competition = Competition.query.get_or_404(competition_id)
    results_rows = _calculate_results(event.id, competition.id)
    criteria_items = Criteria.query.filter_by(competition_id=competition.id).order_by(Criteria.name).all()

    pdf_bytes = render_results_pdf(event, competition, results_rows, criteria_items)
    filename = f"results_{competition.slug}_{event.id}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_bp.route("/history")
@login_required
@role_required("admin")
def history():
    events = Event.query.order_by(Event.created_at.desc()).all()
    competitions = Competition.query.order_by(Competition.name).all()

    completed_competitions = []
    for event in events:
        for competition in competitions:
            judges_count = Judge.query.filter_by(competition_id=competition.id).count()
            contestants_count = Contestant.query.filter_by(competition_id=competition.id).count()
            criteria_count = Criteria.query.filter_by(competition_id=competition.id).count()
            expected_scores = judges_count * contestants_count * criteria_count
            if expected_scores == 0:
                continue
            locked_scores = Score.query.filter_by(
                event_id=event.id,
                competition_id=competition.id,
                locked=True,
            ).count()
            if locked_scores == expected_scores:
                completed_competitions.append(
                    {
                        "event": event,
                        "competition": competition,
                        "expected_scores": expected_scores,
                    }
                )

    return render_template(
        "admin/history.html",
        completed_competitions=completed_competitions,
    )


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@role_required("admin")
def settings():
    reset_form = ResetDatabaseForm(prefix="reset")
    password_form = ChangePasswordForm(prefix="pw")

    if request.method == "POST":
        if "reset-reset_submit" in request.form:
            if reset_form.validate_on_submit():
                if not current_user.check_password(reset_form.password.data):
                    flash("Password is incorrect.", "danger")
                    return redirect(url_for("admin.settings"))
                if not current_user.is_primary:
                    flash("Only the primary admin can reset the database.", "danger")
                    return redirect(url_for("admin.settings"))

                db.session.query(Score).delete(synchronize_session=False)
                db.session.query(Criteria).delete(synchronize_session=False)
                db.session.query(Contestant).delete(synchronize_session=False)
                db.session.query(Judge).delete(synchronize_session=False)
                db.session.query(Competition).delete(synchronize_session=False)
                db.session.query(Event).delete(synchronize_session=False)
                db.session.query(User).filter(User.is_primary.is_(False)).delete(
                    synchronize_session=False
                )
                db.session.commit()

                _get_active_event()
                flash("Database reset completed.", "success")
                return redirect(url_for("admin.settings"))
        elif "pw-submit" in request.form:
            if password_form.validate_on_submit():
                if not current_user.check_password(password_form.current_password.data):
                    flash("Current password is incorrect.", "danger")
                    return redirect(url_for("admin.settings"))

                current_user.set_password(password_form.new_password.data)
                db.session.commit()
                flash("Password updated successfully.", "success")
                return redirect(url_for("admin.settings"))

    return render_template(
        "admin/settings.html",
        reset_form=reset_form,
        password_form=password_form,
    )


@admin_bp.route("/event/close", methods=["POST"])
@login_required
@role_required("admin")
def close_event():
    active_event = _get_active_event()
    active_event.status = "completed"
    active_event.completed_at = datetime.utcnow()
    db.session.add(active_event)

    new_event = Event(name=f"Event {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}", status="active")
    db.session.add(new_event)
    db.session.commit()

    flash("Event closed and archived. New event started.", "success")
    return redirect(url_for("admin.history"))


def _calculate_results(event_id, competition_id):
    contestants = Contestant.query.filter_by(competition_id=competition_id).all()
    criteria_items = Criteria.query.filter_by(competition_id=competition_id).order_by(Criteria.name).all()

    results = []
    for contestant in contestants:
        total_weighted = 0.0
        total_raw = 0.0
        criteria_weighted_totals = {}
        criteria_raw_totals = {}
        for criteria_item in criteria_items:
            scores = (
                Score.query.filter_by(
                    event_id=event_id,
                    competition_id=competition_id,
                    contestant_id=contestant.id,
                    criteria_id=criteria_item.id,
                ).all()
            )
            scores_sum = sum(score.score for score in scores)
            score_count = len(scores)
            avg_raw = scores_sum / score_count if score_count else 0.0
            weighted_total = (
                (avg_raw / criteria_item.max_score) * criteria_item.weight
                if criteria_item.max_score
                else 0.0
            )
            criteria_raw_totals[criteria_item.id] = avg_raw
            criteria_weighted_totals[criteria_item.id] = weighted_total
            total_raw += avg_raw
            total_weighted += weighted_total
        total_weighted = min(total_weighted, 100.0)
        results.append(
            {
                "contestant": contestant.name,
                "total": total_weighted,
                "total_raw": total_raw,
                "criteria_totals": criteria_weighted_totals,
                "criteria_raw_totals": criteria_raw_totals,
            }
        )

    results.sort(key=lambda row: row["total"], reverse=True)
    return results
