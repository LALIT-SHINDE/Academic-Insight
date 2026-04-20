import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "student_app.db"

def migrate():
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()
    
    try:
        # 1. Create a new table with nullable user_id (removed NOT NULL)
        cursor.execute("""
            CREATE TABLE prediction_history_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                student_name TEXT NOT NULL,
                attendance REAL NOT NULL,
                mid_marks REAL NOT NULL,
                assignments REAL NOT NULL,
                study_hours REAL NOT NULL,
                subject TEXT,
                predicted_label TEXT NOT NULL,
                prediction_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 2. Copy data
        cursor.execute("""
            INSERT INTO prediction_history_new 
            SELECT id, user_id, student_name, attendance, mid_marks, assignments, 
                   study_hours, subject, predicted_label, prediction_text, created_at
            FROM prediction_history
        """)
        
        # 3. Swap tables
        cursor.execute("DROP TABLE prediction_history")
        cursor.execute("ALTER TABLE prediction_history_new RENAME TO prediction_history")
        
        connection.commit()
        print("Migration successful: user_id is now nullable in prediction_history.")
    except Exception as e:
        print(f"Migration failed: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    migrate()
