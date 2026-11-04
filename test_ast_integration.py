
import os
import sqlite3
import subprocess
import sys

import pytest


@pytest.fixture
def test_database(tmp_path):
    """
    Create a temporary SQLite database.

    This keeps test measurements separate from
    the real LabPilot AI database.
    """

    database_path = tmp_path / "labpilot_test.db"

    connection = sqlite3.connect(database_path)

    try:
        connection.execute("""
            CREATE TABLE ast_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                antibiotic TEXT NOT NULL,
                zone_diameter REAL NOT NULL,
                replicate_number INTEGER NOT NULL,
                disk_strength TEXT
            )
        """)

        # Two measurements with the same replicate number.
        # LabPilot AI should reject this group.
        connection.executemany("""
            INSERT INTO ast_results (
                experiment_id,
                antibiotic,
                zone_diameter,
                replicate_number,
                disk_strength
            )
            VALUES (?, ?, ?, ?, ?)
        """, [
            (999, "Ciprofloxacin", 15.0, 1, "5 µg"),
            (999, "Ciprofloxacin", 18.0, 1, "5 µg"),
        ])

        connection.commit()

    finally:
        connection.close()

    return database_path


def test_duplicate_ast_replicates_are_excluded(test_database):
    """
    Verify that the real Flask AST analysis route
    excludes duplicate replicate numbers.
    """

    # Copy the current environment.
    environment = os.environ.copy()

    # Point the test process to the temporary database.
    environment["LABPILOT_DATABASE"] = str(test_database)

    # Use a secret key only for this test process.
    environment["LABPILOT_SECRET_KEY"] = (
        "temporary-test-secret-key-not-for-production"
    )

    # Run Flask in a separate Python process.
    # This ensures the database path is configured
    # before the application imports its database module.
    script = """
from flask import session
from flask_wtf.csrf import generate_csrf

from app import create_app


app = create_app()
app.config["TESTING"] = True


with app.test_client() as client:

    # Generate a valid CSRF token.
    with app.test_request_context():
        token = generate_csrf()
        csrf_session_value = session["csrf_token"]

    # Put the matching CSRF session value
    # into the test client's session.
    with client.session_transaction() as client_session:
        client_session["csrf_token"] = csrf_session_value

    # Submit the real AST statistical analysis request.
    response = client.post(
        "/experiments/ast/999/analyse",
        data={
            "comparability_confirmed": "yes",
            "csrf_token": token
        }
    )

    # The request must reach the analysis route.
    assert response.status_code == 200, (
        response.status_code,
        response.get_data(as_text=True)[:500]
    )

    # Duplicate replicate numbers must be rejected.
    assert (
        b"Invalid or duplicate replicate numbers."
        in response.data
    ), response.get_data(as_text=True)[:500]
"""

    # Execute the test against the isolated database.
    completed = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False
    )

    # Report any failure from the Flask test process.
    assert completed.returncode == 0, (
        completed.stdout + completed.stderr
    )
