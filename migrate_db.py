import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "student_app.db"

def migrate():
    print(f"Connecting to {DATABASE_PATH}")
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.execute("ALTER TABLE prediction_history ADD COLUMN subject TEXT")
        connection.commit()
        print("Successfully added 'subject' column.")
    except sqlite3.OperationalError as e:
        print(f"Error or already exists: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    migrate()
