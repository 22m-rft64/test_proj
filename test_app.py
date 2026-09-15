import sqlite3

import pytest

import app as m


@pytest.fixture
def db_path(tmp_path):
    """테스트마다 빈 임시 DB를 쓴다. 개발용 memo.db는 건드리지 않는다."""
    m.DB_PATH = str(tmp_path / "test.db")
    m.init_db()
    m.app.config["TESTING"] = True
    return m.DB_PATH


@pytest.fixture
def client(db_path):
    with m.app.test_client() as c:
        yield c


@pytest.fixture
def other(db_path):
    """같은 DB를 보는 두 번째 브라우저."""
    with m.app.test_client() as c:
        yield c


def signup(client, username="tester", password="pw1234", password2=None):
    return client.post("/register", data={
        "username": username,
        "password": password,
        "password2": password if password2 is None else password2,
    })


def signin(client, username="tester", password="pw1234"):
    return client.post("/login", data={"username": username, "password": password})


def account(client, username="tester", password="pw1234"):
    signup(client, username, password)
    signin(client, username, password)


def write_memo(client, title="회의록", body="내용입니다"):
    r = client.post("/memos/new", data={"title": title, "body": body})
    return int(r.headers["Location"].rstrip("/").rsplit("/", 1)[-1])


# ---------- 계정 ----------

