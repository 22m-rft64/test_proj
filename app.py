import os
import sqlite3

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from jinja2 import DictLoader
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "memo.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# ---------- DB ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return get_db().execute("SELECT id, username FROM users WHERE id = ?", (uid,)).fetchone()


# ---------- 템플릿 (파일 하나로 끝내려고 DictLoader 사용) ----------

app.jinja_loader = DictLoader({
    "base.html": """
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>{% block title %}메모{% endblock %}</title></head>
<body>
<h1>메모 서비스</h1>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>
  {% endif %}
{% endwith %}
{% block body %}{% endblock %}
</body>
</html>
""",

    "index.html": """
{% extends "base.html" %}
{% block title %}홈{% endblock %}
{% block body %}
  {% if user %}
    <p>{{ user['username'] }}님, 로그인 상태입니다.</p>
    <form method="post" action="{{ url_for('logout') }}">
      <button type="submit">로그아웃</button>
    </form>
  {% else %}
    <p>로그인이 필요합니다.</p>
    <p>
      <a href="{{ url_for('register') }}">회원가입</a> |
      <a href="{{ url_for('login') }}">로그인</a>
    </p>
  {% endif %}
{% endblock %}
""",

    "register.html": """
{% extends "base.html" %}
{% block title %}회원가입{% endblock %}
{% block body %}
  <h2>회원가입</h2>
  <form method="post">
    <p><label>아이디 <input name="username" value="{{ username }}" required></label></p>
    <p><label>비밀번호 <input name="password" type="password" required></label></p>
    <p><label>비밀번호 확인 <input name="password2" type="password" required></label></p>
    <p><button type="submit">가입</button></p>
  </form>
  <p><a href="{{ url_for('login') }}">로그인으로</a></p>
{% endblock %}
""",

    "login.html": """
{% extends "base.html" %}
{% block title %}로그인{% endblock %}
{% block body %}
  <h2>로그인</h2>
  <form method="post">
    <p><label>아이디 <input name="username" value="{{ username }}" required></label></p>
    <p><label>비밀번호 <input name="password" type="password" required></label></p>
    <p><button type="submit">로그인</button></p>
  </form>
  <p><a href="{{ url_for('register') }}">회원가입으로</a></p>
{% endblock %}
""",
})


# ---------- 라우트 ----------

@app.route("/")
def index():
    return render_template("index.html", user=current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("index"))

    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not username or not password:
            flash("아이디와 비밀번호를 입력하세요.")
        elif password != password2:
            flash("비밀번호가 일치하지 않습니다.")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                flash("이미 사용 중인 아이디입니다.")
            else:
                flash("가입 완료. 로그인하세요.")
                return redirect(url_for("login"))

    return render_template("register.html", username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("index"))

    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        row = get_db().execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()

        if row is None or not check_password_hash(row["password_hash"], password):
            flash("아이디 또는 비밀번호가 올바르지 않습니다.")
        else:
            session.clear()
            session["user_id"] = row["id"]
            session.permanent = True
            return redirect(url_for("index"))

    return render_template("login.html", username=username)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("로그아웃되었습니다.")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
