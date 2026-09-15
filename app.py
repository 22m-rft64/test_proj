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


@app.context_processor
def inject_user():
    """메뉴바가 모든 화면에서 로그인 상태를 알아야 한다."""
    return {"user": current_user()}


# ---------- 스타일 ----------
# 1984 매킨토시 System. 1비트 흑백, blur 없는 검정 오프셋 그림자,
# 디더 점 패턴 바탕. 애플 6색은 메뉴바 로고에서 페이지당 한 번만 쓴다.

CSS = """
:root{ --ink:#000; --paper:#fff; }

*,*::before,*::after{ box-sizing:border-box; }

body{
  margin:0;
  min-height:100vh;
  font-family:'Gothic A1',system-ui,-apple-system,'Apple SD Gothic Neo',sans-serif;
  font-size:15px;
  line-height:1.7;
  color:var(--ink);
  background-color:var(--paper);
  background-image:radial-gradient(var(--ink) 1px,transparent 1.1px);
  background-size:5px 5px;
}

/* --- 메뉴바: 장식이 아니라 실제 네비게이션을 담는다 --- */
.menubar{
  position:sticky; top:0; z-index:10;
  display:flex; align-items:center; justify-content:space-between;
  gap:16px; flex-wrap:wrap;
  padding:6px 14px;
  background:var(--paper);
  border-bottom:2px solid var(--ink);
}
.menubar__app{
  display:flex; align-items:center; gap:8px;
  font-size:15px; font-weight:900; letter-spacing:-.02em;
  color:var(--ink); text-decoration:none;
}
.mark{
  flex:none; width:13px; height:16px;
  border:1px solid var(--ink);
  background:linear-gradient(
    #5fb44a 0 16.66%, #f5b024 16.66% 33.33%, #ee7b2d 33.33% 50%,
    #d8323c 50% 66.66%, #8e4a9e 66.66% 83.33%, #2e9bd6 83.33% 100%);
}
.menubar__nav{ display:flex; align-items:center; gap:2px; }
.menuitem{
  display:inline-block;
  padding:3px 10px;
  font-family:inherit; font-size:14px; font-weight:700; line-height:1.6;
  color:var(--ink); text-decoration:none;
  background:none; border:0; cursor:pointer;
}
.menuitem:hover,.menuitem:focus-visible{ background:var(--ink); color:var(--paper); outline:none; }
.menubar__who{ padding:3px 10px; font-size:14px; font-weight:700; }

/* --- 데스크탑 --- */
.desk{ display:flex; justify-content:center; padding:56px 16px 80px; }

/* --- 윈도우: 폼은 원래 시스템 다이얼로그였다 --- */
.win{
  width:100%; max-width:420px;
  background:var(--paper);
  border:2px solid var(--ink);
  box-shadow:6px 6px 0 var(--ink);
  animation:open .16s steps(4) both;
}
@keyframes open{ from{ transform:scale(.94); opacity:0; } to{ transform:scale(1); opacity:1; } }

.win__bar{
  display:flex; align-items:center; justify-content:center;
  padding:5px 8px;
  border-bottom:2px solid var(--ink);
  background:repeating-linear-gradient(var(--ink) 0 1px,var(--paper) 1px 3px);
}
.win__title{
  margin:0; padding:0 12px;
  background:var(--paper);
  font-size:14px; font-weight:900; letter-spacing:-.01em;
}
.win__body{ padding:24px 24px 26px; }

.lead{ margin:0 0 6px; font-size:19px; font-weight:900; letter-spacing:-.02em; line-height:1.4; }
.note{ margin:0; font-size:14px; }

/* --- 폼 --- */
.field{ margin:0 0 14px; }
.field label{ display:block; margin-bottom:5px; font-size:13px; font-weight:700; }
.field input{
  width:100%; padding:8px 10px;
  font-family:inherit; font-size:15px;
  color:var(--ink); background:var(--paper);
  border:2px solid var(--ink); border-radius:0;
}
.field input:focus{ outline:3px solid var(--ink); outline-offset:2px; }

.actions{ display:flex; align-items:center; justify-content:flex-end; gap:10px; margin-top:22px; }
.btn{
  display:inline-block;
  padding:8px 20px;
  font-family:inherit; font-size:15px; font-weight:700; line-height:1.6;
  color:var(--ink); background:var(--paper);
  text-decoration:none;
  border:2px solid var(--ink); border-radius:9px;
  box-shadow:3px 3px 0 var(--ink);
  cursor:pointer;
}
.btn--go{ color:var(--paper); background:var(--ink); }
.btn:active{ transform:translate(3px,3px); box-shadow:none; }
.btn:focus-visible{ outline:3px solid var(--ink); outline-offset:3px; }

.swap{ margin:20px 0 0; font-size:14px; }
.link{ color:var(--ink); font-weight:700; text-decoration-thickness:2px; text-underline-offset:3px; }

/* --- 경고 다이얼로그 --- */
.alert{
  display:flex; align-items:flex-start; gap:10px;
  margin:0 0 18px; padding:10px 12px;
  border:2px solid var(--ink);
  font-size:14px;
}
.alert__bang{
  flex:none; display:grid; place-items:center;
  width:22px; height:22px;
  border:2px solid var(--ink); border-radius:50%;
  font-size:14px; font-weight:900; line-height:1;
}

@media (max-width:480px){
  .desk{ padding:32px 12px 56px; }
  .win{ box-shadow:4px 4px 0 var(--ink); }
  .win__body{ padding:20px 18px 22px; }
}

@media (prefers-reduced-motion:reduce){
  .win{ animation:none; }
  .btn:active{ transform:none; }
}
"""


