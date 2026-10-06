// node --test presenter/*.test.mjs   — 대본 파일을 고치다 생긴 실수를 발표 전에 잡는다. 5분판 · 10분판 둘 다.
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { TALK as TALK5, KINDS, CHARTS, VOICE, targetSeconds } from "./talk.js";
import { TALK as TALK10 } from "./talk10.js";

const NEEDS = {
  cover: ["headline"], compare: ["head", "rows"], big: ["value"],
  video: ["src"], flow: ["steps"], ask: ["question"], quote: ["quote", "by"], cards: ["cards"],
};
const exists = (f) => f && existsSync(new URL(f, import.meta.url));

for (const [name, TALK] of [["5분판", TALK5], ["10분판", TALK10]]) {
  test(`${name} is well formed`, () => {
    assert.ok(TALK.slides.length > 0);
    for (const [i, s] of TALK.slides.entries()) {
      const at = `${name} ${i + 1}장`;
      assert.ok(s.title, `${at} 제목`);
      assert.ok(KINDS.includes(s.view.kind), `${at} 슬라이드 종류 ${s.view.kind}`);
      for (const key of NEEDS[s.view.kind]) assert.ok(s.view[key], `${at} ${key}`);
      assert.ok(s.lines.length > 0, `${at} 대사가 없다`);
      for (const line of s.lines) {
        const ok = TALK.people.includes(line.who) || (s.view.kind === "video" && line.who === VOICE);
        assert.ok(ok, `${at} 읽는 사람 '${line.who}' 가 people 에 없다(영상 장만 '${VOICE}')`);
        assert.ok(line.say.trim(), `${at} 빈 대사`);
      }
      const v = s.view;
      if (v.kind === "big") assert.ok(v.caption || v.chart || v.points, `${at} 설명 · 그래프 · 요점 중 하나는 있어야 한다`);
      if (v.img) assert.ok(exists(v.img), `${at} 그림 파일이 없다: ${v.img}`);
      if (v.chart) checkChart(v, at);
      if (v.kind === "flow") assert.ok(v.steps.length >= 2 && v.steps.every((st) => st.n && st.label), `${at} 단계`);
      if (v.kind === "compare") {
        for (const row of v.rows) assert.equal(row.length, v.head.length, `${at} 표 칸 수`);
      }
      if (v.kind === "cards") assert.ok(v.cards.length >= 2 && v.cards.every((c) => c.title && c.body), `${at} 카드`);
      if (v.kind === "video") {
        for (const f of [v.src, v.poster]) assert.ok(exists(f), `${at} 영상 파일이 없다: ${f}`);
        assert.ok(v.seconds > 0, `${at} 영상 길이`);
      }
    }
  });

  test(`${name} fits the time limit`, () => {
    const total = TALK.slides.reduce((n, s) => n + targetSeconds(s, TALK.pace), 0);
    assert.ok(total <= TALK.limit, `대사만 ${total}초 — ${TALK.limit}초를 넘는다`);
  });
}

test("the 10-minute talk leaves room to breathe", () => {
  // 장을 넘기는 데 장마다 1초 — 그것까지 넣어도 10분 안
  const total = TALK10.slides.reduce((n, s) => n + targetSeconds(s, TALK10.pace) + 1, 0);
  assert.ok(total <= 600, `장 넘기기까지 ${total}초`);
  assert.ok(total >= 540, `${total}초 — 10분을 꽉 채우기로 했다`);
});

// 그래프 — 강조형이라 강조하는 막대는 꼭 하나. 큰 숫자와 그래프가 서로 다른 말을 하면 안 된다.
function checkChart(v, at) {
  const c = v.chart;
  assert.ok(CHARTS.includes(c.type), `${at} 그래프 종류 ${c.type}`);
  assert.ok(c.unit, `${at} 그래프 단위`);
  const marks = { hbar: c.rows, stack: c.parts, column: c.cols, timeline: c.rows }[c.type];
  assert.ok(marks.length >= (c.type === "timeline" ? 1 : 2), `${at} 그래프 막대 수`);
  for (const m of marks) {
    assert.ok(m.label, `${at} 그래프 이름표`);
    if (c.type === "timeline") {
      assert.ok(m.after || (m.at >= 0 && m.at + m.fix <= c.span), `${at} 시험 시간 밖 ${m.label}`);
      assert.ok(m.fix > 0, `${at} 고친 시간 ${m.label}`);
    } else assert.ok(Number.isFinite(m.value) && m.value >= 0, `${at} 그래프 값 ${m.value}`);
  }
  assert.equal(marks.filter((m) => m.focus).length, 1, `${at} 강조 막대는 하나`);
  if (c.type === "stack" && v.value) {
    const total = marks.reduce((n, m) => n + m.value, 0).toLocaleString("en-US");
    assert.ok(v.value.includes(total), `${at} 큰 숫자에 합계 ${total} 이 없다`);
  }
  if (c.type === "column" && c.target) {
    assert.ok(c.target.value > 0 && c.target.label, `${at} 목표선`);
    assert.ok(v.value.includes(String(c.target.value)), `${at} 큰 숫자에 목표 ${c.target.value} 가 없다`);
    assert.ok(v.value.includes(String(Math.max(...marks.map((m) => m.value)))), `${at} 큰 숫자에 최고값이 없다`);
  }
}

test("target seconds come from the length of the lines", () => {
  const s = { lines: [{ who: "a", say: "가".repeat(45) }] };
  assert.equal(targetSeconds(s), 10);
  assert.equal(targetSeconds({ ...s, view: { seconds: 30 } }), 30, "영상 장은 영상 길이");
  assert.equal(targetSeconds({ ...s, view: { seconds: 5 } }), 10, "영상보다 말이 길면 말 길이");
  assert.equal(targetSeconds(s, { a: 9 }), 5, "사람마다 빠르기");
  assert.equal(targetSeconds({ lines: [{ who: VOICE, say: "가".repeat(90) }], view: { seconds: 7 } }), 7, "영상 목소리는 세지 않는다");
});
