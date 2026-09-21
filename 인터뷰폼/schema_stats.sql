-- 사이트 접속 수와 도면 검사 횟수. 인터뷰 답과 같은 D1 에 두되 표는 따로다.
-- 남기는 것은 네 칸뿐 — 날짜 · 방문자 값 · 종류 · 횟수.
-- 방문자 값은 `서버만 아는 임의 값 + 그 주 + IP` 를 해시한 16자다.
-- IP 원본은 넣지 않고, 주가 바뀌면 같은 사람이라도 값이 달라져 이어 볼 수 없다.
CREATE TABLE IF NOT EXISTS hits (
  day     TEXT NOT NULL,          -- YYYY-MM-DD
  visitor TEXT NOT NULL,          -- 해시 16자
  kind    TEXT NOT NULL,          -- visit | check | sample
  n       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, visitor, kind)
);

CREATE INDEX IF NOT EXISTS hits_day ON hits(day);

-- 사용자가 보낸 오류 신고와 문의. 같은 D1 에 두되 표는 따로다.
-- 이름 앞에 프로젝트를 붙인 이유: 이 D1 에는 인터뷰 답의 `notes` 표가 이미 있다.
-- 같은 이름으로 만들면 우리 INSERT 가 남의 표로 가서 깨진다(2026-09-21 에 겪음).
CREATE TABLE IF NOT EXISTS cadlens_notes (
  id      TEXT PRIMARY KEY,       -- 임의의 16자
  at      TEXT NOT NULL,          -- ISO 8601
  kind    TEXT NOT NULL,          -- report | ask
  text    TEXT NOT NULL,          -- 사용자가 쓴 글 (최대 2000자)
  spot    TEXT,                   -- 결과 화면에서 고른 자리 ("3. 구멍 치수 누락")
  contact TEXT,                   -- 적고 싶은 사람만
  job     TEXT,                   -- 그 검사 한 번을 가리키는 값
  file    TEXT,                   -- "도면도 같이 보내기"를 켰을 때 그 파일 이름
  shot    TEXT                    -- 도면에서 끌어 고른 부분 그림 (PNG) 파일 이름
);

CREATE INDEX IF NOT EXISTS cadlens_notes_at ON cadlens_notes(at DESC);
