"""방문과 검사 횟수만 세는 자리.

개인을 알아볼 수 있는 것은 남기지 않는다. IP 는 저장하지 않고
`소금 + 그 주 + IP` 를 해시한 16자만 남긴다. 소금은 서버마다 다르고
주가 바뀌면 같은 사람이라도 다른 값이 되므로, 주가 지나면 이어 볼 수 없다.
주 단위인 이유는 북극성 지표가 '주간 재검사 사용자 수'여서다.
"""
import datetime
import hashlib
import os
import re
import secrets
import sqlite3
import threading
import time

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


D1_API = ("https://api.cloudflare.com/client/v4/accounts/{acct}"
          "/d1/database/{db}/query")


def d1_conf():
    """셋 다 있어야 D1 을 쓴다. 하나라도 없으면 이 서버의 sqlite 로 센다.
    Render 무료 플랜은 다시 뜰 때 디스크가 지워져 sqlite 는 0부터 시작한다."""
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    db = os.environ.get("CADLENS_D1_STATS")
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    return (acct, db, token) if acct and db and token else None


NEEDED = ("CLOUDFLARE_ACCOUNT_ID", "CADLENS_D1_STATS", "CLOUDFLARE_API_TOKEN")


def missing_conf():
    """D1 을 못 쓰는 이유를 이름으로만 알려 준다. 값은 내보내지 않는다."""
    return [k for k in NEEDED if not os.environ.get(k)]


def _d1(sql, params=(), timeout=10):
    import requests
    acct, db, token = d1_conf()
    r = requests.post(D1_API.format(acct=acct, db=db),
                      headers={"Authorization": f"Bearer {token}"},
                      json={"sql": sql, "params": [str(p) for p in params]},
                      timeout=timeout)
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(str(body.get("errors") or body)[:200])
    return [x.get("results") or [] for x in body.get("result", [])]


def _connect():
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.execute("""CREATE TABLE IF NOT EXISTS hits(
        day TEXT NOT NULL, visitor TEXT NOT NULL, kind TEXT NOT NULL,
        n INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(day, visitor, kind)) WITHOUT ROWID""")
    con.execute(NOTES_DDL)
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


# 코호트 — 주를 넘어 다시 오는가.
# 방문자 해시에 주차가 들어 있어서 주가 바뀌면 같은 사람도 다른 값이 된다. 그 해시로는
# 1주차에 온 사람이 2주차에 왔는지 알 수 없다. 그래서 처음 온 주를 브라우저에 남긴다.
# 쿠키는 쓰지 않는다 — 안 쓴다고 적어 두었고 이용자가 대부분 미성년이다. 대신 화면이
# 이미 쓰는 `cadcheck.*` 와 같은 자리(localStorage)에 두고, 그 값을 화면이 보내 준다.
# 남는 것은 그 주의 월요일 날짜 하나뿐이고 사람을 가리키는 값은 들어가지 않는다.
WEEK_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def monday_of(day):
    return day - datetime.timedelta(days=day.weekday())


def cohort(request, first, today=None):
    """처음 온 주를 돌려준다. 그 주가 아닌 때 다시 오면 `ret:처음온주` 로 센다.

    `first` 는 화면이 보낸 값이라 지어낼 수 있다. 날짜 모양이 아니면 버리고 이번 주로
    다시 잡는다. 지어낸 날짜를 넣으면 그 주 코호트에 한 명이 얹히는데, 방문 수를
    지어내는 것과 같은 정도라 따로 막지 않는다."""
    today = today or datetime.date.today()
    now = monday_of(today).isoformat()
    first = first if WEEK_RE.match(first or "") else ""
    if not first:
        bump(request, "new", today)
        return now
    if first != now:
        bump(request, f"ret:{first}", today)
    return first


UPSERT = ("INSERT INTO hits(day, visitor, kind, n) VALUES(?,?,?,1) "
          "ON CONFLICT(day, visitor, kind) DO UPDATE SET n = n + 1")


# 사람이 아닌 접속. 검색 엔진, 링크 미리보기 카드, 살아 있나 확인하는 도구,
# 스크립트가 여기 들어간다. UA 를 보고 거르는 것이라 UA 를 감추면 못 거른다.
# 완벽하지 않아도 방문 수가 실제보다 몇십 배 부푸는 것은 막는다.
BOT_UA = re.compile(
    r"bot|crawl|spider|slurp|scrap|fetch|monitor|uptime|preview|"
    r"curl|wget|python-requests|httpx|aiohttp|okhttp|go-http|java/|libwww|"
    r"headless|phantom|lighthouse|pagespeed|facebookexternalhit|embedly",
    re.IGNORECASE)


