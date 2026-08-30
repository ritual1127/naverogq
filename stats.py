"""방문과 검사 횟수만 세는 자리.

개인을 알아볼 수 있는 것은 남기지 않는다. IP 는 저장하지 않고
`소금 + 그 주 + IP` 를 해시한 16자만 남긴다. 소금은 서버마다 다르고
주가 바뀌면 같은 사람이라도 다른 값이 되므로, 주가 지나면 이어 볼 수 없다.
주 단위인 이유는 북극성 지표가 '주간 재검사 사용자 수'여서다.
"""
import datetime
import hashlib
import os
import secrets
import sqlite3

DEFAULT_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "cad-checker")

_salt = None


def db_path():
    return os.environ.get("CADLENS_STAT_DB") or os.path.join(DEFAULT_DIR, "stats.db")


def _salt_value():
    """서버마다 다른 값. 이게 없으면 해시가 IP 사전 대입으로 되돌려진다."""
    global _salt
    if _salt is not None:
        return _salt
    env = os.environ.get("CADLENS_STAT_SALT")
    if env:
        _salt = env
        return _salt
    path = os.path.join(os.path.dirname(db_path()) or ".", "stat_salt")
    try:
        with open(path, encoding="ascii") as fh:
            _salt = fh.read().strip()
    except OSError:
        _salt = secrets.token_hex(16)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="ascii") as fh:
                fh.write(_salt)
        except OSError:
            pass          # 디스크에 못 써도 이번 실행 동안은 센다
    return _salt


def _connect():
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.execute("""CREATE TABLE IF NOT EXISTS hits(
        day TEXT NOT NULL, visitor TEXT NOT NULL, kind TEXT NOT NULL,
        n INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(day, visitor, kind)) WITHOUT ROWID""")
    return con


def client_ip(request):
    """프록시 뒤에 있다. 맨 앞 값이 진짜 접속자다."""
    ip = request.headers.get("cf-connecting-ip")
    if not ip:
        fwd = request.headers.get("x-forwarded-for", "")
        ip = fwd.split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    return ip or "?"


def visitor_id(ip, today=None):
    today = today or datetime.date.today()
    year, week, _ = today.isocalendar()
    raw = f"{_salt_value()}|{year}-W{week:02d}|{ip}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def bump(request, kind, today=None):
    """한 번 센다. 통계 때문에 검사가 실패하면 안 되므로 조용히 넘어간다."""
    today = today or datetime.date.today()
    try:
        con = _connect()
        try:
            with con:
                con.execute(
                    "INSERT INTO hits(day, visitor, kind, n) VALUES(?,?,?,1) "
                    "ON CONFLICT(day, visitor, kind) DO UPDATE SET n = n + 1",
                    (today.isoformat(), visitor_id(client_ip(request), today), kind))
        finally:
            con.close()
    except Exception as e:                                    # noqa: BLE001
        print(f"[stats] {kind} 세기 실패: {type(e).__name__}: {e}", flush=True)


CHECK_KINDS = ("check", "sample")


def summary(today=None, days=14):
    today = today or datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    try:
        con = _connect()
    except Exception:                                          # noqa: BLE001
        return {"available": False}
    with con:
        def one(sql, args=()):
            return con.execute(sql, args).fetchone()[0] or 0

        marks = ",".join("?" * len(CHECK_KINDS))
        day, week = today.isoformat(), monday.isoformat()
        out = {
            "available": True,
            "today": {
                "visitors": one("SELECT COUNT(DISTINCT visitor) FROM hits "
                                "WHERE day=? AND kind='visit'", (day,)),
                "checks": one(f"SELECT SUM(n) FROM hits WHERE day=? "
                              f"AND kind IN ({marks})", (day, *CHECK_KINDS)),
            },
            "week": {
                "since": week,
                "visitors": one("SELECT COUNT(DISTINCT visitor) FROM hits "
                                "WHERE day>=? AND kind='visit'", (week,)),
                "checks": one(f"SELECT SUM(n) FROM hits WHERE day>=? "
                              f"AND kind IN ({marks})", (week, *CHECK_KINDS)),
                # 북극성 지표 — 한 주에 두 번 이상 검사한 사람
                "recheckers": one(
                    f"SELECT COUNT(*) FROM (SELECT visitor, SUM(n) s FROM hits "
                    f"WHERE day>=? AND kind IN ({marks}) "
                    f"GROUP BY visitor HAVING s >= 2)", (week, *CHECK_KINDS)),
            },
            "total": {
                "visits": one("SELECT SUM(n) FROM hits WHERE kind='visit'"),
                "checks": one("SELECT SUM(n) FROM hits WHERE kind='check'"),
                "samples": one("SELECT SUM(n) FROM hits WHERE kind='sample'"),
                "days": one("SELECT COUNT(DISTINCT day) FROM hits"),
                "since": (con.execute("SELECT MIN(day) FROM hits").fetchone()[0]
                          or day),
            },
            "daily": [],
        }
        first = (today - datetime.timedelta(days=days - 1)).isoformat()
        rows = con.execute(
            f"SELECT day, COUNT(DISTINCT CASE WHEN kind='visit' THEN visitor END), "
            f"SUM(CASE WHEN kind IN ({marks}) THEN n ELSE 0 END) "
            f"FROM hits WHERE day>=? GROUP BY day ORDER BY day",
            (*CHECK_KINDS, first)).fetchall()
        out["daily"] = [{"day": d, "visitors": v or 0, "checks": c or 0}
                        for d, v, c in rows]
    con.close()
    return out
