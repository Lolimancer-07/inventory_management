import os
import sys
import socket
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, g, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# PyInstaller compatibility
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    EXE_DIR  = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR  = BASE_DIR

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "banik-hardware-secret-2024")

# ---------------------------------------------------------------------------
# Database — PostgreSQL (cloud) or SQLite (local / EXE)
# ---------------------------------------------------------------------------
DB_PATH  = os.path.join(EXE_DIR, "inventory.db")
_db_url  = os.environ.get("DATABASE_URL", "").strip()

# Supabase / older hosts use postgres:// — SQLAlchemy needs postgresql://
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

IS_POSTGRES = bool(_db_url)
_engine = create_engine(
    _db_url if IS_POSTGRES else f"sqlite:///{DB_PATH}",
    pool_pre_ping=True,
)
ORDER_BY = "LOWER(material)" if IS_POSTGRES else "material COLLATE NOCASE"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = _engine.connect()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables and seed default users if not present. Safe to call multiple times."""
    id_col = "id SERIAL PRIMARY KEY" if IS_POSTGRES else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    with _engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                username      TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL CHECK (role IN ('admin', 'user'))
            )
        """))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS inventory (
                {id_col},
                material        TEXT NOT NULL,
                buying_price    REAL NOT NULL,
                wholesale_price REAL NOT NULL,
                retail_price    REAL NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """))
        row = conn.execute(text("SELECT username FROM users LIMIT 1")).fetchone()
        if row is None:
            conn.execute(
                text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, :r)"),
                [
                    {"u": "admin", "p": generate_password_hash("admin123"), "r": "admin"},
                    {"u": "user",  "p": generate_password_hash("user123"),  "r": "user"},
                ],
            )
        conn.commit()


# Run on startup (works for gunicorn, direct run, and PyInstaller EXE)
init_db()


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
# Routes — PWA static files
# ---------------------------------------------------------------------------
@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json",
                               mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js",
                               mimetype="application/javascript")


# ---------------------------------------------------------------------------
# Routes — app
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db  = get_db()
        row = db.execute(
            text("SELECT * FROM users WHERE username = :u"), {"u": username}
        ).mappings().fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session["username"] = row["username"]
            session["role"]     = row["role"]
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
    db    = get_db()
    items = db.execute(
        text(f"SELECT * FROM inventory ORDER BY {ORDER_BY}")
    ).mappings().fetchall()
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
        buying    = float(request.form.get("buying_price", 0))
        wholesale = float(request.form.get("wholesale_price", 0))
        retail    = float(request.form.get("retail_price", 0))
    except ValueError:
        flash("Prices must be numbers.", "error")
        return redirect(url_for("dashboard"))

    if not material:
        flash("Material name is required.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        text("""INSERT INTO inventory
                 (material, buying_price, wholesale_price, retail_price, updated_at)
                 VALUES (:m, :b, :w, :r, :u)"""),
        {"m": material, "b": buying, "w": wholesale, "r": retail,
         "u": datetime.now().strftime("%Y-%m-%d %H:%M")},
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
        buying    = float(request.form.get("buying_price", 0))
        wholesale = float(request.form.get("wholesale_price", 0))
        retail    = float(request.form.get("retail_price", 0))
    except ValueError:
        flash("Prices must be numbers.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        text("""UPDATE inventory
                SET material=:m, buying_price=:b, wholesale_price=:w,
                    retail_price=:r, updated_at=:u
                WHERE id=:id"""),
        {"m": material, "b": buying, "w": wholesale, "r": retail,
         "u": datetime.now().strftime("%Y-%m-%d %H:%M"), "id": item_id},
    )
    db.commit()
    flash(f"Updated '{material}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/delete/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def delete_item(item_id):
    db  = get_db()
    row = db.execute(
        text("SELECT material FROM inventory WHERE id = :id"), {"id": item_id}
    ).mappings().fetchone()
    db.execute(text("DELETE FROM inventory WHERE id = :id"), {"id": item_id})
    db.commit()
    if row:
        flash(f"Deleted '{row['material']}'.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Local IP helper
# ---------------------------------------------------------------------------
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

    ip = get_local_ip()
    print("=" * 60)
    print("  Banik Hardware — Inventory is running!")
    print(f"  This PC:        http://127.0.0.1:5000")
    print(f"  Other devices:  http://{ip}:5000")
    print("=" * 60)

    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
