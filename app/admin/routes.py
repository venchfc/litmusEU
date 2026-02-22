from datetime import datetime

from sqlalchemy import func

from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import admin_bp
from .forms import (
    AccountForm,
    ChangePasswordForm,
    CompetitionForm,
    ContestantForm,
    CriteriaForm,
    EventTitleForm,
    JudgeForm,
    JudgeAssignForm,
    ResetDatabaseForm,
)
from ..extensions import db
from ..models import (
    Competition,
    Contestant,
    Criteria,
    Event,
    Judge,
    Score,
    User,
    judge_competitions,
)
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
        "judge_accounts": User.query.filter_by(role="judge").count(),
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
    active_event = _get_active_event()
    competition_status = {}
    for competition in competitions_list:
        judge_count = _competition_judges_query(competition.id).count()
        contestant_count = Contestant.query.filter_by(competition_id=competition.id).count()
        criteria_count = Criteria.query.filter_by(competition_id=competition.id).count()
        expected_scores = judge_count * contestant_count * criteria_count
        if expected_scores == 0:
            competition_status[competition.id] = False
            continue

        score_count = (
            Score.query.filter_by(
                event_id=active_event.id,
                competition_id=competition.id,
            )
            .with_entities(func.count(Score.id))
            .scalar()
        )
        competition_status[competition.id] = score_count >= expected_scores

    return render_template(
        "admin/competitions.html",
        competitions=competitions_list,
        competition_status=competition_status,
        form=form,
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
    competitions_list = Competition.query.order_by(Competition.name).all()
    return render_template(
        "admin/judges.html",
        competitions=competitions_list,
    )


@admin_bp.route("/judges/manage/<int:competition_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_judges(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    judge_form = JudgeForm(prefix="new")
    assign_form = JudgeAssignForm(prefix="assign")
    judge_form.competition_id.choices = [(competition.id, competition.name)]
    judge_form.competition_id.data = competition.id

    assigned_judges = _competition_judges_query(competition.id).all()
    assigned_judge_ids = {judge.id for judge in assigned_judges}
    available_judges = Judge.query.order_by(Judge.name).all()
    assign_form.judge_id.choices = [
        (judge.id, judge.name)
        for judge in available_judges
        if judge.id not in assigned_judge_ids
    ]

    if "new-submit" in request.form and judge_form.validate_on_submit():
        username = judge_form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "warning")
            return redirect(url_for("admin.manage_judges", competition_id=competition.id))

        judge = Judge(name=judge_form.name.data.strip(), competition_id=competition.id)
        db.session.add(judge)
        db.session.flush()
        if competition not in judge.competitions:
            judge.competitions.append(competition)

        user = User(
            username=username,
            role="judge",
            competition_id=None,
            judge_id=judge.id,
            is_primary=False,
        )
        user.set_password(judge_form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Judge account created.", "success")
        return redirect(url_for("admin.manage_judges", competition_id=competition.id))

    if "assign-submit" in request.form and assign_form.validate_on_submit():
        judge = Judge.query.get_or_404(assign_form.judge_id.data)
        if judge.id in assigned_judge_ids:
            flash("Judge already assigned to this competition.", "warning")
            return redirect(url_for("admin.manage_judges", competition_id=competition.id))
        judge.competitions.append(competition)
        db.session.commit()
        flash("Judge assigned to competition.", "success")
        return redirect(url_for("admin.manage_judges", competition_id=competition.id))

    judge_users = {}
    if assigned_judge_ids:
        judge_users = {
            user.judge_id: user
            for user in User.query.filter_by(role="judge")
            .filter(User.judge_id.in_(assigned_judge_ids))
            .all()
            if user.judge_id
        }
    return render_template(
        "admin/judges_manage.html",
        form=judge_form,
        assign_form=assign_form,
        competition=competition,
        judges=assigned_judges,
        judge_users=judge_users,
    )


@admin_bp.route("/judges/delete/<int:judge_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_judge(judge_id):
    judge = Judge.query.get_or_404(judge_id)
    competition_id = request.form.get("competition_id", type=int)
    assigned_competitions = {competition.id for competition in judge.competitions}
    if judge.competition_id:
        assigned_competitions.add(judge.competition_id)

    if competition_id and competition_id in assigned_competitions:
        if judge.competition_id == competition_id:
            remaining = [cid for cid in assigned_competitions if cid != competition_id]
            if remaining:
                judge.competition_id = remaining[0]
            else:
                Score.query.filter_by(judge_id=judge.id).delete(synchronize_session=False)
                User.query.filter_by(judge_id=judge.id).delete(synchronize_session=False)
                db.session.delete(judge)
                db.session.commit()
                flash("Judge deleted.", "success")
                return redirect(url_for("admin.manage_judges", competition_id=competition_id))

        db.session.execute(
            judge_competitions.delete().where(
                (judge_competitions.c.judge_id == judge.id)
                & (judge_competitions.c.competition_id == competition_id)
            )
        )
        db.session.commit()
        flash("Judge removed from competition.", "success")
        return redirect(url_for("admin.manage_judges", competition_id=competition_id))

    Score.query.filter_by(judge_id=judge.id).delete(synchronize_session=False)
    User.query.filter_by(judge_id=judge.id).delete(synchronize_session=False)
    db.session.delete(judge)
    db.session.commit()
    flash("Judge deleted.", "success")
    return redirect(url_for("admin.judges"))


@admin_bp.route("/contestants", methods=["GET", "POST"])
@login_required
@role_required("admin")
def contestants():
    competitions_list = Competition.query.order_by(Competition.name).all()
    return render_template(
        "admin/contestants.html",
        competitions=competitions_list,
    )


@admin_bp.route("/contestants/manage/<int:competition_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_contestants(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    form = ContestantForm()
    form.competition_id.choices = [(competition.id, competition.name)]
    form.competition_id.data = competition.id

    if form.validate_on_submit():
        db.session.add(
            Contestant(
                name=form.name.data.strip(), competition_id=competition.id
            )
        )
        db.session.commit()
        flash("Contestant added.", "success")
        return redirect(
            url_for("admin.manage_contestants", competition_id=competition.id)
        )

    contestants_list = (
        Contestant.query.filter_by(competition_id=competition.id)
        .order_by(Contestant.name)
        .all()
    )
    return render_template(
        "admin/contestants_manage.html",
        form=form,
        competition=competition,
        contestants=contestants_list,
    )


@admin_bp.route("/contestants/delete/<int:contestant_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_contestant(contestant_id):
    contestant = Contestant.query.get_or_404(contestant_id)
    db.session.delete(contestant)
    db.session.commit()
    flash("Contestant deleted.", "success")
    return redirect(url_for("admin.manage_contestants", competition_id=contestant.competition_id))


@admin_bp.route("/criteria", methods=["GET", "POST"])
@login_required
@role_required("admin")
def criteria():
    form = CriteriaForm()
    competitions_list = Competition.query.order_by(Competition.name).all()
    competition_id = request.args.get("competition_id", type=int)
    if not competition_id and competitions_list:
        competition_id = competitions_list[0].id

    competition = Competition.query.get(competition_id) if competition_id else None
    if competition:
        form.competition_id.choices = [(competition.id, competition.name)]
        form.competition_id.data = competition.id

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
        competition=competition,
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
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash("Username already exists.", "warning")
        else:
            user = User(
                username=form.username.data.strip(),
                role=form.role.data,
                is_primary=False,
            )
            user.competition_id = None
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash("Account created.", "success")
        return redirect(url_for("admin.accounts"))

    users = User.query.filter_by(role="admin").order_by(User.username).all()
    return render_template(
        "admin/accounts.html",
        form=form,
        users=users,
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
    if competition:
        criteria_items = Criteria.query.filter_by(competition_id=competition.id).order_by(Criteria.name).all()
        results_rows = _calculate_results(event.id, competition.id)

    events = Event.query.filter_by(status="active").order_by(Event.created_at.desc()).all()
    return render_template(
        "admin/results.html",
        competitions=competitions_list,
        events=events,
        event=event,
        competition=competition,
        results=results_rows,
        criteria_items=criteria_items,
    )


@admin_bp.route("/scoring")
@login_required
@role_required("admin")
def scoring():
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
    judge_breakdown = []
    has_scores = False

    if competition:
        criteria_items = Criteria.query.filter_by(competition_id=competition.id).order_by(Criteria.name).all()
        judges = _competition_judges_query(competition.id).all()
        contestants = (
            Contestant.query.filter_by(competition_id=competition.id)
            .order_by(Contestant.name)
            .all()
        )
        scores = Score.query.filter_by(
            event_id=event.id,
            competition_id=competition.id,
        ).all()

        has_scores = len(scores) > 0
        score_lookup = {}
        judge_ids_with_scores = set()
        for score in scores:
            score_lookup[(score.judge_id, score.contestant_id, score.criteria_id)] = score.score
            judge_ids_with_scores.add(score.judge_id)

        for judge in judges:
            if judge.id not in judge_ids_with_scores:
                continue
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

    events = Event.query.filter_by(status="active").order_by(Event.created_at.desc()).all()
    return render_template(
        "admin/scoring.html",
        competitions=competitions_list,
        events=events,
        event=event,
        competition=competition,
        criteria_items=criteria_items,
        judge_breakdown=judge_breakdown,
        has_scores=has_scores,
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
    events = Event.query.filter_by(status="completed").order_by(Event.created_at.desc()).all()
    competitions = Competition.query.order_by(Competition.name).all()

    event_groups = [
        {
            "event": event,
            "competitions": competitions,
        }
        for event in events
    ]

    return render_template(
        "admin/history.html",
        event_groups=event_groups,
    )


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@role_required("admin")
def settings():
    reset_form = ResetDatabaseForm(prefix="reset")
    password_form = ChangePasswordForm(prefix="pw")
    event_form = EventTitleForm(prefix="event")
    active_event = _get_active_event()
    if request.method == "GET" and active_event:
        event_form.name.data = active_event.name

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
        elif "event-submit" in request.form:
            if event_form.validate_on_submit():
                active_event.name = event_form.name.data.strip()
                db.session.commit()
                flash("Event title updated.", "success")
                return redirect(url_for("admin.settings"))

    return render_template(
        "admin/settings.html",
        reset_form=reset_form,
        password_form=password_form,
        event_form=event_form,
        active_event=active_event,
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

    flash("Event closed and archived. New event started and setup cleared.", "success")
    return redirect(url_for("admin.history"))


def _build_judge_breakdown(event_id, competition_id, criteria_items):
    judges = _competition_judges_query(competition_id).all()
    contestants = (
        Contestant.query.filter_by(competition_id=competition_id)
        .order_by(Contestant.name)
        .all()
    )
    scores = Score.query.filter_by(
        event_id=event_id,
        competition_id=competition_id,
    ).all()

    score_lookup = {}
    for score in scores:
        score_lookup[(score.judge_id, score.contestant_id, score.criteria_id)] = score.score

    judge_breakdown = []
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
    return judge_breakdown


@admin_bp.route("/history/results")
@login_required
@role_required("admin")
def history_results():
    event_id = request.args.get("event_id", type=int)
    competition_id = request.args.get("competition_id", type=int)
    event = Event.query.get_or_404(event_id)
    competition = Competition.query.get_or_404(competition_id)
    criteria_items = Criteria.query.filter_by(competition_id=competition.id).order_by(Criteria.name).all()
    results_rows = _calculate_results(event.id, competition.id)
    judge_breakdown = _build_judge_breakdown(event.id, competition.id, criteria_items)

    return render_template(
        "admin/history_results.html",
        event=event,
        competition=competition,
        results=results_rows,
        criteria_items=criteria_items,
        judge_breakdown=judge_breakdown,
    )


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
