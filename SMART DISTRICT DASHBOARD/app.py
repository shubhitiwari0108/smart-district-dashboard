from flask import Flask, render_template, request, redirect, session
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-secret"

DATABASE = "district.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            service TEXT NOT NULL,
            address TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending'
        );

        CREATE TABLE IF NOT EXISTS grievances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending'
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0
        );
    """)

    conn.commit()
    conn.close()


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user" not in session:
                return redirect("/login")

            if role and session.get("role") != role:
                return redirect("/")

            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.route("/")
def home():
    conn = get_db()
    announcements = conn.execute(
        "SELECT id, title, message FROM announcements ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("home.html", announcements=announcements)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        valid_users = {
            "citizen": {"password": "1234", "role": "citizen"},
            "admin": {"password": "1234", "role": "admin"}
        }

        user = valid_users.get(username)

        if user and user["password"] == password and user["role"] == role:
            session.clear()
            session["user"] = username
            session["role"] = role

            if role == "admin":
                return redirect("/admin")
            return redirect("/citizen")

        error = "Invalid username, password, or portal selection."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/citizen")
@login_required("citizen")
def citizen():
    username = session["user"]
    conn = get_db()

    applications = conn.execute(
        """SELECT * FROM applications
           WHERE username = ? ORDER BY id DESC""",
        (username,)
    ).fetchall()

    grievances = conn.execute(
        """SELECT * FROM grievances
           WHERE username = ? ORDER BY id DESC""",
        (username,)
    ).fetchall()

    notifications = conn.execute(
        """SELECT * FROM notifications
           WHERE username = ? ORDER BY id DESC""",
        (username,)
    ).fetchall()

    unread_notifications = conn.execute(
        """SELECT COUNT(*) FROM notifications
           WHERE username = ? AND is_read = 0""",
        (username,)
    ).fetchone()[0]

    announcements = conn.execute(
        "SELECT * FROM announcements ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "citizen.html",
        applications=applications,
        grievances=grievances,
        notifications=notifications,
        unread_notifications=unread_notifications,
        announcements=announcements
    )


@app.route("/apply", methods=["GET", "POST"])
@login_required("citizen")
def apply():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        service = request.form.get("service", "").strip()
        address = request.form.get("address", "").strip()
        description = request.form.get("description", "").strip()

        if not all([name, mobile, service, address, description]):
            return render_template(
                "apply.html", error="Please fill in all fields."
            )

        conn = get_db()
        cur = conn.execute(
            """INSERT INTO applications
               (username, name, mobile, service, address, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session["user"], name, mobile, service, address, description)
        )
        application_id = cur.lastrowid
        conn.commit()
        conn.close()

        return render_template(
            "apply.html",
            success=f"Application submitted successfully. Your ID is APP{application_id}."
        )

    return render_template("apply.html")


@app.route("/track", methods=["GET", "POST"])
@login_required("citizen")
def track():
    application = None
    error = None

    if request.method == "POST":
        raw_id = request.form.get("application_id", "").strip()
        raw_id = raw_id.upper().removeprefix("APP")

        if raw_id.isdigit():
            conn = get_db()
            application = conn.execute(
                """SELECT * FROM applications
                   WHERE id = ? AND username = ?""",
                (int(raw_id), session["user"])
            ).fetchone()
            conn.close()

        if application is None:
            error = "Application not found. Check the ID and try again."

    return render_template("track.html", application=application, error=error)


@app.route("/grievance", methods=["GET", "POST"])
@login_required("citizen")
def grievance():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()

        if not subject or not description:
            return render_template(
                "grievance.html", error="Please fill in all fields."
            )

        conn = get_db()
        cur = conn.execute(
            """INSERT INTO grievances (username, subject, description)
               VALUES (?, ?, ?)""",
            (session["user"], subject, description)
        )
        grievance_id = cur.lastrowid
        conn.commit()
        conn.close()

        return render_template(
            "grievance.html",
            success=f"Grievance submitted successfully. Your ID is GRV{grievance_id}."
        )

    return render_template("grievance.html")


