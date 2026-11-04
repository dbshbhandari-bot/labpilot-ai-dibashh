
import os
import logging

import psycopg
from flask import Flask, render_template, request, redirect, url_for, abort


logger = logging.getLogger(__name__)

EXPERIMENTS = {
    "serial_dilution",
    "ast",
    "spectrophotometry",
}

ROLES = {
    "student",
    "lecturer",
    "researcher",
    "lab_professional",
    "other",
}


def create_public_app():
    app = Flask(__name__)

    secret_key = os.environ.get("LABPILOT_PUBLIC_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "LABPILOT_PUBLIC_SECRET_KEY is not configured."
        )

    app.config["SECRET_KEY"] = secret_key
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

    database_url = os.environ.get("DATABASE_URL")

    def get_connection():
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        return psycopg.connect(database_url, connect_timeout=10)

    def initialise_feedback_table():
        if not database_url:
            logger.warning("Feedback database not configured.")
            return

        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS public_feedback (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    experiment VARCHAR(50) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    ease SMALLINT NOT NULL
                        CHECK (ease BETWEEN 1 AND 5),
                    worked TEXT NOT NULL,
                    difficult TEXT NOT NULL,
                    improve TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @app.route("/")
    def home():
        return render_template("public_home.html")

    @app.route("/demo/serial-dilution")
    def serial_dilution_demo():
        return render_template(
            "public_demo.html",
            experiment="serial"
        )

    @app.route("/demo/ast")
    def ast_demo():
        return render_template(
            "public_demo.html",
            experiment="ast"
        )

    @app.route("/demo/spectrophotometry")
    def spectrophotometry_demo():
        return render_template(
            "public_demo.html",
            experiment="spectro"
        )

    @app.route("/feedback", methods=["GET", "POST"])
    def feedback_page():
        if request.method == "GET":
            return render_template("public_feedback.html")

        # Require same-origin browser submissions.
        origin = request.headers.get("Origin")
        if origin:
            from urllib.parse import urlsplit

            submitted_origin = urlsplit(origin)
            expected_origin = urlsplit(request.host_url)

            if (
                submitted_origin.scheme != expected_origin.scheme
                or submitted_origin.netloc != expected_origin.netloc
            ):
                abort(403)

        # Only accept standard form submissions.
        if request.mimetype != "application/x-www-form-urlencoded":
            abort(415)

        experiment = request.form.get("experiment", "")
        role = request.form.get("role", "")
        ease_raw = request.form.get("ease", "")
        worked = request.form.get("worked", "").strip()
        difficult = request.form.get("difficult", "").strip()
        improve = request.form.get("improve", "").strip()

        try:
            ease = int(ease_raw)
        except (TypeError, ValueError):
            abort(400, "Invalid rating.")

        if experiment not in EXPERIMENTS:
            abort(400, "Invalid experiment.")

        if role not in ROLES:
            abort(400, "Invalid role.")

        if ease not in range(1, 6):
            abort(400, "Invalid rating.")

        if any(
            len(value) > 2000
            for value in (worked, difficult, improve)
        ):
            abort(400, "Feedback exceeds the maximum length.")

        if not any((worked, difficult, improve)):
            abort(400, "Please provide at least one comment.")

        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO public_feedback
                    (experiment, role, ease,
                     worked, difficult, improve)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        experiment,
                        role,
                        ease,
                        worked,
                        difficult,
                        improve,
                    )
                )
        except psycopg.Error:
            logger.exception("Feedback submission failed")
            abort(503, "Feedback is temporarily unavailable.")

        return redirect(url_for("feedback_success"), code=303)

    @app.route("/feedback/success")
    def feedback_success():
        return (
            "<!doctype html><html lang='en'>"
            "<head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Feedback Received | LabPilot AI</title></head>"
            "<body style='font-family:Arial;background:#f6f8fc;"
            "color:#17233b;text-align:center;padding:80px 20px'>"
            "<h1>Thank you for your feedback!</h1>"
            "<p>Your suggestions have been recorded successfully.</p>"
            "<a href='/' style='color:#163b75'>Back to LabPilot AI</a>"
            "</body></html>"
        )

    initialise_feedback_table()

    return app


if __name__ == "__main__":
    application = create_public_app()
    application.run(
        host="127.0.0.1",
        port=5001,
        debug=False
    )
