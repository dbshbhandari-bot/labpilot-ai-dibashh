
import os

from flask import Flask, request
from flask_wtf.csrf import CSRFProtect

from app.database.db import create_tables


csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # Load the secret key from the environment.
    secret_key = os.environ.get("LABPILOT_SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "LABPILOT_SECRET_KEY is not configured. "
            "Set it before starting LabPilot AI."
        )

    app.config["SECRET_KEY"] = secret_key

    # Temporarily protect selected POST endpoints.
    app.config["WTF_CSRF_CHECK_DEFAULT"] = False

    csrf.init_app(app)

    # Register LabPilot AI blueprints.
    from app.routes.dashboard import dashboard_bp
    from app.routes.experiment_planner import experiment_planner_bp
    from app.routes.feedback import feedback_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(experiment_planner_bp)
    app.register_blueprint(feedback_bp)

    @app.before_request
    def protect_selected_forms():

        protected_endpoints = (
            "feedback.feedback_form",
            "experiment_planner.save_serial_dilution",
            "experiment_planner.save_ast",
            "experiment_planner.save_ast_methodology",
            "experiment_planner.add_ast_antibiotic",
            "experiment_planner.analyse_ast_experiment",
            "experiment_planner.update_ast_measurement",
        )

        if (
            request.method == "POST"
            and request.endpoint in protected_endpoints
        ):
            csrf.protect()

    # Create database tables if needed.
    create_tables()

    return app
