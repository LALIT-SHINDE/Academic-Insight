import csv
import pickle
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = "student-performance-secret-key"

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
DATABASE_PATH = BASE_DIR / "student_app.db"
DATASET_PATH = BASE_DIR / "students.csv"


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_history (
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
            """
        )
        connection.commit()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS students_dataset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                name TEXT,
                attendance REAL NOT NULL,
                mid_marks REAL NOT NULL,
                assignments REAL NOT NULL,
                study_hours REAL NOT NULL,
                performance_label TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()

    # Migration: Add subject column if it doesn't exist
    try:
        with get_db_connection() as connection:
            connection.execute("ALTER TABLE prediction_history ADD COLUMN subject TEXT")
            connection.commit()
    except sqlite3.OperationalError:
        pass

    try:
        with get_db_connection() as connection:
            connection.execute("ALTER TABLE prediction_history ADD COLUMN semester TEXT")
            connection.commit()
    except sqlite3.OperationalError:
        pass


def ensure_default_admin() -> None:
    with get_db_connection() as connection:
        admin_user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            ("admin@school.com",),
        ).fetchone()

        if admin_user is None:
            connection.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (
                    "System Admin",
                    "admin@school.com",
                    generate_password_hash("admin123"),
                    "admin",
                ),
            )
            connection.commit()


def import_dataset() -> None:
    if not DATASET_PATH.exists():
        return

    with DATASET_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    if not rows:
        return

    with get_db_connection() as connection:
        connection.execute("DELETE FROM students_dataset")
        connection.executemany(
            """
            INSERT INTO students_dataset (
                student_id, name, attendance, mid_marks, assignments, study_hours, performance_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("student_id", "").strip(),
                    row.get("name", "").strip(),
                    float(row["attendance"]),
                    float(row["mid_marks"]),
                    float(row["assignments"]),
                    float(row["study_hours"]),
                    row["performance_label"].strip(),
                )
                for row in rows
            ],
        )
        connection.commit()


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def parse_float(field_name: str, minimum: float, maximum: float) -> float:
    raw_value = request.form.get(field_name, "").strip()
    if not raw_value:
        raise ValueError(f"{field_name.replace('_', ' ').title()} is required.")

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{field_name.replace('_', ' ').title()} must be a number.") from exc

    if not minimum <= value <= maximum:
        raise ValueError(
            f"{field_name.replace('_', ' ').title()} must be between {minimum} and {maximum}."
        )

    return value


def parse_student_name() -> str:
    student_name = request.form.get("student_name", "").strip()
    if not student_name:
        raise ValueError("Student Name is required.")
    return student_name


def generate_prediction(
    attendance: float, mid_marks: float, assignments: float, study_hours: float
) -> tuple[str, str, str]:
    normalized_hours = clamp((study_hours / 8) * 100, 0, 100)
    score = (
        attendance * 0.25
        + mid_marks * 0.35
        + assignments * 0.25
        + normalized_hours * 0.15
    )

    if score >= 85:
        level = "Excellent"
        insight = "The student is likely to perform very strongly."
    elif score >= 70:
        level = "Good"
        insight = "The student is likely to maintain solid academic performance."
    elif score >= 55:
        level = "Average"
        insight = "The student may perform moderately but has room to improve."
    else:
        level = "Needs Improvement"
        insight = "The student may need additional academic support and consistency."

    reasons = []
    actions = []
    if attendance < 75:
        reasons.append("lower attendance levels")
        actions.append("attending more lectures consistently")
    if study_hours < 4:
        reasons.append("limited daily study hours")
        actions.append("increasing your daily study schedule")
    if mid_marks < 60:
        reasons.append("room for improvement in mid-exam scores")
        actions.append("strengthening your grasp on core concepts")
    if assignments < 70:
        reasons.append("a gap in assignment submissions")
        actions.append("focusing on more diligent assignment completion")

    if not reasons:
        advice = f"Excellent work! You are maintaining an '{level}' standing. Continue with your current dedication to keep up this momentum."
    else:
        reason_str = ", ".join(reasons[:-1]) + (" and " if len(reasons) > 1 else "") + reasons[-1]
        action_str = ", ".join(actions[:-1]) + (" and " if len(actions) > 1 else "") + actions[-1]
        advice = f"Your performance is currently '{level}', primarily influenced by {reason_str}. To improve, we recommend {action_str}."

    return level, f"{level} Performance ({score:.2f}%) - {insight}", advice


