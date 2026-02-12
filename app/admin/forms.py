from flask_wtf import FlaskForm
from wtforms import FloatField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, NumberRange


class CompetitionForm(FlaskForm):
    name = StringField("Competition Name", validators=[DataRequired()])
    slug = StringField("Slug", validators=[DataRequired()])
    submit = SubmitField("Add Competition")


class JudgeForm(FlaskForm):
    name = StringField("Judge Name", validators=[DataRequired()])
    competition_id = SelectField("Competition", coerce=int)
    submit = SubmitField("Add Judge")


class ContestantForm(FlaskForm):
    name = StringField("Contestant Name", validators=[DataRequired()])
    competition_id = SelectField("Competition", coerce=int)
    submit = SubmitField("Add Contestant")


class CriteriaForm(FlaskForm):
    name = StringField("Criteria Name", validators=[DataRequired()])
    max_score = FloatField("Max Score", validators=[DataRequired(), NumberRange(min=0.1)])
    weight = FloatField("Weight (%)", validators=[DataRequired(), NumberRange(min=0.1)])
    competition_id = SelectField("Competition", coerce=int)
    submit = SubmitField("Add Criteria")


class AccountForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    role = SelectField("Role", choices=[("admin", "Admin"), ("tabulator", "Tabulator")])
    competition_id = SelectField("Competition", coerce=int)
    submit = SubmitField("Create Account")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=8)],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Update Password")


class ResetDatabaseForm(FlaskForm):
    password = PasswordField("Confirm Password", validators=[DataRequired()])
    reset_submit = SubmitField("Reset Database")
