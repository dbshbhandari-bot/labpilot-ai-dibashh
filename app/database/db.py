
import os
import sqlite3

DATABASE = os.environ.get(
    "LABPILOT_DATABASE",
    "labpilot.db"
)


def get_connection():
    return sqlite3.connect(DATABASE)


def create_tables():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # MAIN EXPERIMENTS TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area TEXT NOT NULL,
                experiment TEXT NOT NULL,
                research_question TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                independent_variable TEXT NOT NULL,
                dependent_variable TEXT NOT NULL,
                controls TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # SERIAL DILUTION RESULTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS serial_dilution_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER,
                colony_count REAL NOT NULL,
                dilution REAL NOT NULL,
                volume_ml REAL NOT NULL,
                cfu_per_ml REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(id)
            )
        """)

        cursor.execute("""
            PRAGMA table_info(serial_dilution_results)
        """)

        existing_columns = {
            column[1] for column in cursor.fetchall()
        }

        if "experiment_title" not in existing_columns:
            cursor.execute("""
                ALTER TABLE serial_dilution_results
                ADD COLUMN experiment_title TEXT
            """)

        if "sample_name" not in existing_columns:
            cursor.execute("""
                ALTER TABLE serial_dilution_results
                ADD COLUMN sample_name TEXT
            """)

        if "plate_label" not in existing_columns:
            cursor.execute("""
                ALTER TABLE serial_dilution_results
                ADD COLUMN plate_label TEXT
            """)

        # ANTIBIOTIC SUSCEPTIBILITY RESULTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ast_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                experiment_title TEXT NOT NULL,
                organism TEXT NOT NULL,
                sample_name TEXT NOT NULL,
                antibiotic TEXT NOT NULL,
                zone_diameter REAL NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (experiment_id)
                    REFERENCES experiments(id),
                CHECK (zone_diameter >= 0)
            )
        """)

        cursor.execute("PRAGMA table_info(ast_results)")

        ast_columns = {
            column[1] for column in cursor.fetchall()
        }

        if "replicate_number" not in ast_columns:
            cursor.execute("""
                ALTER TABLE ast_results
                ADD COLUMN replicate_number INTEGER
                NOT NULL DEFAULT 1
                CHECK (replicate_number >= 1)
            """)

        if "testing_method" not in ast_columns:
            cursor.execute("""
                ALTER TABLE ast_results
                ADD COLUMN testing_method TEXT
            """)

        if "disk_strength" not in ast_columns:
            cursor.execute("""
                ALTER TABLE ast_results
                ADD COLUMN disk_strength TEXT
            """)

        if "interpretation_standard" not in ast_columns:
            cursor.execute("""
                ALTER TABLE ast_results
                ADD COLUMN interpretation_standard TEXT
            """)

        # SPECTROPHOTOMETRY RESULTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spectrophotometry_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_title TEXT NOT NULL,
                sample_name TEXT NOT NULL,
                slope REAL NOT NULL,
                intercept REAL NOT NULL,
                r_squared REAL NOT NULL,
                unknown_absorbance REAL NOT NULL,
                unknown_concentration REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ORIGINAL CALIBRATION MEASUREMENTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spectrophotometry_standards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                concentration REAL NOT NULL,
                absorbance REAL NOT NULL,
                FOREIGN KEY (result_id)
                    REFERENCES spectrophotometry_results(id)
            )
        """)

        cursor.execute("""
            PRAGMA table_info(spectrophotometry_results)
        """)

        spectro_columns = {
            column[1] for column in cursor.fetchall()
        }

        if "wavelength" not in spectro_columns:
            cursor.execute("""
                ALTER TABLE spectrophotometry_results
                ADD COLUMN wavelength REAL
            """)

        if "concentration_unit" not in spectro_columns:
            cursor.execute("""
                ALTER TABLE spectrophotometry_results
                ADD COLUMN concentration_unit TEXT
            """)

        # CUSTOMER FEEDBACK TABLE
        # This is independent of the existing-column checks.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                experiment TEXT NOT NULL
                    CHECK (
                        experiment IN (
                            'Serial Dilution & CFU',
                            'Antibiotic Susceptibility (AST)',
                            'Spectrophotometry'
                        )
                    ),

                user_role TEXT NOT NULL
                    CHECK (
                        user_role IN (
                            'Student',
                            'Lecturer',
                            'Researcher',
                            'Laboratory Professional',
                            'Other'
                        )
                    ),

                usability_rating INTEGER NOT NULL
                    CHECK (usability_rating BETWEEN 1 AND 5),

                what_worked TEXT,
                difficulties TEXT,
                suggestions TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_spectrophotometry_result(
    experiment_title,
    sample_name,
    concentrations,
    absorbances,
    unknown_absorbance,
    result,
    wavelength,
    concentration_unit
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO spectrophotometry_results (
                experiment_title,
                sample_name,
                slope,
                intercept,
                r_squared,
                unknown_absorbance,
                unknown_concentration,
                wavelength,
                concentration_unit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment_title,
            sample_name,
            result["slope"],
            result["intercept"],
            result["r_squared"],
            float(unknown_absorbance),
            result["unknown_concentration"],
            float(wavelength),
            concentration_unit
        ))

        result_id = cursor.lastrowid

        for concentration, absorbance in zip(
            concentrations,
            absorbances
        ):
            cursor.execute("""
                INSERT INTO spectrophotometry_standards (
                    result_id,
                    concentration,
                    absorbance
                )
                VALUES (?, ?, ?)
            """, (
                result_id,
                float(concentration),
                float(absorbance)
            ))

        connection.commit()
        return result_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
