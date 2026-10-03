// node --test presenter/*.test.mjs   — 대본 파일을 고치다 생긴 실수를 발표 전에 잡는다.
import test from "node:test";
import assert from "node:assert/strict";
import { TALK, KINDS, targetSeconds } from "./talk.js";

const NEEDS = { cover: ["headline"], big: ["value", "caption"], flow: ["steps"], ask: ["question"] };

test("talk is well formed", () => {
  assert.ok(TALK.slides.length > 0);
  for (const [i, s] of TALK.slides.entries()) {
    const at = `${i + 1}장`;
    assert.ok(s.title, `${at} 제목`);
    assert.ok(KINDS.includes(s.view.kind), `${at} 슬라이드 종류 ${s.view.kind}`);
    for (const key of NEEDS[s.view.kind]) assert.ok(s.view[key], `${at} ${key}`);
    assert.ok(s.lines.length > 0, `${at} 대사가 없다`);
    for (const line of s.lines) {
      assert.ok(TALK.people.includes(line.who), `${at} 읽는 사람 '${line.who}' 가 people 에 없다`);
      assert.ok(line.say.trim(), `${at} 빈 대사`);
    }
  }
  if (TALK.slides.some((s) => s.view.kind === "flow")) {
    for (const s of TALK.slides.filter((x) => x.view.kind === "flow")) {
      assert.ok(s.view.steps.length >= 2 && s.view.steps.every((st) => st.n && st.label));
    }
  }
});

test("talk fits the time limit", () => {
  const total = TALK.slides.reduce((n, s) => n + targetSeconds(s), 0);
  assert.ok(total <= TALK.limit, `대사만 ${total}초 — ${TALK.limit}초를 넘는다`);
});

test("target seconds come from the length of the lines", () => {
  const s = { lines: [{ who: "a", say: "가".repeat(45) }] };
  assert.equal(targetSeconds(s), 10);
});
