-- 답변 한 건 = answers 한 줄.
-- 고른 것은 picks 로 펼쳐서 넣는다. 그래야 1000건이 쌓여도 통계가 GROUP BY 한 번이다.
-- 직접 적은 것은 세지 않으므로 notes 에 따로 둔다.

CREATE TABLE IF NOT EXISTS answers (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  at   TEXT NOT NULL,            -- ISO 8601 (UTC)
  data TEXT NOT NULL             -- 받은 그대로의 JSON. 한 사람씩 볼 때만 읽는다
);

CREATE TABLE IF NOT EXISTS picks (
  answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
  field     TEXT NOT NULL,
  value     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
  answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
  field     TEXT NOT NULL,
  text      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS picks_field  ON picks(field, value);
CREATE INDEX IF NOT EXISTS picks_answer ON picks(answer_id);
CREATE INDEX IF NOT EXISTS notes_field  ON notes(field);
CREATE INDEX IF NOT EXISTS answers_at   ON answers(at DESC);
