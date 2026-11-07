
import os
import logging
import secrets

import psycopg
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    session,
)
from werkzeug.security import check_password_hash


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

    # --------------------------------------------------
    # APPLICATION CONFIGURATION
    # --------------------------------------------------

    secret_key = os.environ.get("LABPILOT_PUBLIC_SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "LABPILOT_PUBLIC_SECRET_KEY is not configured."
        )

    app.config["SECRET_KEY"] = secret_key
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800

    database_url = os.environ.get("DATABASE_URL")

    founder_password_hash = os.environ.get(
        "LABPILOT_FOUNDER_PASSWORD_HASH"
    )

    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
    LOGIN_IDENTIFIER = "founder_global"

    # --------------------------------------------------
    # DATABASE CONNECTION
    # --------------------------------------------------

    def get_connection():
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured."
            )

        return psycopg.connect(
            database_url,
            connect_timeout=10
        )

    # --------------------------------------------------
    # INITIALISE DATABASE TABLES
    # --------------------------------------------------

    def initialise_feedback_table():
        if not database_url:
            logger.warning(
                "Feedback database not configured."
            )
            return

        with get_connection() as conn:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS public_feedback (
                    id BIGINT GENERATED ALWAYS
                        AS IDENTITY PRIMARY KEY,

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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                    founder_login_attempts (

                    identifier VARCHAR(64)
                        PRIMARY KEY,

                    failed_count INTEGER NOT NULL
                        DEFAULT 0,

                    locked_until TIMESTAMPTZ
                )
            """)

    # --------------------------------------------------
    # LOGIN CSRF PROTECTION
    # --------------------------------------------------

    def get_login_csrf_token():
        token = session.get(
            "founder_login_csrf"
        )

        if not token:
            token = secrets.token_urlsafe(32)

            session[
                "founder_login_csrf"
            ] = token

        return token

    def is_valid_login_csrf_token():
        submitted_token = request.form.get(
            "csrf_token",
            ""
        )

        expected_token = session.get(
            "founder_login_csrf",
            ""
        )

        return (
            bool(submitted_token)
            and bool(expected_token)
            and secrets.compare_digest(
                submitted_token,
                expected_token
            )
        )

    # --------------------------------------------------
    # LOGIN LOCKOUT PROTECTION
    # --------------------------------------------------

    def is_founder_locked():
        with get_connection() as conn:

            row = conn.execute("""
                SELECT
                    locked_until > CURRENT_TIMESTAMP

                FROM founder_login_attempts

                WHERE identifier = %s
            """, (
                LOGIN_IDENTIFIER,
            )).fetchone()

        return bool(row and row[0])

    def record_failed_login():
        with get_connection() as conn:

            conn.execute("""
                INSERT INTO founder_login_attempts
                    (
                        identifier,
                        failed_count,
                        locked_until
                    )

                VALUES (%s, 1, NULL)

                ON CONFLICT (identifier)

                DO UPDATE SET

                    failed_count = CASE

                        WHEN
                            founder_login_attempts.locked_until
                            IS NOT NULL

                            AND
                            founder_login_attempts.locked_until
                            <= CURRENT_TIMESTAMP

                        THEN 1

                        ELSE
                            founder_login_attempts.failed_count + 1

                    END,

                    locked_until = CASE

                        WHEN
                            founder_login_attempts.locked_until
                            IS NOT NULL

                            AND
                            founder_login_attempts.locked_until
                            <= CURRENT_TIMESTAMP

                        THEN NULL

                        WHEN
                            founder_login_attempts.failed_count + 1
                            >= %s

                        THEN
                            CURRENT_TIMESTAMP
                            + (%s * INTERVAL '1 minute')

                        ELSE
                            founder_login_attempts.locked_until

                    END
            """, (
                LOGIN_IDENTIFIER,
                MAX_LOGIN_ATTEMPTS,
                LOGIN_LOCKOUT_MINUTES
            ))

    def clear_failed_logins():
        with get_connection() as conn:

            conn.execute("""
                DELETE FROM founder_login_attempts

                WHERE identifier = %s
            """, (
                LOGIN_IDENTIFIER,
            ))

    # --------------------------------------------------
    # PRIVATE PAGE CACHE PROTECTION
    # --------------------------------------------------

    @app.after_request
    def prevent_founder_page_caching(response):

        if request.path.startswith("/founder/"):

            response.headers[
                "Cache-Control"
            ] = "no-store, private"

            response.headers[
                "Pragma"
            ] = "no-cache"

            response.headers[
                "X-Content-Type-Options"
            ] = "nosniff"

        return response

    # --------------------------------------------------
    # FOUNDER LOGIN
    # --------------------------------------------------

    @app.route(
        "/founder/login",
        methods=["GET", "POST"]
    )
    def founder_login():

        if request.method == "GET":

            return render_template(
                "founder_login.html",
                csrf_token=get_login_csrf_token(),
                error=None
            )

        if request.mimetype != (
            "application/x-www-form-urlencoded"
        ):
            abort(415)

        if not is_valid_login_csrf_token():
            abort(403)

        if not founder_password_hash:

            logger.error(
                "Founder password hash is not configured."
            )

            abort(503)

        if is_founder_locked():

            return render_template(
                "founder_login.html",
                csrf_token=get_login_csrf_token(),
                error=(
                    "Too many incorrect attempts. "
                    "Please try again in 15 minutes."
                )
            ), 429

        submitted_password = request.form.get(
            "password",
            ""
        )

        if check_password_hash(
            founder_password_hash,
            submitted_password
        ):

            clear_failed_logins()

            session.clear()

            session[
                "founder_authenticated"
            ] = True

            session.permanent = True

            return redirect(
                url_for("founder_feedback")
            )

        record_failed_login()

        return render_template(
            "founder_login.html",
            csrf_token=get_login_csrf_token(),
            error="Incorrect password."
        ), 401

    # --------------------------------------------------
    # FOUNDER LOGOUT
    # --------------------------------------------------

    @app.route(
        "/founder/logout",
        methods=["POST"]
    )
    def founder_logout():

        if not session.get(
            "founder_authenticated"
        ):
            return redirect(
                url_for("founder_login")
            )

        if request.mimetype != (
            "application/x-www-form-urlencoded"
        ):
            abort(415)

        submitted_token = request.form.get(
            "csrf_token",
            ""
        )

        expected_token = session.get(
            "founder_logout_csrf",
            ""
        )

        if not (
            submitted_token
            and expected_token
            and secrets.compare_digest(
                submitted_token,
                expected_token
            )
        ):
            abort(403)

        session.clear()

        return redirect(
            url_for("founder_login")
        )

    # --------------------------------------------------
    # PRIVATE FOUNDER FEEDBACK DASHBOARD
    # --------------------------------------------------

    @app.route(
        "/founder/feedback",
        methods=["GET"]
    )
    def founder_feedback():

        if not session.get(
            "founder_authenticated"
        ):

            return redirect(
                url_for("founder_login")
            )

        with get_connection() as conn:

            with conn.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        id,
                        experiment,
                        role,
                        ease,
                        worked,
                        difficult,
                        improve,
                        created_at AT TIME ZONE
                            'Europe/London'

                    FROM public_feedback

                    ORDER BY created_at DESC
                """)

                feedback_records = (
                    cursor.fetchall()
                )

        logout_token = secrets.token_urlsafe(32)

        session[
            "founder_logout_csrf"
        ] = logout_token

        return render_template(
            "founder_feedback.html",
            feedback_records=feedback_records,
            logout_csrf_token=logout_token
        )

    # --------------------------------------------------
    # PUBLIC HOME PAGE
    # --------------------------------------------------

    @app.route("/")
    def home():

        return render_template(
            "public_home.html"
        )

    # --------------------------------------------------
    # EXPERIMENT 1 — SERIAL DILUTION
    # --------------------------------------------------

    @app.route(
        "/demo/serial-dilution"
    )
    def serial_dilution_demo():

        return render_template(
            "public_demo.html",
            experiment="serial"
        )

    # --------------------------------------------------
    # EXPERIMENT 2 — AST
    # --------------------------------------------------

    @app.route("/demo/ast")
    def ast_demo():

        return render_template(
            "public_demo.html",
            experiment="ast"
        )

    # --------------------------------------------------
    # EXPERIMENT 3 — SPECTROPHOTOMETRY
    # --------------------------------------------------

    @app.route(
        "/demo/spectrophotometry"
    )
    def spectrophotometry_demo():

        return render_template(
            "public_demo.html",
            experiment="spectro"
        )

    # --------------------------------------------------
    # PUBLIC CUSTOMER FEEDBACK FORM
    # --------------------------------------------------

    @app.route(
        "/feedback",
        methods=["GET", "POST"]
    )
    def feedback_page():

        if request.method == "GET":

            return render_template(
                "public_feedback.html"
            )

        # Check submission origin when supplied.

        origin = request.headers.get(
            "Origin"
        )

        if origin:

            from urllib.parse import urlsplit

            submitted_origin = urlsplit(
                origin
            )

            expected_origin = urlsplit(
                request.host_url
            )

            if (
                submitted_origin.scheme
                != expected_origin.scheme

                or

                submitted_origin.netloc
                != expected_origin.netloc
            ):
                abort(403)

        # Only accept standard HTML form data.

        if request.mimetype != (
            "application/x-www-form-urlencoded"
        ):
            abort(415)

        experiment = request.form.get(
            "experiment",
            ""
        )

        role = request.form.get(
            "role",
            ""
        )

        ease_raw = request.form.get(
            "ease",
            ""
        )

        worked = request.form.get(
            "worked",
            ""
        ).strip()

        difficult = request.form.get(
            "difficult",
            ""
        ).strip()

        improve = request.form.get(
            "improve",
            ""
        ).strip()

        # Validate rating.

        try:
            ease = int(ease_raw)

        except (TypeError, ValueError):

            abort(
                400,
                "Invalid rating."
            )

        # Validate experiment.

        if experiment not in EXPERIMENTS:

            abort(
                400,
                "Invalid experiment."
            )

        # Validate user role.

        if role not in ROLES:

            abort(
                400,
                "Invalid role."
            )

        # Validate ease-of-use score.

        if ease not in range(1, 6):

            abort(
                400,
                "Invalid rating."
            )

        # Validate feedback length.

        if any(
            len(value) > 2000
            for value in (
                worked,
                difficult,
                improve
            )
        ):

            abort(
                400,
                "Feedback exceeds the maximum length."
            )

        # Require at least one written comment.

        if not any((
            worked,
            difficult,
            improve
        )):

            abort(
                400,
                "Please provide at least one comment."
            )

        # Save customer feedback.

        try:

            with get_connection() as conn:

                conn.execute(
                    """
                    INSERT INTO public_feedback
                    (
                        experiment,
                        role,
                        ease,
                        worked,
                        difficult,
                        improve
                    )

                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        experiment,
                        role,
                        ease,
                        worked,
                        difficult,
                        improve
                    )
                )

        except psycopg.Error:

            logger.exception(
                "Feedback submission failed"
            )

            abort(
                503,
                "Feedback is temporarily unavailable."
            )

        return redirect(
            url_for("feedback_success"),
            code=303
        )

    # --------------------------------------------------
    # FEEDBACK SUCCESS PAGE
    # --------------------------------------------------

    @app.route("/feedback/success")
    def feedback_success():

        return (
            "<!doctype html><html lang='en'>"
            "<head><meta charset='utf-8'>"
            "<meta name='viewport' "
            "content='width=device-width,initial-scale=1'>"
            "<title>Feedback Received | LabPilot AI</title>"
            "</head>"
            "<body style='font-family:Arial;"
            "background:#f6f8fc;"
            "color:#17233b;"
            "text-align:center;"
            "padding:80px 20px'>"
            "<h1>Thank you for your feedback!</h1>"
            "<p>Your suggestions have been "
            "recorded successfully.</p>"
            "<a href='/' style='color:#163b75'>"
            "Back to LabPilot AI</a>"
            "</body></html>"
        )

    # --------------------------------------------------
    # INITIALISE AND RETURN APPLICATION
    # --------------------------------------------------

    initialise_feedback_table()

    return app


# ------------------------------------------------------
# LOCAL DEVELOPMENT
# ------------------------------------------------------

if __name__ == "__main__":

    application = create_public_app()

    application.run(
        host="127.0.0.1",
        port=5001,
        debug=False
    )
