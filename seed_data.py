import sqlite3
from werkzeug.security import generate_password_hash
import random
from datetime import datetime, timedelta

DATABASE_PATH = "student_app.db"

def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def populate_sample_data():
    with get_db_connection() as conn:
        # 1. Create Sample Users
        users = [
            ("Aarav Sharma", "aarav@example.com", "user"),
            ("Priya Patel", "priya@example.com", "user"),
            ("Vikram Singh", "vikram@example.com", "user"),
            ("Ananya Iyer", "ananya@example.com", "user"),
        ]
        
        user_ids = []
        for name, email, role in users:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (name, email, generate_password_hash("password123"), role)
                )
                user_ids.append(cursor.lastrowid)
            except sqlite3.IntegrityError:
                # User might already exist
                row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                if row:
                    user_ids.append(row['id'])

        # 2. Sample Subjects by Semester
        semester_subjects = {
            'SEM I': [
                'Mathematical foundation for Computer Applications',
                'Data Structures and Algorithms',
                'Object Oriented Programming',
                'Research Methodology',
                'Elective I - Artificial Intelligence'
            ],
            'SEM II': [
                'Operating System and Network Fundamentals',
                'Database Management System',
                'Software Engineering and Project Management',
                'Java and Advance Java Programming',
                'Elective II - Machine Learning',
                'Elective II - Internet of Things'
            ],
            'SEM III': [
                'Software Engineering',
                'Web Technologies',
                'Data Warehousing and Data Mining',
                'Artificial Intelligence / Machine Learning',
                'Cloud Computing'
            ],
            'SEM IV': [
                'Big Data Analytics',
                'Cyber Security',
                'Cloud Computing',
                'Internet of Things (IoT)',
                'Major Project / Dissertation'
            ]
        }

        # 3. Performance Labels
        labels = ["Excellent", "Good", "Average", "Needs Improvement"]
        
        # 4. Generate Predictions
        student_names = ["Rahul", "Sneha", "Amit", "Kavita", "Rohan", "Suresh", "Meena", "Laks"]
        
        for _ in range(25):
            user_id = random.choice(user_ids)
            student_name = random.choice(student_names)
            semester = random.choice(list(semester_subjects.keys()))
            subject = random.choice(semester_subjects[semester])
            
            attendance = random.uniform(60, 98)
            mid_marks = random.uniform(40, 95)
            assignments = random.uniform(50, 100)
            study_hours = random.uniform(1, 8)
            
            label = random.choice(labels)
            text = f"{label} Performance - The student logic simulation prediction."
            
            # Create a random date within the last 30 days
            random_days = random.randint(0, 30)
            created_at = (datetime.now() - timedelta(days=random_days)).strftime("%Y-%m-%d %H:%M:%S")
            
            conn.execute(
                """
                INSERT INTO prediction_history 
                (user_id, student_name, attendance, mid_marks, assignments, study_hours, subject, semester, predicted_label, prediction_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, student_name, attendance, mid_marks, assignments, study_hours, subject, semester, label, text, created_at)
            )
        
        conn.commit()
    print("Sample data populated successfully.")

if __name__ == "__main__":
    populate_sample_data()
