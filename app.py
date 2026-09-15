import functools
import os
import sqlite3

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from jinja2 import DictLoader
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "memo.db")

# 초기 데이터. 실서비스에 올릴 거면 전부 환경변수로 덮어써라.
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")
ADMIN_MEMO_TITLE = "대외비"
ADMIN_MEMO_BODY = os.environ.get("FLAG", "SBOB{0nly_4dm1n_c4n_r34d_h1s_0wn_m3m0}")

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
    """스키마를 만들고 admin 계정과 admin 메모를 심는다. 몇 번 돌려도 안전하다."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title      TEXT NOT NULL,
                body       TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_memos_user ON memos(user_id)")

        admin_id = db.execute(
            "SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)
        ).fetchone()
        if admin_id is None:
            cur = db.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD)),
            )
            admin_id = (cur.lastrowid,)

        has_memo = db.execute(
            "SELECT 1 FROM memos WHERE user_id = ?", (admin_id[0],)
        ).fetchone()
        if has_memo is None:
            db.execute(
                "INSERT INTO memos (user_id, title, body) VALUES (?, ?, ?)",
                (admin_id[0], ADMIN_MEMO_TITLE, ADMIN_MEMO_BODY),
            )


# ---------- 인증 ----------

def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return get_db().execute(
        "SELECT id, username, is_admin FROM users WHERE id = ?", (uid,)
    ).fetchone()


@app.context_processor
def inject_user():
    """메뉴바가 모든 화면에서 로그인 상태를 알아야 한다."""
    return {"user": current_user()}


def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if current_user() is None:
            flash("로그인이 필요합니다.")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        u = current_user()
        if u is None:
            flash("로그인이 필요합니다.")
            return redirect(url_for("login"))
        if not u["is_admin"]:
            abort(403)
        return view(*a, **kw)
    return wrapped


def own_memo_or_404(memo_id):
    """소유권 검사. 남의 메모는 403이 아니라 404 — 존재 여부조차 흘리지 않는다."""
    memo = get_db().execute(
        "SELECT * FROM memos WHERE id = ? AND user_id = ?",
        (memo_id, session["user_id"]),
    ).fetchone()
    if memo is None:
        abort(404)
    return memo


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
  word-break:keep-all;
  overflow-wrap:break-word;
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
.desk{ display:flex; justify-content:center; padding:48px 16px 80px; }

/* --- 윈도우: 폼은 원래 시스템 다이얼로그였다 --- */
.win{
  width:100%; max-width:420px;
  background:var(--paper);
  border:2px solid var(--ink);
  box-shadow:6px 6px 0 var(--ink);
  animation:open .16s steps(4) both;
}
.win--wide{ max-width:660px; }
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
.field input,.field textarea{
  width:100%; padding:8px 10px;
  font-family:inherit; font-size:15px;
  color:var(--ink); background:var(--paper);
  border:2px solid var(--ink); border-radius:0;
}
.field textarea{ min-height:200px; line-height:1.8; resize:vertical; }
.field input:focus,.field textarea:focus{ outline:3px solid var(--ink); outline-offset:2px; }

.actions{ display:flex; align-items:center; justify-content:flex-end; gap:10px; margin-top:22px; }
.actions--split{ justify-content:space-between; }
.actions__group{ display:flex; align-items:center; gap:10px; }
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
.btn--sm{ padding:5px 14px; font-size:14px; box-shadow:2px 2px 0 var(--ink); }
.btn:active{ transform:translate(3px,3px); box-shadow:none; }
.btn--sm:active{ transform:translate(2px,2px); }
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

/* --- 목록 --- */
.toolbar{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin:0 0 16px; }
.toolbar__count{ margin:0; font-size:14px; font-weight:700; }

.list{ margin:0; padding:0; list-style:none; border:2px solid var(--ink); }
.list li + li{ border-top:2px solid var(--ink); }
.list a{
  display:flex; align-items:baseline; justify-content:space-between; gap:14px;
  padding:11px 13px;
  color:var(--ink); text-decoration:none;
}
.list a:hover,.list a:focus-visible{ background:var(--ink); color:var(--paper); outline:none; }
.list__title{ font-weight:700; }
.list__date{ flex:none; font-size:13px; }

.empty{ padding:28px 16px; border:2px dashed var(--ink); text-align:center; }
.empty p{ margin:0 0 16px; }

/* --- 문서 --- */
.meta{ margin:0 0 18px; padding-bottom:14px; border-bottom:2px solid var(--ink); font-size:13px; }
.doc{ margin:0; white-space:pre-wrap; line-height:1.85; }

/* --- 표 --- */
.tablewrap{ overflow-x:auto; border:2px solid var(--ink); }
.table{ width:100%; border-collapse:collapse; font-size:14px; }
.table th,.table td{ padding:9px 12px; text-align:left; white-space:nowrap; }
.table thead th{ background:var(--ink); color:var(--paper); font-weight:700; }
.table tbody tr + tr td{ border-top:2px solid var(--ink); }
.badge{ display:inline-block; padding:0 7px; border:2px solid var(--ink); font-size:12px; font-weight:700; }

@media (max-width:480px){
  .desk{ padding:28px 12px 56px; }
  .win{ box-shadow:4px 4px 0 var(--ink); }
  .win__body{ padding:20px 18px 22px; }
  .actions--split{ flex-direction:column; align-items:stretch; }
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
      {% if user['is_admin'] and request.endpoint != 'admin' %}
        <a class="menuitem" href="{{ url_for('admin') }}">관리자</a>
      {% endif %}
      <span class="menubar__who">{{ user['username'] }}</span>
      <form method="post" action="{{ url_for('logout') }}">
        <button class="menuitem" type="submit">로그아웃</button>
      </form>
    {% else %}
      {% if request.endpoint != 'login' %}<a class="menuitem" href="{{ url_for('login') }}">로그인</a>{% endif %}
      {% if request.endpoint != 'register' %}<a class="menuitem" href="{{ url_for('register') }}">회원가입</a>{% endif %}
    {% endif %}
  </div>
</nav>

<main class="desk">
  <section class="win {% block wide %}{% endblock %}">
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

    "landing.html": """
{% extends "base.html" %}
{% block title %}메모{% endblock %}
{% block body %}
  <p class="lead">로그인이 필요합니다.</p>
  <p class="note">아이디와 비밀번호만 정하면 바로 쓸 수 있습니다.</p>
  <div class="actions">
    <a class="btn" href="{{ url_for('register') }}">회원가입</a>
    <a class="btn btn--go" href="{{ url_for('login') }}">로그인</a>
  </div>
{% endblock %}
""",

    "memos.html": """
{% extends "base.html" %}
{% block title %}내 메모{% endblock %}
{% block wide %}win--wide{% endblock %}
{% block body %}
  {% if memos %}
    <div class="toolbar">
      <p class="toolbar__count">{{ memos|length }}개</p>
      <a class="btn btn--go btn--sm" href="{{ url_for('memo_new') }}">새 메모</a>
    </div>
    <ul class="list">
      {% for m in memos %}
        <li>
          <a href="{{ url_for('memo_detail', memo_id=m['id']) }}">
            <span class="list__title">{{ m['title'] }}</span>
            <span class="list__date">{{ m['updated_at'][:10] }}</span>
          </a>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <div class="empty">
      <p>아직 메모가 없습니다.</p>
      <a class="btn btn--go" href="{{ url_for('memo_new') }}">첫 메모 쓰기</a>
    </div>
  {% endif %}
{% endblock %}
""",

    "memo_form.html": """
{% extends "base.html" %}
{% block title %}{{ '메모 수정' if memo else '새 메모' }}{% endblock %}
{% block wide %}win--wide{% endblock %}
{% block body %}
  <form method="post">
    <div class="field">
      <label for="title">제목</label>
      <input id="title" name="title" value="{{ title }}" maxlength="120" autofocus required>
    </div>
    <div class="field">
      <label for="body">내용</label>
      <textarea id="body" name="body">{{ body }}</textarea>
    </div>
    <div class="actions">
      <a class="btn" href="{{ url_for('memo_detail', memo_id=memo['id']) if memo else url_for('index') }}">취소</a>
      <button class="btn btn--go" type="submit">{{ '저장하기' if memo else '만들기' }}</button>
    </div>
  </form>
{% endblock %}
""",

    "memo_detail.html": """
{% extends "base.html" %}
{% block title %}{{ memo['title'] }}{% endblock %}
{% block wide %}win--wide{% endblock %}
{% block body %}
  <p class="meta">작성 {{ memo['created_at'][:16] }} · 수정 {{ memo['updated_at'][:16] }}</p>
  <p class="doc">{{ memo['body'] }}</p>
  <div class="actions actions--split">
    <a class="btn btn--sm" href="{{ url_for('index') }}">목록</a>
    <span class="actions__group">
      <form method="post" action="{{ url_for('memo_delete', memo_id=memo['id']) }}"
            onsubmit="return confirm('메모를 삭제합니다. 되돌릴 수 없습니다.')">
        <button class="btn btn--sm" type="submit">삭제</button>
      </form>
      <a class="btn btn--go btn--sm" href="{{ url_for('memo_edit', memo_id=memo['id']) }}">수정</a>
    </span>
  </div>
{% endblock %}
""",

    "admin.html": """
{% extends "base.html" %}
{% block title %}관리자 · 회원 목록{% endblock %}
{% block wide %}win--wide{% endblock %}
{% block body %}
  <div class="toolbar">
    <p class="toolbar__count">회원 {{ rows|length }}명</p>
    <a class="btn btn--sm" href="{{ url_for('index') }}">내 메모</a>
  </div>
  <div class="tablewrap">
    <table class="table">
      <thead>
        <tr><th>ID</th><th>아이디</th><th>권한</th><th>메모</th><th>가입일</th></tr>
      </thead>
      <tbody>
        {% for r in rows %}
          <tr>
            <td>{{ r['id'] }}</td>
            <td>{{ r['username'] }}</td>
            <td>{% if r['is_admin'] %}<span class="badge">관리자</span>{% else %}회원{% endif %}</td>
            <td>{{ r['memo_count'] }}</td>
            <td>{{ r['created_at'][:10] }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <p class="swap">회원 목록만 봅니다. 다른 사람의 메모는 관리자도 열 수 없습니다.</p>
{% endblock %}
""",

    "error.html": """
{% extends "base.html" %}
{% block title %}오류 {{ code }}{% endblock %}
{% block body %}
  <p class="lead">{{ headline }}</p>
  <p class="note">{{ detail }}</p>
  <div class="actions">
    <a class="btn btn--go" href="{{ url_for('index') }}">처음으로</a>
  </div>
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


# ---------- 계정 ----------

@app.route("/")
def index():
    if current_user() is None:
        return render_template("landing.html")
    memos = get_db().execute(
        "SELECT id, title, updated_at FROM memos WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("memos.html", memos=memos)


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


# ---------- 메모 ----------

@app.route("/memos/new", methods=["GET", "POST"])
@login_required
def memo_new():
    title = body = ""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "")

        if not title:
            flash("제목을 입력하세요.")
        else:
            db = get_db()
            cur = db.execute(
                "INSERT INTO memos (user_id, title, body) VALUES (?, ?, ?)",
                (session["user_id"], title, body),
            )
            db.commit()
            return redirect(url_for("memo_detail", memo_id=cur.lastrowid))

    return render_template("memo_form.html", memo=None, title=title, body=body)


@app.route("/memos/<int:memo_id>")
@login_required
def memo_detail(memo_id):
    return render_template("memo_detail.html", memo=own_memo_or_404(memo_id))


@app.route("/memos/<int:memo_id>/edit", methods=["GET", "POST"])
@login_required
def memo_edit(memo_id):
    memo = own_memo_or_404(memo_id)
    title, body = memo["title"], memo["body"]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "")

        if not title:
            flash("제목을 입력하세요.")
        else:
            db = get_db()
            db.execute(
                "UPDATE memos SET title = ?, body = ?, updated_at = datetime('now','localtime') "
                "WHERE id = ? AND user_id = ?",
                (title, body, memo_id, session["user_id"]),
            )
            db.commit()
            return redirect(url_for("memo_detail", memo_id=memo_id))

    return render_template("memo_form.html", memo=memo, title=title, body=body)


