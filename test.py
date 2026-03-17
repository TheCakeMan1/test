import sqlite3
import subprocess
import time
from pathlib import Path
from functools import wraps
from html import escape

from flask import (
    Flask,
    jsonify,
    request,
    session,
    redirect,
    url_for,
    render_template_string,
    flash,
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "ctf-demo-secret-change-me"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ctf_lab.db"
FILES_DIR = BASE_DIR / "public_files"
UPLOADS_DIR = BASE_DIR / "uploads"
SAFE_UPLOADS_DIR = BASE_DIR / "safe_uploads"

for p in [FILES_DIR, UPLOADS_DIR, SAFE_UPLOADS_DIR]:
    p.mkdir(exist_ok=True)

FLAGS = {
    "sqli": "",
    "xss": "",
    "traversal": "",
    "cmd": "",
    "idor": "",
    "bruteforce": "",
    "upload": "",
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Необходимо войти в систему.")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS users")
    cur.execute("DROP TABLE IF EXISTS comments")
    cur.execute("DROP TABLE IF EXISTS notes")
    cur.execute("DROP TABLE IF EXISTS login_attempts")

    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            mission TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            text TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE login_attempts (
            username TEXT PRIMARY KEY,
            tries INTEGER NOT NULL,
            last_try REAL NOT NULL
        )
    """)

    users = [
        ("admin", "admin123", "Oracle Admin", "admin@fortress.local", "admin", "Хранитель ядра"),
        ("neo", "qwerty", "Neo Student", "neo@fortress.local", "user", "Разведчик периметра"),
        ("trinity", "123456", "Trinity Student", "trinity@fortress.local", "user", "Оператор доступа"),
    ]
    cur.executemany(
        "INSERT INTO users (username, password, full_name, email, role, mission) VALUES (?, ?, ?, ?, ?, ?)",
        users,
    )

    comments = [
        ("system", "Система комментариев переведена на новый движок."),
        ("support", "Если вы видите некорректное отображение, обновите страницу."),
    ]
    cur.executemany("INSERT INTO comments (author, text) VALUES (?, ?)", comments)

    notes = [
        (1, "Vault note", f"Секретное содержимое хранилища. Флаг: {FLAGS['idor']}"),
        (2, "Neo private note", "Neo: проверить журналы доступа после смены."),
        (3, "Trinity private note", "Trinity: обновить политику паролей."),
    ]
    cur.executemany("INSERT INTO notes (owner_id, title, body) VALUES (?, ?, ?)", notes)

    conn.commit()
    conn.close()

    (FILES_DIR / "readme.txt").write_text(
        "Open documents directory.\nAvailable resources are stored here.\n",
        encoding="utf-8"
    )
    (FILES_DIR / "map.txt").write_text(
        "Sector A -> Web\nSector B -> Storage\nSector C -> Auth\n",
        encoding="utf-8"
    )
    (BASE_DIR / "secret_archive.txt").write_text(
        f"Архив вне public_files. Флаг: {FLAGS['traversal']}\n",
        encoding="utf-8"
    )
    (BASE_DIR / "cmd_flag.txt").write_text(
        f"Командный шлюз раскрыт. Флаг: {FLAGS['cmd']}\n",
        encoding="utf-8"
    )


def ensure_initialized():
    if not DB_PATH.exists():
        init_db()


def nav_block():
    return f"""
    <div style="margin-top:20px;font-size:14px;">
        <a href="{url_for('index')}">Главная</a> |
        <a href="{url_for('sqli_login')}">Auth</a> |
        <a href="{url_for('xss_comments')}">Comments</a> |
        <a href="{url_for('path_traversal')}">Docs</a> |
        <a href="{url_for('cmd_injection')}">Tools</a> |
        <a href="{url_for('idor_profile', user_id=1)}">Profile</a> |
        <a href="{url_for('bruteforce_login')}">Access</a> |
        <a href="{url_for('upload_lab')}">Upload</a> |
        <a href="{url_for('logout')}">Logout</a> |
        <a href="{url_for('reset_lab')}">Reset</a>
    </div>
    """


@app.route("/")
def index():
    user = current_user()
    username = escape(user["username"]) if user else "guest"

    html = f"""
    <!doctype html>
    <html lang="ru">
    <head>
        <meta charset="utf-8">
        <title>Links</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f3f4f6;
                color: #111827;
                margin: 0;
                padding: 40px;
            }}
            .box {{
                max-width: 900px;
                margin: 0 auto;
                background: white;
                border: 1px solid #d1d5db;
                border-radius: 12px;
                padding: 28px;
            }}
            h1 {{ margin-top: 0; }}
            ul {{ line-height: 1.9; }}
            a {{ color: #2563eb; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .muted {{ color: #6b7280; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>Service index</h1>
            <p class="muted">Текущий пользователь: <b>{username}</b></p>
            <p>Ниже собраны ссылки на разные внутренние и внешние сервисы компании.</p>
            <ul>
                <li><a href="{url_for('sqli_login')}">Corporate SSO Login</a></li>
                <li><a href="{url_for('xss_comments')}">Community guestbook</a></li>
                <li><a href="{url_for('path_traversal')}">Document browser</a></li>
                <li><a href="{url_for('cmd_injection')}">Network tools</a></li>
                <li><a href="{url_for('idor_profile', user_id=1)}">Employee profile</a></li>
                <li><a href="{url_for('bruteforce_login')}">Account access panel</a></li>
                <li><a href="{url_for('upload_lab')}">Document upload service</a></li>
            </ul>
            <p class="muted">Тестовые аккаунты: admin/admin123, neo/qwerty, trinity/123456</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/reset")
def reset_lab():
    init_db()
    session.clear()
    flash("Стенд сброшен.")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

from flask import jsonify

@app.route("/sqli_api", methods=["GET", "POST"])
def sqli_api():
    result = ""

    if request.method == "POST":
        if request.is_json:
            data = request.get_json(silent=True) or {}
            username = data.get("username", "")
            password = data.get("password", "")
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")

        query = f"SELECT id, username, email, role FROM users WHERE username = '{username}' AND password = '{password}'"

        conn = get_conn()
        try:
            rows = conn.execute(query).fetchall()
        except Exception as e:
            conn.close()

            if request.is_json:
                return jsonify({
                    "ok": False,
                    "error": str(e)
                }), 400

            result = f"<div class='error'>{escape(str(e))}</div>"
            rows = []

        else:
            conn.close()

        users = [
            {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role": row["role"],
            }
            for row in rows
        ]

        flag = FLAGS["sqli"] if users else None

        if request.is_json:
            return jsonify({
                "ok": True,
                "count": len(users),
                "users": users,
                "flag": flag
            })

        if users:
            result = "<div class='ok'>Records found</div>"
            result += f"<div class='flag'>{flag}</div>"
            result += "<pre>" + escape(str(users)) + "</pre>"
        else:
            result = "<div class='error'>No records found</div>"

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Corporate Login</title>
        <style>
            body {{
                margin: 0;
                font-family: Tahoma, Arial, sans-serif;
                background: linear-gradient(#e8eef7, #d6deea);
            }}
            .wrap {{
                width: 420px;
                margin: 70px auto;
                background: #fff;
                border: 1px solid #b9c7d8;
                box-shadow: 0 2px 8px rgba(0,0,0,.12);
            }}
            .head {{
                background: #2d5d8b;
                color: white;
                padding: 16px 20px;
                font-size: 22px;
            }}
            .content {{
                padding: 22px;
            }}
            label {{
                display: block;
                margin-bottom: 6px;
                color: #374151;
                font-size: 14px;
            }}
            input {{
                width: 100%;
                padding: 9px;
                margin-bottom: 14px;
                border: 1px solid #aebccc;
            }}
            button {{
                background: #2d5d8b;
                color: white;
                border: none;
                padding: 10px 14px;
                cursor: pointer;
            }}
            .error {{
                margin-top: 12px;
                color: #b91c1c;
            }}
            .ok {{
                margin-top: 12px;
                color: #166534;
            }}
            .flag {{
                margin-top: 12px;
                padding: 10px;
                background: #ecfdf5;
                border: 1px solid #16a34a;
                color: #166534;
            }}
            .links {{
                margin-top: 18px;
                font-size: 12px;
                color: #6b7280;
            }}
            a {{
                color: #2d5d8b;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="head">Company Secure Login</div>
            <div class="content">
                <form method="post">
                    <label>User name</label>
                    <input name="username">
                    <label>Password</label>
                    <input name="password" type="password">
                    <button type="submit">Sign in</button>
                </form>
                {result}
                <div class="links">
                    <a href="#">Forgot password?</a> · <a href="#">Help desk</a>
                </div>
                {nav_block()}
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/sqli", methods=["GET", "POST"])
def sqli_login():
    result = ""

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"

        conn = get_conn()
        try:
            user = conn.execute(query).fetchone()
        except Exception as e:
            user = None
            result = f"<div class='error'>{escape(str(e))}</div>"
        conn.close()

        if user:
            session["user_id"] = user["id"]
            result += f"<div class='ok'>Welcome back, {escape(user['full_name'])}</div>"
            result += f"<div class='flag'>{FLAGS['sqli']}</div>"
        else:
            result += "<div class='error'>Invalid username or password</div>"

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Corporate Login</title>
        <style>
            body {{
                margin: 0;
                font-family: Tahoma, Arial, sans-serif;
                background: linear-gradient(#e8eef7, #d6deea);
            }}
            .wrap {{
                width: 420px;
                margin: 70px auto;
                background: #fff;
                border: 1px solid #b9c7d8;
                box-shadow: 0 2px 8px rgba(0,0,0,.12);
            }}
            .head {{
                background: #2d5d8b;
                color: white;
                padding: 16px 20px;
                font-size: 22px;
            }}
            .content {{
                padding: 22px;
            }}
            label {{
                display: block;
                margin-bottom: 6px;
                color: #374151;
                font-size: 14px;
            }}
            input {{
                width: 100%;
                padding: 9px;
                margin-bottom: 14px;
                border: 1px solid #aebccc;
            }}
            button {{
                background: #2d5d8b;
                color: white;
                border: none;
                padding: 10px 14px;
                cursor: pointer;
            }}
            .error {{
                margin-top: 12px;
                color: #b91c1c;
            }}
            .ok {{
                margin-top: 12px;
                color: #166534;
            }}
            .flag {{
                margin-top: 12px;
                padding: 10px;
                background: #ecfdf5;
                border: 1px solid #16a34a;
                color: #166534;
            }}
            .links {{
                margin-top: 18px;
                font-size: 12px;
                color: #6b7280;
            }}
            a {{
                color: #2d5d8b;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="head">Company Secure Login</div>
            <div class="content">
                <form method="post">
                    <label>User name</label>
                    <input name="username">
                    <label>Password</label>
                    <input name="password" type="password">
                    <button type="submit">Sign in</button>
                </form>
                {result}
                <div class="links">
                    <a href="#">Forgot password?</a> · <a href="#">Help desk</a>
                </div>
                {nav_block()}
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/xss", methods=["GET", "POST"])
def xss_comments():
    conn = get_conn()
    if request.method == "POST":
        author = request.form.get("author", "anonymous")
        text = request.form.get("text", "")
        conn.execute("INSERT INTO comments (author, text) VALUES (?, ?)", (author, text))
        conn.commit()
        return redirect(url_for("xss_comments"))

    comments = conn.execute("SELECT * FROM comments ORDER BY id DESC").fetchall()
    conn.close()

    raw_comments = "".join(
        f"<div class='comment'><div class='meta'>{row['author']}</div><div class='text'>{row['text']}</div></div>"
        for row in comments
    )

    flag = ""
    if any("<script" in row["text"].lower() or "onerror=" in row["text"].lower() for row in comments):
        flag = f"<div class='flag'>{FLAGS['xss']}</div>"

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Guestbook</title>
        <style>
            body {{
                margin: 0;
                font-family: Georgia, serif;
                background: #fdfaf4;
                color: #2d2a26;
            }}
            .page {{
                width: 900px;
                margin: 30px auto;
            }}
            .title {{
                font-size: 38px;
                margin-bottom: 8px;
            }}
            .sub {{
                color: #7c6f64;
                margin-bottom: 28px;
            }}
            .box {{
                background: #fffefb;
                border: 1px solid #d8cfc2;
                padding: 18px;
                margin-bottom: 24px;
            }}
            input, textarea {{
                width: 100%;
                padding: 10px;
                border: 1px solid #cbbfae;
                margin-bottom: 12px;
                background: #fffdfa;
                font-family: Georgia, serif;
            }}
            button {{
                background: #8b5e3c;
                color: white;
                border: none;
                padding: 10px 16px;
                cursor: pointer;
            }}
            .comment {{
                padding: 14px 0;
                border-bottom: 1px solid #e8dfd2;
            }}
            .meta {{
                font-weight: bold;
                margin-bottom: 6px;
            }}
            .text {{
                line-height: 1.6;
            }}
            .flag {{
                margin-top: 14px;
                padding: 10px;
                background: #ecfdf5;
                border: 1px solid #16a34a;
                color: #166534;
            }}
            a {{ color: #8b5e3c; }}
        </style>
    </head>
    <body>
        <div class="page">
            <div class="title">Community Guestbook</div>
            <div class="sub">Оставьте сообщение или отзыв для других посетителей.</div>

            <div class="box">
                <form method="post">
                    <input name="author" placeholder="Ваше имя">
                    <textarea name="text" rows="5" placeholder="Ваш комментарий"></textarea>
                    <button type="submit">Publish</button>
                </form>
                {flag}
            </div>

            <div class="box">
                {raw_comments}
            </div>

            {nav_block()}
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/traversal")
def path_traversal():
    name = request.args.get("name", "readme.txt")

    try:
        vuln_path = BASE_DIR / "public_files" / name
        vuln_result = vuln_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        vuln_result = f"Error: {e}"

    flag = ""
    if FLAGS["traversal"] in vuln_result:
        flag = f"<div class='flag'>{FLAGS['traversal']}</div>"

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Docs Portal</title>
        <style>
            body {{
                margin: 0;
                font-family: "Segoe UI", sans-serif;
                background: #eef2f7;
                color: #1f2937;
            }}
            .top {{
                background: white;
                border-bottom: 1px solid #d1d5db;
                padding: 16px 24px;
                font-size: 22px;
                font-weight: 600;
            }}
            .wrap {{
                max-width: 1100px;
                margin: 24px auto;
                display: grid;
                grid-template-columns: 280px 1fr;
                gap: 20px;
            }}
            .side, .main {{
                background: white;
                border: 1px solid #dbe2ea;
                border-radius: 8px;
                padding: 18px;
            }}
            input {{
                width: 100%;
                padding: 10px;
                border: 1px solid #cbd5e1;
                margin-bottom: 10px;
            }}
            button {{
                background: #2563eb;
                color: white;
                border: none;
                padding: 10px 14px;
                border-radius: 6px;
            }}
            pre {{
                background: #0f172a;
                color: #e2e8f0;
                padding: 16px;
                border-radius: 8px;
                overflow-x: auto;
                min-height: 320px;
            }}
            .flag {{
                margin-top: 14px;
                padding: 10px;
                background: #ecfdf5;
                border: 1px solid #16a34a;
                color: #166534;
            }}
            a {{ color: #2563eb; }}
        </style>
    </head>
    <body>
        <div class="top">Document Repository</div>
        <div class="wrap">
            <div class="side">
                <h3>Open file</h3>
                <form method="get">
                    <input name="name" value="{escape(name)}">
                    <button type="submit">View</button>
                </form>
                <p>Recent files:</p>
                <ul>
                    <li>readme.txt</li>
                    <li>map.txt</li>
                </ul>
                {nav_block()}
            </div>
            <div class="main">
                <h3>Preview</h3>
                <pre>{escape(vuln_result)}</pre>
                {flag}
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/cmd", methods=["GET", "POST"])
def cmd_injection():
    target = "127.0.0.1"
    output = ""

    if request.method == "POST":
        target = request.form.get("target", "127.0.0.1")
        shell_cmd = f"echo PING {target}"
        try:
            output = subprocess.check_output(shell_cmd, shell=True, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            output = e.output

    flag = ""
    if FLAGS["cmd"] in output:
        flag = f"<div class='flag'>{FLAGS['cmd']}</div>"

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Ops Tools</title>
        <style>
            body {{
                margin: 0;
                font-family: Consolas, monospace;
                background: #111827;
                color: #d1fae5;
            }}
            .bar {{
                background: #0b1220;
                padding: 14px 20px;
                border-bottom: 1px solid #1f2937;
            }}
            .wrap {{
                max-width: 1000px;
                margin: 24px auto;
                background: #0f172a;
                border: 1px solid #1f2937;
                padding: 20px;
            }}
            input {{
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                background: #020617;
                color: #d1fae5;
                border: 1px solid #374151;
            }}
            button {{
                background: #059669;
                color: white;
                border: none;
                padding: 10px 14px;
                cursor: pointer;
            }}
            pre {{
                background: black;
                color: #86efac;
                padding: 16px;
                min-height: 220px;
                overflow-x: auto;
            }}
            .flag {{
                margin-top: 14px;
                padding: 10px;
                background: #052e16;
                border: 1px solid #166534;
                color: #86efac;
            }}
            a {{ color: #93c5fd; }}
        </style>
    </head>
    <body>
        <div class="bar">Ops Remote Diagnostics Console</div>
        <div class="wrap">
            <form method="post">
                <label>Target host</label>
                <input name="target" value="{escape(target)}">
                <button type="submit">Run</button>
            </form>
            <pre>{escape(output or 'Awaiting command...')}</pre>
            {flag}
            {nav_block()}
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/idor/profile/<int:user_id>")
@login_required
def idor_profile(user_id: int):
    conn = get_conn()
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    vuln_note = conn.execute("SELECT * FROM notes WHERE owner_id = ?", (user_id,)).fetchone()
    conn.close()

    profile_html = "<p>User not found</p>"
    if target:
        profile_html = f"""
        <table>
            <tr><td>ID</td><td>{target['id']}</td></tr>
            <tr><td>Username</td><td>{escape(target['username'])}</td></tr>
            <tr><td>Name</td><td>{escape(target['full_name'])}</td></tr>
            <tr><td>Email</td><td>{escape(target['email'])}</td></tr>
            <tr><td>Role</td><td>{escape(target['role'])}</td></tr>
            <tr><td>Mission</td><td>{escape(target['mission'])}</td></tr>
        </table>
        """

    flag = ""
    me = current_user()
    if target and me and target["id"] != me["id"]:
        flag = f"<div class='flag'>{FLAGS['idor']}</div>"

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Employee Cabinet</title>
        <style>
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f8fafc;
                color: #0f172a;
            }}
            .header {{
                background: white;
                border-bottom: 1px solid #e2e8f0;
                padding: 20px 30px;
                font-size: 24px;
                font-weight: bold;
            }}
            .container {{
                max-width: 900px;
                margin: 24px auto;
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 24px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .note {{
                margin-top: 20px;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                padding: 16px;
                border-radius: 8px;
            }}
            .flag {{
                margin-top: 14px;
                padding: 10px;
                background: #ecfdf5;
                border: 1px solid #16a34a;
                color: #166534;
            }}
            a {{ color: #2563eb; }}
        </style>
    </head>
    <body>
        <div class="header">Employee Cabinet</div>
        <div class="container">
            <h2>Profile overview</h2>
            {profile_html}
            <div class="note">
                <h3>Personal note</h3>
                <pre>{escape(vuln_note['body'] if vuln_note else 'Нет')}</pre>
            </div>
            {flag}
            {nav_block()}
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/bruteforce", methods=["GET", "POST"])
def bruteforce_login():
    vuln_msg = ""
    safe_msg = ""

    if request.method == "POST":
        mode = request.form.get("mode")
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        conn = get_conn()

        if mode == "vuln":
            user = conn.execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username, password),
            ).fetchone()
            if user:
                vuln_msg = f"<div class='flag'>{FLAGS['bruteforce']}</div>"
            else:
                vuln_msg = "<div class='err'>Wrong credentials</div>"

        elif mode == "safe":
            row = conn.execute(
                "SELECT * FROM login_attempts WHERE username = ?",
                (username,),
            ).fetchone()

            now = time.time()
            tries = row["tries"] if row else 0
            last_try = row["last_try"] if row else 0

            if tries >= 5 and now - last_try < 60:
                safe_msg = "<div class='err'>Too many attempts. Try later.</div>"
            else:
                user = conn.execute(
                    "SELECT * FROM users WHERE username = ? AND password = ?",
                    (username, password),
                ).fetchone()
                if user:
                    safe_msg = "<div class='ok'>Authenticated</div>"
                    conn.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
                else:
                    conn.execute(
                        "INSERT INTO login_attempts(username, tries, last_try) VALUES(?, 1, ?) "
                        "ON CONFLICT(username) DO UPDATE SET tries = tries + 1, last_try = excluded.last_try",
                        (username, now),
                    )
                    safe_msg = "<div class='err'>Denied</div>"

        conn.commit()
        conn.close()

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Access Center</title>
        <style>
            body {{
                margin: 0;
                font-family: Inter, Arial, sans-serif;
                background: #0f172a;
                color: white;
            }}
            .wrap {{
                max-width: 1100px;
                margin: 40px auto;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }}
            .panel {{
                background: #111827;
                border: 1px solid #1f2937;
                border-radius: 18px;
                padding: 24px;
            }}
            input {{
                width: 100%;
                padding: 11px;
                margin-bottom: 12px;
                border-radius: 10px;
                border: 1px solid #374151;
                background: #030712;
                color: white;
            }}
            button {{
                width: 100%;
                padding: 11px;
                border: 0;
                border-radius: 10px;
                background: #3b82f6;
                color: white;
                font-weight: bold;
            }}
            .flag {{
                margin-top: 14px;
                padding: 10px;
                background: #052e16;
                border: 1px solid #166534;
                color: #86efac;
            }}
            .err {{ color: #fca5a5; margin-top: 10px; }}
            .ok {{ color: #86efac; margin-top: 10px; }}
            a {{ color: #93c5fd; }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <div class="panel">
                <h2>Standard access</h2>
                <form method="post">
                    <input type="hidden" name="mode" value="vuln">
                    <input name="username" placeholder="Username" value="admin">
                    <input name="password" placeholder="Password">
                    <button type="submit">Sign in</button>
                </form>
                {vuln_msg}
            </div>

            <div class="panel">
                <h2>Protected access</h2>
                <form method="post">
                    <input type="hidden" name="mode" value="safe">
                    <input name="username" placeholder="Username" value="admin">
                    <input name="password" placeholder="Password">
                    <button type="submit">Sign in</button>
                </form>
                {safe_msg}
            </div>
        </div>
        <div style="max-width:1100px;margin:0 auto 40px;">{nav_block()}</div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/upload", methods=["GET", "POST"])
def upload_lab():
    message = ""

    if request.method == "POST":
        mode = request.form.get("mode")
        f = request.files.get("file")

        if f and f.filename:
            filename = secure_filename(f.filename)

            if mode == "vuln":
                path = UPLOADS_DIR / filename
                f.save(path)
                message += f"<div class='flag'>{FLAGS['upload']}</div>"
                message += f"<div class='ok'>Uploaded: {escape(filename)}</div>"

            elif mode == "safe":
                allowed = {'.txt', '.png', '.jpg', '.jpeg', '.pdf'}
                ext = Path(filename).suffix.lower()
                if ext not in allowed:
                    message += "<div class='err'>File type is not allowed</div>"
                else:
                    path = SAFE_UPLOADS_DIR / filename
                    f.save(path)
                    message += f"<div class='ok'>Stored: {escape(filename)}</div>"

    vuln_files = [p.name for p in UPLOADS_DIR.iterdir() if p.is_file()]
    safe_files = [p.name for p in SAFE_UPLOADS_DIR.iterdir() if p.is_file()]

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Upload Service</title>
        <style>
            body {{
                margin: 0;
                font-family: Verdana, sans-serif;
                background: #f5f7fb;
                color: #1f2937;
            }}
            .header {{
                background: #1e40af;
                color: white;
                padding: 18px 24px;
                font-size: 22px;
            }}
            .wrap {{
                max-width: 1000px;
                margin: 24px auto;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }}
            .card {{
                background: white;
                border: 1px solid #dbe2ea;
                border-radius: 10px;
                padding: 20px;
            }}
            input[type=file] {{
                margin: 10px 0 14px;
            }}
            button {{
                background: #1e40af;
                color: white;
                border: none;
                padding: 10px 14px;
                border-radius: 6px;
            }}
            .flag {{
                margin-top: 14px;
                padding: 10px;
                background: #ecfdf5;
                border: 1px solid #16a34a;
                color: #166534;
            }}
            .ok {{ color: #166534; margin-top: 10px; }}
            .err {{ color: #b91c1c; margin-top: 10px; }}
            a {{ color: #1e40af; }}
        </style>
    </head>
    <body>
        <div class="header">Electronic Document Upload</div>
        <div class="wrap">
            <div class="card">
                <h3>Public intake</h3>
                <form method="post" enctype="multipart/form-data">
                    <input type="hidden" name="mode" value="vuln">
                    <input type="file" name="file">
                    <button type="submit">Upload</button>
                </form>
                <p>Files: {', '.join(escape(x) for x in vuln_files) if vuln_files else 'empty'}</p>
            </div>

            <div class="card">
                <h3>Checked intake</h3>
                <form method="post" enctype="multipart/form-data">
                    <input type="hidden" name="mode" value="safe">
                    <input type="file" name="file">
                    <button type="submit">Upload</button>
                </form>
                <p>Files: {', '.join(escape(x) for x in safe_files) if safe_files else 'empty'}</p>
            </div>
        </div>
        <div style="max-width:1000px;margin:0 auto 30px;">
            {message}
            {nav_block()}
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password),
    ).fetchone()
    conn.close()

    if user:
        session["user_id"] = user["id"]
        return jsonify({
            "ok": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
            }
        }), 200

    return jsonify({
        "ok": False,
        "error": "invalid_credentials"
    }), 401

ensure_initialized()

if __name__ == "__main__":
    print("CTF lab is starting on http://127.0.0.1:5000")
    app.run(debug=True)