def load_model():
    if not MODEL_PATH.exists():
        return None

    with MODEL_PATH.open("rb") as model_file:
        return pickle.load(model_file)


def predict_with_model(model, attendance: float, mid_marks: float, assignments: float, study_hours: float) -> tuple[str, str, str]:
    label_map = {
        0: "Needs Improvement",
        1: "Average",
        2: "Good",
        3: "Excellent",
    }
    insight_map = {
        0: "The student may need additional academic support and consistency.",
        1: "The student may perform moderately but has room to improve.",
        2: "The student is likely to maintain solid academic performance.",
        3: "The student is likely to perform very strongly.",
    }

    predicted_label = model.predict([[attendance, mid_marks, assignments, study_hours]])[0]
    level = label_map[predicted_label]
    insight = insight_map[predicted_label]

    reasons = []
    actions = []
    if attendance < 75:
        reasons.append("lower attendance levels")
        actions.append("attending more lectures consistently")
    if study_hours < 4:
        reasons.append("limited daily study hours")
        actions.append("increasing your daily study schedule")
    if mid_marks < 60:
        reasons.append("room for improvement in mid-exam scores")
        actions.append("strengthening your grasp on core concepts")
    if assignments < 70:
        reasons.append("a gap in assignment submissions")
        actions.append("focusing on more diligent assignment completion")

    if not reasons:
        advice = f"Excellent work! You are maintaining an '{level}' standing. Continue with your current dedication to keep up this momentum."
    else:
        reason_str = ", ".join(reasons[:-1]) + (" and " if len(reasons) > 1 else "") + reasons[-1]
        action_str = ", ".join(actions[:-1]) + (" and " if len(actions) > 1 else "") + actions[-1]
        advice = f"Your performance is currently '{level}', primarily influenced by {reason_str}. To improve, we recommend {action_str}."

    return level, f"{level} Performance - {insight}", advice


def get_logged_in_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT id, name, email, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return user


def is_admin_logged_in() -> bool:
    return session.get("user_role") == "admin" and session.get("user_id") is not None


def save_prediction(
    user_id: int | None,
    student_name: str,
    attendance: float,
    mid_marks: float,
    assignments: float,
    study_hours: float,
    subject: str,
    semester: str,
    predicted_label: str,
    prediction_text: str,
) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO prediction_history (
                user_id, student_name, attendance, mid_marks, assignments, study_hours,
                subject, semester, predicted_label, prediction_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                student_name,
                attendance,
                mid_marks,
                assignments,
                study_hours,
                subject,
                semester,
                predicted_label,
                prediction_text,
            ),
        )
        connection.commit()