@app.route("/track-grievance", methods=["GET", "POST"])
@login_required("citizen")
def track_grievance():
    grievance_item = None
    error = None

    if request.method == "POST":
        raw_id = request.form.get("grievance_id", "").strip()
        raw_id = raw_id.upper().removeprefix("GRV")

        if raw_id.isdigit():
            conn = get_db()
            grievance_item = conn.execute(
                """SELECT * FROM grievances
                   WHERE id = ? AND username = ?""",
                (int(raw_id), session["user"])
            ).fetchone()
            conn.close()

        if grievance_item is None:
            error = "Grievance not found. Check the ID and try again."

    return render_template(
        "track_grievance.html",
        grievance=grievance_item,
        error=error
    )


@app.route("/notifications/read/<int:notification_id>")
@login_required("citizen")
def mark_notification_read(notification_id):
    conn = get_db()
    conn.execute(
        """UPDATE notifications SET is_read = 1
           WHERE id = ? AND username = ?""",
        (notification_id, session["user"])
    )
    conn.commit()
    conn.close()
    return redirect("/citizen")


@app.route("/admin")
@login_required("admin")
def admin():
    conn = get_db()

    applications = conn.execute(
        "SELECT * FROM applications ORDER BY id DESC"
    ).fetchall()

    grievances = conn.execute(
        "SELECT * FROM grievances ORDER BY id DESC"
    ).fetchall()

    announcements = conn.execute(
        "SELECT * FROM announcements ORDER BY id DESC"
    ).fetchall()

    stats = {
        "total_applications": conn.execute(
            "SELECT COUNT(*) FROM applications"
        ).fetchone()[0],
        "pending_applications": conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status='Pending'"
        ).fetchone()[0],
        "approved_applications": conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status='Approved'"
        ).fetchone()[0],
        "total_grievances": conn.execute(
            "SELECT COUNT(*) FROM grievances"
        ).fetchone()[0],
        "resolved_grievances": conn.execute(
            "SELECT COUNT(*) FROM grievances WHERE status='Resolved'"
        ).fetchone()[0]
    }

    conn.close()

    return render_template(
        "admin.html",
        applications=applications,
        grievances=grievances,
        announcements=announcements,
        stats=stats
    )


@app.route("/application/<int:app_id>/<status>")
@login_required("admin")
def update_application(app_id, status):
    if status not in ("Approved", "Rejected"):
        return "Invalid status", 400

    conn = get_db()
    application = conn.execute(
        "SELECT username, service FROM applications WHERE id = ?",
        (app_id,)
    ).fetchone()

    if application is None:
        conn.close()
        return "Application not found", 404

    conn.execute(
        "UPDATE applications SET status = ? WHERE id = ?",
        (status, app_id)
    )
    conn.execute(
        """INSERT INTO notifications (username, message)
           VALUES (?, ?)""",
        (
            application["username"],
            f"Your application APP{app_id} for {application['service']} has been {status}."
        )
    )
    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/grievance/<int:grievance_id>/resolve")
@login_required("admin")
def resolve_grievance(grievance_id):
    conn = get_db()

    grievance_item = conn.execute(
        "SELECT username, subject, status FROM grievances WHERE id = ?",
        (grievance_id,)
    ).fetchone()

    if grievance_item is None:
        conn.close()
        return "Grievance not found", 404

    if grievance_item["status"] != "Resolved":
        conn.execute(
            "UPDATE grievances SET status = 'Resolved' WHERE id = ?",
            (grievance_id,)
        )
        conn.execute(
            """INSERT INTO notifications (username, message)
               VALUES (?, ?)""",
            (
                grievance_item["username"],
                f"Your grievance GRV{grievance_id} ({grievance_item['subject']}) has been resolved."
            )
        )

    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/announcement", methods=["POST"])
@login_required("admin")
def add_announcement():
    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()

    if title and message:
        conn = get_db()
        conn.execute(
            "INSERT INTO announcements (title, message) VALUES (?, ?)",
            (title, message)
        )
        conn.commit()
        conn.close()

    return redirect("/admin")


@app.route("/announcement/<int:announcement_id>/delete", methods=["POST"])
@login_required("admin")
def delete_announcement(announcement_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM announcements WHERE id = ?",
        (announcement_id,)
    )
    conn.commit()
    conn.close()
    return redirect("/admin")


init_db()

if __name__ == "__main__":
    app.run(debug=True)