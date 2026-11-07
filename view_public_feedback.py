
import os
from pathlib import Path
from datetime import timezone

import psycopg


# Read the database URL from your private .env file.
env_file = Path(__file__).resolve().parent / ".env"

if not env_file.exists():
    raise RuntimeError(".env file not found.")

database_url = None

for line in env_file.read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        database_url = line.split("=", 1)[1].strip()
        break

if not database_url:
    raise RuntimeError("DATABASE_URL is missing from .env")


# Connect to the public feedback database (read-only).
with psycopg.connect(database_url) as connection:
    with connection.cursor() as cursor:
        cursor.execute("BEGIN READ ONLY")

        cursor.execute("""
            SELECT
                id,
                experiment,
                role,
                ease,
                worked,
                difficult,
                improve,
                created_at AT TIME ZONE 'Europe/London'
            FROM public_feedback
            ORDER BY created_at DESC
        """)

        feedback = cursor.fetchall()

print("\nLABPILOT AI — PUBLIC FEEDBACK")
print("=" * 55)
print(f"Total feedback submissions: {len(feedback)}")

for record in feedback:
    (
        feedback_id,
        experiment,
        role,
        rating,
        worked,
        difficult,
        improve,
        submitted_at,
    ) = record

    print("\n" + "-" * 55)
    print(f"Feedback ID: {feedback_id}")
    print(f"Date & time (UK): {submitted_at:%d %B %Y, %I:%M %p}")
    print(f"Experiment: {experiment}")
    print(f"Role: {role}")
    print(f"Ease of use: {rating}/5")
    print(f"What worked well: {worked}")
    print(f"Difficulties: {difficult}")
    print(f"Suggestions: {improve}")

print("\nFinished reading feedback.")

import csv
from datetime import datetime

# Save original feedback records in the existing evidence folder.
evidence_folder = Path(__file__).resolve().parent / "evidence"
evidence_folder.mkdir(exist_ok=True)

backup_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup_file = evidence_folder / f"public_feedback_{backup_date}.csv"

with backup_file.open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.writer(file)

    writer.writerow([
        "Feedback ID",
        "Experiment",
        "User Role",
        "Ease Rating",
        "What Worked",
        "Difficulties",
        "Suggestions",
        "Submitted At (UK Time)"
    ])

    for record in feedback:
        writer.writerow(record)

print(f"\nBackup saved successfully: {backup_file}")
