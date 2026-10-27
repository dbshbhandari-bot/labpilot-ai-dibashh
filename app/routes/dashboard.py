
from flask import Blueprint, render_template
from app.database.db import get_connection
from datetime import date, timedelta

dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


@dashboard_bp.route("/")
def dashboard():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Total number of saved experiments
        cursor.execute("""
            SELECT COUNT(*)
            FROM experiments
        """)
        total_experiments = cursor.fetchone()[0]

        # Number of Serial Dilution experiments
        cursor.execute("""
            SELECT COUNT(*)
            FROM experiments
            WHERE experiment = ?
        """, ("Serial Dilution & CFU Analysis",))

        serial_dilution_count = cursor.fetchone()[0]

        # Number of AST experiments
        cursor.execute("""
            SELECT COUNT(*)
            FROM experiments
            WHERE experiment = ?
        """, ("Antibiotic Susceptibility Testing",))

        ast_count = cursor.fetchone()[0]

        # Retrieve the five most recent experiments
        cursor.execute("""
            SELECT
                id,
                experiment,
                research_question,
                created_at
            FROM experiments
            ORDER BY created_at DESC, id DESC
            LIMIT 5
        """)

        recent_experiments = cursor.fetchall()

        # Retrieve experiment activity for the last 7 days.
        today = date.today()
        start_date = today - timedelta(days=6)

        cursor.execute("""
            SELECT
                DATE(created_at) AS experiment_date,
                COUNT(*) AS experiment_count
            FROM experiments
            WHERE DATE(created_at) BETWEEN ? AND ?
            GROUP BY DATE(created_at)
            ORDER BY experiment_date ASC
        """, (
            start_date.isoformat(),
            today.isoformat()
        ))

        activity_rows = cursor.fetchall()

        # Create a lookup of dates and experiment counts.
        activity_lookup = {
            row[0]: row[1]
            for row in activity_rows
        }

        # Include days with zero experiments.
        activity_labels = []
        activity_counts = []

        for day_offset in range(7):
            current_day = start_date + timedelta(days=day_offset)

            activity_labels.append(
                current_day.strftime("%d %b")
            )

            activity_counts.append(
                activity_lookup.get(
                    current_day.isoformat(),
                    0
                )
            )


    finally:
        connection.close()

    return render_template(
        "dashboard.html",
        total_experiments=total_experiments,
        serial_dilution_count=serial_dilution_count,
        ast_count=ast_count,
        recent_experiments=recent_experiments,
        activity_labels=activity_labels,
        activity_counts=activity_counts
    )