@app.route("/memos/<int:memo_id>/delete", methods=["POST"])
@login_required
def memo_delete(memo_id):
    own_memo_or_404(memo_id)
    db = get_db()
    db.execute("DELETE FROM memos WHERE id = ? AND user_id = ?", (memo_id, session["user_id"]))
    db.commit()
    flash("메모를 삭제했습니다.")
    return redirect(url_for("index"))


# ---------- 관리자 ----------

@app.route("/admin")
@admin_required
def admin():
    rows = get_db().execute(
        """
        SELECT u.id, u.username, u.is_admin, u.created_at,
               COUNT(m.id) AS memo_count
        FROM users u
        LEFT JOIN memos m ON m.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id
        """
    ).fetchall()
    return render_template("admin.html", rows=rows)


# ---------- 에러 ----------

@app.errorhandler(403)
def forbidden(e):
    return render_template(
        "error.html",
        code=403,
        headline="권한이 없습니다.",
        detail="관리자만 들어갈 수 있는 곳입니다.",
    ), 403


@app.errorhandler(404)
def not_found(e):
    return render_template(
        "error.html",
        code=404,
        headline="찾을 수 없습니다.",
        detail="주소가 틀렸거나, 내 메모가 아닙니다.",
    ), 404


init_db()

if __name__ == "__main__":
    # macOS는 5000번을 AirPlay Receiver가 선점한다. 기본값을 5001로 둔다.
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
