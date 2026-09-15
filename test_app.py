import sqlite3

import pytest

import app as m


@pytest.fixture
def client(tmp_path):
    """테스트마다 빈 임시 DB를 쓴다. 개발용 memo.db는 건드리지 않는다."""
    m.DB_PATH = str(tmp_path / "test.db")
    m.init_db()
    m.app.config["TESTING"] = True
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
    r = signup(client)
    assert "이미 사용 중인 아이디입니다." in r.get_data(as_text=True)


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
    signup(client)
    assert signin(client).status_code == 302
    assert "tester님, 로그인 상태입니다." in client.get("/").get_data(as_text=True)


def test_로그인_상태에서는_로그인_가입_페이지를_막는다(client):
    signup(client)
    signin(client)
    assert client.get("/login").status_code == 302
    assert client.get("/register").status_code == 302


def test_로그아웃하면_세션이_끊긴다(client):
    signup(client)
    signin(client)
    client.post("/logout")
    assert "로그인이 필요합니다" in client.get("/").get_data(as_text=True)


def test_비밀번호는_평문으로_저장되지_않는다(client):
    signup(client)
    row = sqlite3.connect(m.DB_PATH).execute(
        "SELECT password_hash FROM users WHERE username = 'tester'"
    ).fetchone()
    assert row[0] != "pw1234"
    assert row[0].startswith("scrypt:")