def is_bot(request):
    """UA 가 비어 있는 것도 사람이 아니라고 본다. 브라우저는 항상 보낸다."""
    ua = request.headers.get("user-agent", "") or ""
    return not ua.strip() or bool(BOT_UA.search(ua))


def bump(request, kind, today=None):
    """한 번 센다. 통계 때문에 검사가 실패하면 안 되므로 조용히 넘어간다."""
    if is_bot(request):
        return
    today = today or datetime.date.today()
    row = (today.isoformat(), visitor_id(client_ip(request), today), kind)
    if d1_conf():
        # 화면이 D1 응답을 기다릴 이유가 없다. 실패해도 검사는 그대로 간다.
        threading.Thread(target=_bump_d1, args=(row,), daemon=True).start()
        return
    try:
        con = _connect()
        try:
            with con:
                con.execute(UPSERT, row)
        finally:
            con.close()
    except Exception as e:                                    # noqa: BLE001
        print(f"[stats] {kind} 세기 실패: {type(e).__name__}: {e}", flush=True)


def _bump_d1(row):
    try:
        _d1(UPSERT, row)
        _cache[0] = 0.0                      # 다음 조회는 새로 읽는다
    except Exception as e:                                    # noqa: BLE001
        print(f"[stats] D1 세기 실패: {type(e).__name__}: {e}", flush=True)


"""사용자가 보낸 말 — 오류 신고와 문의.

표 이름이 `cadlens_notes` 인 이유: 이 D1 은 인터뷰 폼과 같이 쓰는데 거기에 이미
`notes` 표가 있다(답변에 직접 적은 글). 같은 이름으로 만들면 우리 INSERT 가
남의 표에 가서 깨진다 — 실제로 그렇게 깨져 봤다. 우리 표는 이름 앞에 프로젝트를 붙인다.

`hits` 와 달리 사람이 직접 쓴 글이 들어온다. 연락처는 적고 싶은 사람만 적는다.
도면 파일은 여기 넣지 않는다. 보내도 된다고 한 경우에만 서버 디스크에 따로 두고
여기에는 파일 이름만 남긴다.
"""
NOTES_DDL = """CREATE TABLE IF NOT EXISTS cadlens_notes(
    id TEXT PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL,
    text TEXT NOT NULL, spot TEXT, contact TEXT, job TEXT, file TEXT, shot TEXT)"""

NOTE_INSERT = ("INSERT INTO cadlens_notes(id, at, kind, text, spot, contact, job, file, shot) "
               "VALUES(?,?,?,?,?,?,?,?,?)")
NOTE_LIST = ("SELECT id, at, kind, text, spot, contact, job, file, shot FROM cadlens_notes "
             "ORDER BY at DESC LIMIT {n}")
NOTE_COLS = ("id", "at", "kind", "text", "spot", "contact", "job", "file", "shot")

_notes_ready = [False]


def _d1_notes():
    """D1 에는 표를 만들어 둔 적이 없을 수 있다. 프로세스마다 한 번만 확인한다."""
    if not _notes_ready[0]:
        _d1(NOTES_DDL)
        _notes_ready[0] = True


def note(kind, text, spot="", contact="", job="", file="", shot=""):
    """한 건 남기고 그 id 를 돌려준다. 못 남기면 RuntimeError.

    `spot` 은 사용자가 결과 화면에서 고른 자리다 — 몇 번 지적인지, 점수인지, 미리보기인지.
    `shot` 은 도면에서 끌어 고른 부분을 그림으로 저장한 파일 이름이다."""
    row = (secrets.token_hex(8), datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           kind, text, spot, contact, job, file, shot)
    if d1_conf():
        _d1_notes()
        _d1(NOTE_INSERT, row)
        return row[0]
    con = _connect()
    try:
        with con:
            con.execute(NOTE_INSERT, row)
    finally:
        con.close()
    return row[0]


NOTE_PICK = "SELECT job, file FROM cadlens_notes WHERE id = ?"   # 도면과 고른 부분은 job 폴더째 지운다
NOTE_DELETE = "DELETE FROM cadlens_notes WHERE id = ?"


def delete_note(note_id):
    """지워 달라는 요청을 받았을 때. 지운 글의 (검사 번호, 파일 이름) 을 돌려준다.
    그런 글이 없으면 None."""
    if d1_conf():
        _d1_notes()
        rows = _d1(NOTE_PICK, (note_id,))[0]
        if not rows:
            return None
        _d1(NOTE_DELETE, (note_id,))
        return rows[0].get("job") or "", rows[0].get("file") or ""
    con = _connect()
    try:
        row = con.execute(NOTE_PICK, (note_id,)).fetchone()
        if not row:
            return None
        with con:
            con.execute(NOTE_DELETE, (note_id,))
    finally:
        con.close()
    return row[0] or "", row[1] or ""


