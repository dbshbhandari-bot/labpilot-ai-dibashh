
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.database.db import get_connection


feedback_bp = Blueprint("feedback", __name__)

EXPERIMENTS = (
    "Serial Dilution & CFU",
    "Antibiotic Susceptibility (AST)",
    "Spectrophotometry",
)

USER_ROLES = (
    "Student",
    "Lecturer",
    "Researcher",
    "Laboratory Professional",
    "Other",
)


@feedback_bp.route("/feedback", methods=["GET", "POST"])
def feedback_form():
    if request.method == "POST":
        experiment = request.form.get("experiment", "").strip()
        user_role = request.form.get("user_role", "").strip()
        rating_text = request.form.get("usability_rating", "").strip()

        what_worked = request.form.get("what_worked", "").strip()
        difficulties = request.form.get("difficulties", "").strip()
        suggestions = request.form.get("suggestions", "").strip()

        # Validate experiment and user role.
        if experiment not in EXPERIMENTS:
            flash("Please select a valid experiment.", "error")
            return redirect(url_for("feedback.feedback_form"))

        if user_role not in USER_ROLES:
            flash("Please select a valid user role.", "error")
            return redirect(url_for("feedback.feedback_form"))

        # Validate the usability rating.
        try:
            usability_rating = int(rating_text)
        except ValueError:
            flash("Please select a rating between 1 and 5.", "error")
            return redirect(url_for("feedback.feedback_form"))

        if usability_rating not in range(1, 6):
            flash("Please select a rating between 1 and 5.", "error")
            return redirect(url_for("feedback.feedback_form"))

        # Limit the length of written feedback.
        if any(
            len(value) > 2000
            for value in (what_worked, difficulties, suggestions)
        ):
            flash("Each written response must be under 2000 characters.", "error")
            return redirect(url_for("feedback.feedback_form"))

        connection = get_connection()

        try:
            connection.execute(
                """
                INSERT INTO user_feedback (
                    experiment,
                    user_role,
                    usability_rating,
                    what_worked,
                    difficulties,
                    suggestions
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment,
                    user_role,
                    usability_rating,
                    what_worked,
                    difficulties,
                    suggestions,
                ),
            )

            connection.commit()

        except sqlite3.Error:
            connection.rollback()
            raise

        finally:
            connection.close()

        flash("Thank you! Your feedback has been saved.", "success")
        return redirect(url_for("feedback.feedback_form"))

    return render_template(
        "feedback.html",
        experiments=EXPERIMENTS,
        user_roles=USER_ROLES,
    )
