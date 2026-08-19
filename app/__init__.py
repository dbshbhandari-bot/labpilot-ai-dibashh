from flask import Flask
from app.database.db import create_tables

def create_app():
    app = Flask(__name__)

    from app.routes.dashboard import dashboard_bp
    from app.routes.experiment_planner import experiment_planner_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(experiment_planner_bp)
    create_tables()
    return app