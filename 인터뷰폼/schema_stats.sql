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