def notes(limit=200):
    if d1_conf():
        _d1_notes()
        return _d1(NOTE_LIST.format(n=int(limit)))[0]
    con = _connect()
    try:
        rows = con.execute(NOTE_LIST.format(n=int(limit))).fetchall()
    finally:
        con.close()
    return [dict(zip(NOTE_COLS, r)) for r in rows]


CHECK_KINDS = ("check", "sample")

_cache = [0.0, None]                         # 마지막으로 읽은 때, 그 값
CACHE_SEC = 30


SUMMARY_SQL = """SELECT
 (SELECT COUNT(DISTINCT visitor) FROM hits WHERE day=?1 AND kind='visit'),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE day=?1 AND kind IN ('check','sample')),
 (SELECT COUNT(DISTINCT visitor) FROM hits WHERE day>=?2 AND kind='visit'),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE day>=?2 AND kind IN ('check','sample')),
 (SELECT COUNT(*) FROM (SELECT visitor, SUM(n) s FROM hits WHERE day>=?2
    AND kind IN ('check','sample') GROUP BY visitor HAVING s >= 2)),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE kind='visit'),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE kind='check'),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE kind='sample'),
 (SELECT COUNT(DISTINCT day) FROM hits),
 (SELECT COALESCE(MIN(day),?1) FROM hits),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE day>=?2 AND kind='recheck'),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE kind='recheck'),
 (SELECT COALESCE(SUM(n),0) FROM hits WHERE kind='done'),
 (SELECT COUNT(DISTINCT visitor) FROM hits WHERE day>=?2 AND kind IN ('check','sample')),
 (SELECT COUNT(DISTINCT visitor) FROM hits WHERE day>=?2 AND kind='done')"""

DAILY_SQL = ("SELECT day, COUNT(DISTINCT CASE WHEN kind='visit' THEN visitor END) v, "
             "SUM(CASE WHEN kind IN ('check','sample') THEN n ELSE 0 END) c "
             "FROM hits WHERE day>=?1 GROUP BY day ORDER BY day")


# 주 단위 기록 — 북극성 지표(주간 재검사 사용자)를 주마다 남긴다.
# 방문자 값은 주가 바뀌면 달라지므로 주 안에서만 사람을 셀 수 있다. 그래서 주가 단위다.
MONDAY = "date(day, '-' || ((CAST(strftime('%w', day) AS INTEGER) + 6) % 7) || ' days')"

WEEKLY_SQL = f"""SELECT {MONDAY} AS wk,
 COUNT(DISTINCT CASE WHEN kind='visit' THEN visitor END) v,
 COUNT(DISTINCT CASE WHEN kind='pick' THEN visitor END) p,
 COUNT(DISTINCT CASE WHEN kind IN ('check','sample') THEN visitor END) c,
 COUNT(DISTINCT CASE WHEN kind='done' THEN visitor END) f
 FROM hits GROUP BY wk ORDER BY wk DESC LIMIT {{n}}"""

WEEKLY_AGAIN_SQL = f"""SELECT wk, COUNT(*) AS r FROM (
 SELECT {MONDAY} AS wk, visitor, SUM(n) s FROM hits WHERE kind IN ('check','sample')
 GROUP BY wk, visitor HAVING s >= 2) GROUP BY wk"""


RETENTION_SQL = f"""SELECT kind, {MONDAY} AS wk, COUNT(DISTINCT visitor) AS n
 FROM hits WHERE kind = 'new' OR kind LIKE 'ret:%' GROUP BY kind, wk"""


def _retention(rows, limit=6):
    """처음 온 주(`new`)를 분모로, 그 뒤 주마다 다시 온 사람(`ret:그주`)을 분자로 놓는다."""
    size, back = {}, {}
    for kind, wk, n in rows:
        if kind == "new":
            size[wk] = n or 0
        else:
            back.setdefault(kind[4:], {})[wk] = n or 0
    out = []
    for first in sorted(size, reverse=True)[:limit]:
        n0 = size[first]
        out.append({"cohort": first, "size": n0, "weeks": [
            {"since": wk, "back": n, "rate": round(n / n0, 3) if n0 else 0.0}
            for wk, n in sorted(back.get(first, {}).items())]})
    return out


def retention(con=None, limit=6):
    """리텐션 커브. 처음 온 주가 같은 사람들을 묶어 그 뒤 주마다 몇 명이 돌아왔나 본다.
    쿠키를 지우거나 다른 기기로 오면 새로 온 사람으로 세므로 실제보다 낮게 나온다."""
    if d1_conf():
        rows = [(r["kind"], r["wk"], r["n"]) for r in _d1(RETENTION_SQL)[0]]
    else:
        rows = con.execute(RETENTION_SQL).fetchall()
    return _retention(rows, limit)


