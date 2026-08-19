import sqlite3

DATABASE = "labpilot.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            ALTER TABLE serial_dilution_results
            ADD COLUMN experiment_title TEXT
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE serial_dilution_results
            ADD COLUMN sample_name TEXT
        """)
    except sqlite3.OperationalError:
        pass

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

    connection.commit()
    connection.close()