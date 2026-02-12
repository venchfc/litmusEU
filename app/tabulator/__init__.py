from flask import Blueprint


tabulator_bp = Blueprint("tabulator", __name__, template_folder="../templates/tabulator")

from . import routes  # noqa: E402,F401