def test_익명_홈은_로그인_안내를_보여준다(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "로그인이 필요합니다" in r.get_data(as_text=True)


def test_가입하면_로그인_페이지로_간다(client):
    r = signup(client)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login")


def test_중복_아이디는_거부된다(client):
    signup(client)
    assert "이미 사용 중인 아이디입니다." in signup(client).get_data(as_text=True)


def test_비밀번호_확인이_다르면_거부된다(client):
    r = signup(client, password="aaa", password2="bbb")
    assert "비밀번호가 일치하지 않습니다." in r.get_data(as_text=True)


def test_빈_입력은_거부된다(client):
    r = signup(client, username="", password="")
    assert "아이디와 비밀번호를 입력하세요." in r.get_data(as_text=True)


def test_틀린_비밀번호로는_로그인할_수_없다(client):
    signup(client)
    r = signin(client, password="wrong")
    assert "아이디 또는 비밀번호가 올바르지 않습니다." in r.get_data(as_text=True)


def test_없는_계정으로는_로그인할_수_없다(client):
    r = signin(client, username="nobody")
    assert "아이디 또는 비밀번호가 올바르지 않습니다." in r.get_data(as_text=True)


def test_로그인하면_세션이_유지된다(client):
    account(client)
    body = client.get("/").get_data(as_text=True)
    assert "tester" in body
    assert "아직 메모가 없습니다." in body


def test_로그인_상태에서는_로그인_가입_페이지를_막는다(client):
    account(client)
    assert client.get("/login").status_code == 302
    assert client.get("/register").status_code == 302


def test_로그아웃하면_세션이_끊긴다(client):
    account(client)
    client.post("/logout")
    assert "로그인이 필요합니다" in client.get("/").get_data(as_text=True)


def test_비밀번호는_평문으로_저장되지_않는다(client, db_path):
    signup(client)
    row = sqlite3.connect(db_path).execute(
        "SELECT password_hash FROM users WHERE username = 'tester'"
    ).fetchone()
    assert row[0] != "pw1234"
    assert row[0].startswith("scrypt:")


# ---------- 메모 CRUD ----------

def test_메모를_작성하면_상세로_간다(client):
    account(client)
    memo_id = write_memo(client, "첫 메모", "본문")
    body = client.get(f"/memos/{memo_id}").get_data(as_text=True)
    assert "첫 메모" in body
    assert "본문" in body


def test_제목이_없으면_작성되지_않는다(client):
    account(client)
    r = client.post("/memos/new", data={"title": "  ", "body": "본문"})
    assert r.status_code == 200
    assert "제목을 입력하세요." in r.get_data(as_text=True)


def test_목록에_내_메모가_보인다(client):
    account(client)
    write_memo(client, "장보기")
    write_memo(client, "회의 준비")
    body = client.get("/").get_data(as_text=True)
    assert "장보기" in body
    assert "회의 준비" in body


def test_메모를_수정할_수_있다(client):
    account(client)
    memo_id = write_memo(client, "초안", "예전 내용")
    client.post(f"/memos/{memo_id}/edit", data={"title": "완성본", "body": "새 내용"})
    body = client.get(f"/memos/{memo_id}").get_data(as_text=True)
    assert "완성본" in body
    assert "새 내용" in body
    assert "예전 내용" not in body


def test_메모를_삭제할_수_있다(client):
    account(client)
    memo_id = write_memo(client, "지울 메모")
    client.post(f"/memos/{memo_id}/delete")
    assert client.get(f"/memos/{memo_id}").status_code == 404
    assert "지울 메모" not in client.get("/").get_data(as_text=True)


# ---------- 소유권 격리 (보안 핵심) ----------

def test_비로그인은_메모에_접근할_수_없다(client):
    for path in ["/memos/new", "/memos/1", "/memos/1/edit"]:
        r = client.get(path)
        assert r.status_code == 302, path
        assert "/login" in r.headers["Location"], path
    assert client.post("/memos/1/delete").status_code == 302


def test_남의_메모는_상세_조회가_404다(client, other):
    account(client, "alice")
    memo_id = write_memo(client, "앨리스의 비밀")

    account(other, "bob")
    assert other.get(f"/memos/{memo_id}").status_code == 404


def test_남의_메모는_목록에_안_보인다(client, other):
    account(client, "alice")
    write_memo(client, "앨리스의 비밀")

    account(other, "bob")
    assert "앨리스의 비밀" not in other.get("/").get_data(as_text=True)


def test_남의_메모는_수정되지_않는다(client, other, db_path):
    account(client, "alice")
    memo_id = write_memo(client, "앨리스의 비밀", "원본")

    account(other, "bob")
    assert other.get(f"/memos/{memo_id}/edit").status_code == 404
    assert other.post(f"/memos/{memo_id}/edit",
                      data={"title": "탈취", "body": "덮어씀"}).status_code == 404

    row = sqlite3.connect(db_path).execute(
        "SELECT title, body FROM memos WHERE id = ?", (memo_id,)
    ).fetchone()
    assert row == ("앨리스의 비밀", "원본")


def test_남의_메모는_삭제되지_않는다(client, other, db_path):
    account(client, "alice")
    memo_id = write_memo(client, "앨리스의 비밀")

    account(other, "bob")
    assert other.post(f"/memos/{memo_id}/delete").status_code == 404

    count = sqlite3.connect(db_path).execute(
        "SELECT COUNT(*) FROM memos WHERE id = ?", (memo_id,)
    ).fetchone()[0]
    assert count == 1


# ---------- 관리자 ----------

def test_admin_계정과_메모가_미리_생성된다(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    admin = con.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
    assert admin is not None
    assert admin["is_admin"] == 1

    memo = con.execute("SELECT * FROM memos WHERE user_id = ?", (admin["id"],)).fetchone()
    assert memo is not None
    assert memo["body"].startswith("SBOB{")


def test_init_db를_여러_번_돌려도_중복되지_않는다(db_path):
    m.init_db()
    m.init_db()
    con = sqlite3.connect(db_path)
    assert con.execute("SELECT COUNT(*) FROM users WHERE username='admin'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM memos").fetchone()[0] == 1


def test_admin은_관리자_페이지에서_전체_회원을_본다(client):
    account(client, "alice")
    client.post("/logout")
    account(client, "bob")
    client.post("/logout")
    signin(client, "admin", m.ADMIN_PASSWORD)

    body = client.get("/admin").get_data(as_text=True)
    assert "alice" in body
    assert "bob" in body
    assert "admin" in body


def test_일반_회원은_관리자_페이지에_들어갈_수_없다(client):
    account(client, "alice")
    assert client.get("/admin").status_code == 403


def test_비로그인은_관리자_페이지에서_로그인으로_밀린다(client):
    r = client.get("/admin")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_관리자도_남의_메모는_못_본다(client, other):
    account(client, "alice")
    memo_id = write_memo(client, "앨리스의 비밀")

    signin(other, "admin", m.ADMIN_PASSWORD)
    assert other.get(f"/memos/{memo_id}").status_code == 404


def test_플래그는_admin_메모_안에만_있고_남에게_노출되지_않는다(client, db_path):
    flag = sqlite3.connect(db_path).execute(
        "SELECT body FROM memos WHERE title = ?", (m.ADMIN_MEMO_TITLE,)
    ).fetchone()[0]

    account(client, "alice")
    assert flag not in client.get("/").get_data(as_text=True)
    assert client.get("/memos/1").status_code == 404

    client.post("/logout")
    signin(client, "admin", m.ADMIN_PASSWORD)
    assert flag in client.get("/memos/1").get_data(as_text=True)