# ---------- 템플릿 (파일 하나로 끝내려고 DictLoader 사용) ----------

app.jinja_loader = DictLoader({
    "base.html": """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ self.title() }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gothic+A1:wght@400;700;900&display=swap">
<style>{{ css }}</style>
</head>
<body>

<nav class="menubar">
  <a class="menubar__app" href="{{ url_for('index') }}"><span class="mark" aria-hidden="true"></span>메모</a>
  <div class="menubar__nav">
    {% if user %}
      <span class="menubar__who">{{ user['username'] }}</span>
    {% else %}
      <a class="menuitem" href="{{ url_for('login') }}">로그인</a>
      <a class="menuitem" href="{{ url_for('register') }}">회원가입</a>
    {% endif %}
  </div>
</nav>

<main class="desk">
  <section class="win">
    <header class="win__bar">
      <h1 class="win__title">{% block title %}메모{% endblock %}</h1>
    </header>
    <div class="win__body">
      {% for m in get_flashed_messages() %}
        <div class="alert" role="status"><span class="alert__bang" aria-hidden="true">!</span><span>{{ m }}</span></div>
      {% endfor %}
      {% block body %}{% endblock %}
    </div>
  </section>
</main>

</body>
</html>
""",

    "index.html": """
{% extends "base.html" %}
{% block title %}메모{% endblock %}
{% block body %}
  {% if user %}
    <p class="lead">{{ user['username'] }}님, 로그인 상태입니다.</p>
    <p class="note">메모 기능은 아직 없습니다. 지금은 계정을 만들고 로그인하는 것까지 됩니다.</p>
    <form class="actions" method="post" action="{{ url_for('logout') }}">
      <button class="btn" type="submit">로그아웃</button>
    </form>
  {% else %}
    <p class="lead">로그인이 필요합니다.</p>
    <p class="note">아이디와 비밀번호만 정하면 바로 쓸 수 있습니다.</p>
    <div class="actions">
      <a class="btn" href="{{ url_for('register') }}">회원가입</a>
      <a class="btn btn--go" href="{{ url_for('login') }}">로그인</a>
    </div>
  {% endif %}
{% endblock %}
""",

    "register.html": """
{% extends "base.html" %}
{% block title %}회원가입{% endblock %}
{% block body %}
  <form method="post">
    <div class="field">
      <label for="username">아이디</label>
      <input id="username" name="username" value="{{ username }}" autocomplete="username" autofocus required>
    </div>
    <div class="field">
      <label for="password">비밀번호</label>
      <input id="password" name="password" type="password" autocomplete="new-password" required>
    </div>
    <div class="field">
      <label for="password2">비밀번호 확인</label>
      <input id="password2" name="password2" type="password" autocomplete="new-password" required>
    </div>
    <div class="actions">
      <button class="btn btn--go" type="submit">가입하기</button>
    </div>
  </form>
  <p class="swap">이미 계정이 있나요? <a class="link" href="{{ url_for('login') }}">로그인</a></p>
{% endblock %}
""",

    "login.html": """
{% extends "base.html" %}
{% block title %}로그인{% endblock %}
{% block body %}
  <form method="post">
    <div class="field">
      <label for="username">아이디</label>
      <input id="username" name="username" value="{{ username }}" autocomplete="username" autofocus required>
    </div>
    <div class="field">
      <label for="password">비밀번호</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>
    </div>
    <div class="actions">
      <button class="btn btn--go" type="submit">로그인</button>
    </div>
  </form>
  <p class="swap">계정이 없나요? <a class="link" href="{{ url_for('register') }}">회원가입</a></p>
{% endblock %}
""",
})

app.jinja_env.globals["css"] = CSS


# ---------- 라우트 ----------

@app.route("/")
def index():
    return render_template("index.html")


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
    app.run(host="0.0.0.0", port=8000)
