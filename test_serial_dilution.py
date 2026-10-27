
from app import create_app
from app.database.db import get_connection

app = create_app()

MEASUREMENT_ID = 15


def get_measurement():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                antibiotic,
                zone_diameter,
                disk_strength,
                replicate_number,
                notes
            FROM ast_results
            WHERE id = ?
        """, (MEASUREMENT_ID,))

        return cursor.fetchone()

    finally:
        connection.close()


def test_negative_zone():

    before = get_measurement()

    if before is None:
        print("FAIL: Test measurement not found.")
        return

    print("BEFORE:", before)

    antibiotic, zone, strength, replicate, notes = before

    with app.test_client() as client:

        response = client.post(
            f"/experiments/ast/measurements/"
            f"{MEASUREMENT_ID}/update",
            data={
                "antibiotic": antibiotic,
                "zone_diameter": "-5",
                "disk_strength": "10",
                "replicate_number": str(replicate),
                "notes": notes or ""
            }
        )

    after = get_measurement()

    print("HTTP STATUS:", response.status_code)
    print("RESPONSE:", response.get_data(as_text=True))
    print("AFTER:", after)

    if response.status_code == 400 and before == after:
        print("PASS: Invalid zone rejected. Database unchanged.")
    else:
        print("FAIL: Check backend validation and database.")


if __name__ == "__main__":
    test_negative_zone()
