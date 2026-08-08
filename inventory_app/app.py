import os
import sys
import sqlite3
import socket
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# PyInstaller compatibility
# When frozen with PyInstaller, bundled files live in sys._MEIPASS.
# The database must stay next to the EXE so data persists between runs.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle
    BASE_DIR = sys._MEIPASS          # templates & static are here
    EXE_DIR  = os.path.dirname(sys.executable)  # DB lives next to the .exe
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR  = BASE_DIR

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = "change-this-secret-key-later"  # change before real deployment
DB_PATH = os.path.join(EXE_DIR, "inventory.db")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'user'))
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material TEXT NOT NULL,
            buying_price REAL NOT NULL,
            wholesale_price REAL NOT NULL,
            retail_price REAL NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    # Seed default accounts if none exist yet
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin"),
        )
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("user", generate_password_hash("user123"), "user"),
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("You don't have permission to do that.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json",
                               mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js",
                               mimetype="application/javascript")


@app.route("/connect")
def connect_page():
    """Shown on the host PC — displays QR code so other devices can connect."""
    ip = get_local_ip()
    url = f"http://{ip}:5000"
    return render_template("connect.html", url=url, ip=ip)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        row = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session["username"] = row["username"]
            session["role"] = row["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    db = get_db()
    items = db.execute("SELECT * FROM inventory ORDER BY material COLLATE NOCASE").fetchall()
    return render_template(
        "index.html",
        items=items,
        role=session.get("role"),
        username=session.get("username"),
    )


@app.route("/add", methods=["POST"])
@login_required
@admin_required
def add_item():
    material = request.form.get("material", "").strip()
    try:
        buying = float(request.form.get("buying_price", 0))
        wholesale = float(request.form.get("wholesale_price", 0))
        retail = float(request.form.get("retail_price", 0))
    except ValueError:
        flash("Prices must be numbers.", "error")
        return redirect(url_for("dashboard"))

    if not material:
        flash("Material name is required.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        """INSERT INTO inventory (material, buying_price, wholesale_price, retail_price, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (material, buying, wholesale, retail, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    db.commit()
    flash(f"Added '{material}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/edit/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def edit_item(item_id):
    material = request.form.get("material", "").strip()
    try:
        buying = float(request.form.get("buying_price", 0))
        wholesale = float(request.form.get("wholesale_price", 0))
        retail = float(request.form.get("retail_price", 0))
    except ValueError:
        flash("Prices must be numbers.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        """UPDATE inventory
           SET material = ?, buying_price = ?, wholesale_price = ?, retail_price = ?, updated_at = ?
           WHERE id = ?""",
        (material, buying, wholesale, retail, datetime.now().strftime("%Y-%m-%d %H:%M"), item_id),
    )
    db.commit()
    flash(f"Updated '{material}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/delete/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def delete_item(item_id):
    db = get_db()
    row = db.execute("SELECT material FROM inventory WHERE id = ?", (item_id,)).fetchone()
    db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    db.commit()
    if row:
        flash(f"Deleted '{row['material']}'.", "success")
    return redirect(url_for("dashboard"))


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    import threading
    import webbrowser

    init_db()
    ip = get_local_ip()

    print("=" * 60)
    print("  Stockroom is running!")
    print(f"  This PC:        http://127.0.0.1:5000")
    print(f"  Other devices:  http://{ip}:5000")
    print(f"  Connect page:   http://127.0.0.1:5000/connect")
    print("=" * 60)

    # Auto-open the connect page — shows QR code for other devices to scan
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000/connect")).start()

    app.run(host="0.0.0.0", port=5000, debug=False)