def get_prediction_history(user_id: int, limit: int = 50, all_records: bool = False) -> list[sqlite3.Row]:
    with get_db_connection() as connection:
        if all_records:
            rows = connection.execute(
                """
                SELECT p.id, p.student_name, p.attendance, p.mid_marks, p.assignments, p.study_hours,
                       p.subject, p.predicted_label, p.prediction_text, p.created_at, u.name AS user_name
                FROM prediction_history p
                LEFT JOIN users u ON u.id = p.user_id
                ORDER BY p.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT p.id, p.student_name, p.attendance, p.mid_marks, p.assignments, p.study_hours,
                       p.subject, p.predicted_label, p.prediction_text, p.created_at, u.name AS user_name
                FROM prediction_history p
                LEFT JOIN users u ON u.id = p.user_id
                WHERE p.user_id = ?
                ORDER BY p.created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
    return rows


def get_all_predictions(limit: int = 0, offset: int = 0, search: str = "", subject: str = "", serial: str = "", result: str = "", semester: str = "", date_from: str = "", date_to: str = "") -> list[sqlite3.Row]:
    with get_db_connection() as connection:
        query = """
            SELECT
                prediction_history.id,
                prediction_history.student_name,
                prediction_history.attendance,
                prediction_history.mid_marks,
                prediction_history.assignments,
                prediction_history.study_hours,
                prediction_history.subject,
                prediction_history.semester,
                prediction_history.predicted_label,
                prediction_history.created_at,
                users.name AS user_name,
                users.email AS user_email
            FROM prediction_history
            LEFT JOIN users ON users.id = prediction_history.user_id
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (prediction_history.student_name LIKE ? OR users.name LIKE ? OR users.email LIKE ?)"
            params.extend([f"%{search}%"] * 3)

        if subject:
            query += " AND prediction_history.subject LIKE ?"
            params.append(f"%{subject}%")

        if serial:
            try:
                serial_id = int(serial.upper().replace("PR", ""))
                query += " AND prediction_history.id = ?"
                params.append(serial_id)
            except ValueError:
                query += " AND prediction_history.id = -1"

        if result:
            query += " AND prediction_history.predicted_label = ?"
            params.append(result)

        if semester:
            query += " AND prediction_history.semester = ?"
            params.append(semester)

        if date_from:
            query += " AND date(prediction_history.created_at) >= date(?)"
            params.append(date_from)

        if date_to:
            query += " AND date(prediction_history.created_at) <= date(?)"
            params.append(date_to)

        query += " ORDER BY prediction_history.id DESC"

        if limit > 0:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        rows = connection.execute(query, params).fetchall()
    return rows


def get_prediction_count(search: str = "", subject: str = "", serial: str = "", result: str = "", semester: str = "", date_from: str = "", date_to: str = "") -> int:
    with get_db_connection() as connection:
        query = """
            SELECT COUNT(*) as count
            FROM prediction_history
            LEFT JOIN users ON users.id = prediction_history.user_id
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (prediction_history.student_name LIKE ? OR users.name LIKE ? OR users.email LIKE ?)"
            params.extend([f"%{search}%"] * 3)

        if subject:
            query += " AND prediction_history.subject LIKE ?"
            params.append(f"%{subject}%")

        if serial:
            try:
                serial_id = int(serial.upper().replace("PR", ""))
                query += " AND prediction_history.id = ?"
                params.append(serial_id)
            except ValueError:
                query += " AND prediction_history.id = -1"

        if result:
            query += " AND prediction_history.predicted_label = ?"
            params.append(result)

        if semester:
            query += " AND prediction_history.semester = ?"
            params.append(semester)

        if date_from:
            query += " AND date(prediction_history.created_at) >= date(?)"
            params.append(date_from)

        if date_to:
            query += " AND date(prediction_history.created_at) <= date(?)"
            params.append(date_to)

        row = connection.execute(query, params).fetchone()
    return int(row["count"] if row else 0)


def get_all_users() -> list[sqlite3.Row]:
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return rows


def get_model_status():
    model_exists = MODEL_PATH.exists()
    dataset_count = get_dataset_count()
    return {
        "model_exists": model_exists,
        "model_path": str(MODEL_PATH),
        "dataset_count": dataset_count,
        "train_script": "train_model.py available"
    }


def get_dataset_count() -> int:
    with get_db_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM students_dataset").fetchone()
    return int(row["count"]) if row else 0


def get_user_count() -> int:
    with get_db_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    return int(row["count"]) if row else 0


@app.route("/")
def home():
    user = get_logged_in_user()
    return render_template(
        "index.html",
        current_user=user,
        dataset_count=get_dataset_count(),
        user_count=get_user_count(),
    )


@app.route("/auth", methods=["POST"])
def auth():
    data = request.get_json(silent=True) or {}
    role = data.get("role", "user").strip().lower()
    mode = data.get("mode", "login").strip().lower()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip() or "Student User"

    if role not in {"user", "admin"}:
        return jsonify({"success": False, "message": "Invalid role selected."}), 400
    if mode not in {"login", "signup"}:
        return jsonify({"success": False, "message": "Invalid auth mode."}), 400
    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    with get_db_connection() as connection:
        existing_user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if mode == "signup":
            if role != "user":
                return jsonify({"success": False, "message": "Only student signup is available here."}), 400
            if not name:
                return jsonify({"success": False, "message": "Full name is required for signup."}), 400
            if existing_user:
                return jsonify({"success": False, "message": "An account with this email already exists."}), 409

            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), role),
            )
            connection.commit()
            user_id = cursor.lastrowid
        else:
            if not existing_user:
                return jsonify({"success": False, "message": "No account found for this email."}), 404
            if existing_user["role"] != role:
                return jsonify({"success": False, "message": "This account does not match the selected role."}), 403
            if not check_password_hash(existing_user["password_hash"], password):
                return jsonify({"success": False, "message": "Incorrect password."}), 401
            user_id = existing_user["id"]
            name = existing_user["name"]

    session["user_id"] = user_id
    session["user_role"] = role
    session["user_name"] = name
    session["user_email"] = email

    redirect_url = url_for("predict") if role == "user" else url_for("admin_dashboard")
    success_message = "Account created successfully." if mode == "signup" else "Login successful."
    return jsonify({"success": True, "message": success_message, "redirect_url": redirect_url})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/predict", methods=["GET", "POST"])
def predict():
    user = get_logged_in_user()
    form_values = {
        "student_name": user["name"] if user else "",
        "attendance": "",
        "mid_marks": "",
        "assignments": "",
        "study_hours": "",
        "subject": "",
    }

    if request.method == "GET":
        return render_template("predict.html", current_user=user)

    try:
        student_name = parse_student_name()
        attendance = parse_float("attendance", 0, 100)
        mid_marks = parse_float("mid_marks", 0, 100)
        assignments = parse_float("assignments", 0, 100)
        study_hours = parse_float("study_hours", 0, 24)
        subject = request.form.get("subject", "General").strip()
        semester = request.form.get("semester", "N/A").strip()

        form_values = {
            "student_name": student_name,
            "attendance": request.form.get("attendance", ""),
            "mid_marks": request.form.get("mid_marks", ""),
            "assignments": request.form.get("assignments", ""),
            "study_hours": request.form.get("study_hours", ""),
            "subject": subject,
            "semester": semester,
        }

        model = load_model()
        if model is not None:
            predicted_label, prediction_text, advice = predict_with_model(
                model=model,
                attendance=attendance,
                mid_marks=mid_marks,
                assignments=assignments,
                study_hours=study_hours,
            )
        else:
            predicted_label, prediction_text, advice = generate_prediction(
                attendance=attendance,
                mid_marks=mid_marks,
                assignments=assignments,
                study_hours=study_hours,
            )

        save_prediction(
            user_id=user["id"] if user else None,
            student_name=student_name,
            attendance=attendance,
            mid_marks=mid_marks,
            assignments=assignments,
            study_hours=study_hours,
            subject=subject,
            semester=semester,
            predicted_label=predicted_label,
            prediction_text=prediction_text,
        )

        return render_template(
            "result.html",
            prediction_text=prediction_text,
            predicted_label=predicted_label,
            advice=advice,
            current_user=user,
            student_name=student_name,
            attendance=attendance,
            mid_marks=mid_marks,
            assignments=assignments,
            study_hours=study_hours,
            subject=subject,
            semester=semester,
        )
    except ValueError as error:
        return render_template(
            "result.html",
            prediction_text=f"Input error: {error}",
            predicted_label="Error",
            advice="Please check your inputs and try again.",
            current_user=user,
            student_name=form_values["student_name"],
            attendance=form_values["attendance"],
            mid_marks=form_values["mid_marks"],
            assignments=form_values["assignments"],
            study_hours=form_values["study_hours"],
            subject=form_values["subject"],
        )


@app.route("/progress")
def progress():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("home", show_user_login="true"))

    is_admin = user["role"] == "admin"
    history = get_prediction_history(user["id"], all_records=is_admin)
    history_dicts = [dict(row) for row in history]
    return render_template("progress.html", current_user=user, history=history_dicts)


@app.route("/admin")
def admin_dashboard():
    if not is_admin_logged_in():
        return redirect(url_for("home", show_admin_login="true"))

    return render_template("admin.html")


@app.route("/admin/data")
def admin_data():
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin access required."}), 403

    search = request.args.get("search", "").strip()
    subject = request.args.get("subject", "").strip()
    serial = request.args.get("serial", "").strip()
    result = request.args.get("result", "").strip()
    semester = request.args.get("semester", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    offset = (page - 1) * limit

    predictions = get_all_predictions(limit=limit, offset=offset, search=search, subject=subject, serial=serial, result=result, semester=semester, date_from=date_from, date_to=date_to)
    total_count = get_prediction_count(search=search, subject=subject, serial=serial, result=result, semester=semester, date_from=date_from, date_to=date_to)

    payload = [
        {
            "id": row["id"],
            "user_name": row["user_name"],
            "user_email": row["user_email"],
            "student_name": row["student_name"],
            "subject": row["subject"],
            "semester": row["semester"],
            "attendance": row["attendance"],
            "mid_marks": row["mid_marks"],
            "assignments": row["assignments"],
            "study_hours": row["study_hours"],
            "predicted_label": row["predicted_label"],
            "created_at": row["created_at"],
        }
        for row in predictions
    ]

    return jsonify(
        {
            "success": True,
            "admin_email": session.get("user_email", ""),
            "total_predictions": total_count,
            "records": payload,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1
        }
    )


@app.route("/admin/users")
def admin_users():
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin access required."}), 403

    users = get_all_users()
    payload = [
        {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "role": row["role"],
            "created_at": row["created_at"]
        }
        for row in users
    ]
    return jsonify({"success": True, "users": payload})


@app.route("/admin/export")
def admin_export():
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin access required."}), 403

    search = request.args.get("search", "").strip()
    subject = request.args.get("subject", "").strip()
    serial = request.args.get("serial", "").strip()
    result = request.args.get("result", "").strip()
    semester = request.args.get("semester", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    predictions = get_all_predictions(search=search, subject=subject, serial=serial, result=result, semester=semester, date_from=date_from, date_to=date_to)
    import io
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["ID", "User", "Email", "Student", "Subject", "Attendance", "Mid", "Assignments", "Hours", "Result", "Date"])
    for row in predictions:
        writer.writerow([
            row["id"],
            row["user_name"],
            row["user_email"],
            row["student_name"],
            row["subject"],
            row["attendance"],
            row["mid_marks"],
            row["assignments"],
            row["study_hours"],
            row["predicted_label"],
            row["created_at"]
        ])

    output.seek(0)
    return app.response_class(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=predictions.csv"}
    )


@app.route("/admin/model_status")
def admin_model_status():
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin access required."}), 403

    return jsonify({"success": True, **get_model_status()})


@app.route("/admin/delete_prediction/<int:prediction_id>", methods=["POST"])
def admin_delete_prediction(prediction_id):
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin access required."}), 403

    with get_db_connection() as connection:
        connection.execute("DELETE FROM prediction_history WHERE id = ?", (prediction_id,))
        connection.commit()

    return jsonify({"success": True, "message": "Prediction deleted successfully."})


@app.route("/admin/update_prediction/<int:prediction_id>", methods=["POST"])
def admin_update_prediction(prediction_id):
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin access required."}), 403

    data = request.get_json()
    try:
        student_name = data.get("student_name")
        attendance = float(data.get("attendance"))
        mid_marks = float(data.get("mid_marks"))
        assignments = float(data.get("assignments"))
        study_hours = float(data.get("study_hours"))
        subject = data.get("subject")
        semester = data.get("semester")

        # Recalculate performance based on updated metrics
        from app import generate_prediction, load_model, predict_with_model
        
        model = load_model()
        if model:
            predicted_label, prediction_text, advice = predict_with_model(model, attendance, mid_marks, assignments, study_hours)
        else:
            predicted_label, prediction_text, advice = generate_prediction(attendance, mid_marks, assignments, study_hours)

        with get_db_connection() as connection:
            connection.execute(
                """
                UPDATE prediction_history 
                SET student_name = ?, attendance = ?, mid_marks = ?, assignments = ?, study_hours = ?, subject = ?, semester = ?, predicted_label = ?, prediction_text = ?
                WHERE id = ?
                """,
                (student_name, attendance, mid_marks, assignments, study_hours, subject, semester, predicted_label, prediction_text, prediction_id)
            )
            connection.commit()
        
        return jsonify({"success": True, "message": "Prediction updated and performance recalculated."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


init_db()
ensure_default_admin()
import_dataset()


if __name__ == "__main__":
    app.run(debug=True)