def _weeks(rows, again):
    # pickers = 파일 선택창을 연 사람. 방문과 검사 사이가 제일 크게 빠지는 칸이라,
    # 안 누른 것과 누르고 그만둔 것을 갈라 보려고 2026-09-25 에 넣었다.
    return [{"since": r[0], "visitors": r[1] or 0, "pickers": r[2] or 0,
             "checkers": r[3] or 0, "finishers": r[4] or 0,
             "recheckers": again.get(r[0], 0)} for r in rows]


def weekly(con=None, limit=6):
    """최근 몇 주를 한 줄씩. 화면과 제출본이 같은 값을 보게 여기서 한 번만 센다."""
    if d1_conf():
        rows = _d1(WEEKLY_SQL.format(n=int(limit)))[0]
        again = {r["wk"]: r["r"] for r in _d1(WEEKLY_AGAIN_SQL)[0]}
        return _weeks([(r["wk"], r["v"], r["p"], r["c"], r["f"]) for r in rows], again)
    rows = con.execute(WEEKLY_SQL.format(n=int(limit))).fetchall()
    again = dict(con.execute(WEEKLY_AGAIN_SQL).fetchall())
    return _weeks(rows, again)


def _summary_d1(today, days):
    monday = today - datetime.timedelta(days=today.weekday())
    first = (today - datetime.timedelta(days=days - 1)).isoformat()
    row = _d1(SUMMARY_SQL, (today.isoformat(), monday.isoformat()))[0][0]
    (tv, tc, wv, wc, wr, vis, chk, smp, nday, since,
     wrc, rc, dn, wdo, wfin) = list(row.values())
    daily = _d1(DAILY_SQL, (first,))[0]
    return {
        "available": True, "store": "d1",
        "today": {"visitors": tv or 0, "checks": tc or 0},
        "week": {"since": monday.isoformat(), "visitors": wv or 0,
                 "checks": wc or 0, "recheckers": wr or 0,
                 "rechecks": wrc or 0,
                 # 사람 단위 — 횟수가 아니라 몇 명이 했나. 방문 → 검사 → 결과 순서다.
                 "checkers": wdo or 0, "finishers": wfin or 0},
        "total": {"visits": vis or 0, "checks": chk or 0, "samples": smp or 0,
                  "rechecks": rc or 0, "done": dn or 0,
                  "days": nday or 0, "since": since or today.isoformat()},
        "daily": [{"day": r["day"], "visitors": r["v"] or 0, "checks": r["c"] or 0}
                  for r in daily],
        "weeks": weekly(),
        "retention": retention(),
    }


def summary(today=None, days=14):
    today = today or datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    if d1_conf():
        if _cache[1] and time.time() - _cache[0] < CACHE_SEC:
            return _cache[1]
        try:
            out = _summary_d1(today, days)
            _cache[0], _cache[1] = time.time(), out
            return out
        except Exception as e:                                # noqa: BLE001
            print(f"[stats] D1 조회 실패: {type(e).__name__}: {e}", flush=True)
            return {"available": False}
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
            "available": True, "store": "sqlite",
            "missing_env": missing_conf(),
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
                # 화면이 '지난번과 비교'를 실제로 띄운 횟수
                "rechecks": one("SELECT SUM(n) FROM hits WHERE day>=? "
                                "AND kind='recheck'", (week,)),
                # 사람 단위 — 방문한 사람 중 몇 명이 검사를 시작했고 몇 명이 결과까지 갔나.
                # 횟수(checks)는 한 사람이 여러 번 올리면 여러 번으로 세어 전환율이 될 수 없다.
                "checkers": one(f"SELECT COUNT(DISTINCT visitor) FROM hits "
                                f"WHERE day>=? AND kind IN ({marks})", (week, *CHECK_KINDS)),
                "finishers": one("SELECT COUNT(DISTINCT visitor) FROM hits "
                                 "WHERE day>=? AND kind='done'", (week,)),
            },
            "total": {
                "visits": one("SELECT SUM(n) FROM hits WHERE kind='visit'"),
                "checks": one("SELECT SUM(n) FROM hits WHERE kind='check'"),
                "samples": one("SELECT SUM(n) FROM hits WHERE kind='sample'"),
                "rechecks": one("SELECT SUM(n) FROM hits WHERE kind='recheck'"),
                "done": one("SELECT SUM(n) FROM hits WHERE kind='done'"),
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
        out["weeks"] = weekly(con)
        out["retention"] = retention(con)
    con.close()
    return out
