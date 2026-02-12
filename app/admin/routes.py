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
    return render_template(
        "admin/criteria.html",
        form=form,
        competitions=competitions_list,
        criteria=criteria_list,
        selected_competition=competition_id,
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
    results_rows = []
    if competition:
        results_rows = _calculate_results(event.id, competition.id)

    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template(
        "admin/results.html",
        competitions=competitions_list,
        events=events,
        event=event,
        competition=competition,
        results=results_rows,
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

    pdf_bytes = render_results_pdf(event, competition, results_rows)
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
    events = Event.query.filter_by(status="completed").order_by(Event.completed_at.desc()).all()
    return render_template("admin/history.html", events=events)


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
    criteria_items = Criteria.query.filter_by(competition_id=competition_id).all()

    results = []
    for contestant in contestants:
        total = 0.0
        for criteria_item in criteria_items:
            scores = (
                Score.query.filter_by(
                    event_id=event_id,
                    competition_id=competition_id,
                    contestant_id=contestant.id,
                    criteria_id=criteria_item.id,
                ).all()
            )
            for score in scores:
                total += score.score * criteria_item.weight
        results.append({"contestant": contestant.name, "total": total})

    results.sort(key=lambda row: row["total"], reverse=True)
    return results
