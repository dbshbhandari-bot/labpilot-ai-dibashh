
import sqlite3

DATABASE = "labpilot.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    # Create the main experiments table
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

    # Create the serial dilution results table
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

    # Check which columns already exist
    cursor.execute("PRAGMA table_info(serial_dilution_results)")

    existing_columns = {
        column[1] for column in cursor.fetchall()
    }

    # Add experiment title if missing
    if "experiment_title" not in existing_columns:
        cursor.execute("""
            ALTER TABLE serial_dilution_results
            ADD COLUMN experiment_title TEXT
        """)

    # Add sample name if missing
    if "sample_name" not in existing_columns:
        cursor.execute("""
            ALTER TABLE serial_dilution_results
            ADD COLUMN sample_name TEXT
        """)

    # Add plate label for multiple plate measurements
    if "plate_label" not in existing_columns:
        cursor.execute("""
            ALTER TABLE serial_dilution_results
            ADD COLUMN plate_label TEXT
        """)


    # Create the antibiotic susceptibility results table
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

    # Add replicate number to AST measurements
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

    # Add experimental-method documentation fields
    # to existing AST results without deleting records.

    cursor.execute("PRAGMA table_info(ast_results)")

    ast_columns = {
        column[1]
        for column in cursor.fetchall()
    }

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

    connection.commit()
    connection.close()
