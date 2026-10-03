// node --test presenter/*.test.mjs   — 기기끼리 같은 장에 모이는 규칙을 확인한다.
import test from "node:test";
import assert from "node:assert/strict";
import { initial, step, setTimer, newer, toWire, receive } from "./state.js";

test("step moves within range and bumps seq", () => {
  const s = step(initial("a"), 1, 7, "a");
  assert.deepEqual([s.slide, s.seq, s.by], [1, 1, "a"]);
});

test("edges do not move or bump seq", () => {
  const first = initial("a");
  assert.equal(step(first, -1, 7, "a"), first);
  let last = first;
  for (let i = 0; i < 6; i++) last = step(last, 1, 7, "a");
  assert.equal(last.slide, 6);
  assert.equal(step(last, 1, 7, "a"), last);
});

test("newer state wins, older is ignored", () => {
  const mine = step(step(initial("a"), 1, 7, "a"), 1, 7, "a");       // seq 2 · 장 2
  const old = toWire(step(initial("b"), 1, 7, "b"), 0);              // seq 1 · 장 1
  assert.equal(receive(mine, old, 0), mine);
  const fresh = toWire({ ...mine, slide: 4, seq: 3, by: "b" }, 0);
  assert.equal(receive(mine, fresh, 0).slide, 4);
});

test("same seq picks larger device id everywhere", () => {
  const a = step(initial("x"), 1, 7, "a");                            // seq 1 · 장 1
  const b = step(initial("x"), 2, 7, "b");                            // seq 1 · 장 2
  assert.equal(receive(a, toWire(b, 0), 0).slide, 2);
  assert.equal(receive(b, toWire(a, 0), 0).slide, 2);
  assert.equal(newer(b, a), true);
  assert.equal(newer(a, b), false);
});

test("clock skew does not matter", () => {
  // b 의 시계가 a 보다 한참 빠르다. 그래도 나중에 누른 a 가 이긴다.
  const b1 = step(initial("b"), 1, 7, "b");
  const atA = receive(initial("a"), toWire(b1, 999_999), 1);
  const a2 = step(atA, 1, 7, "a");
  assert.equal(receive(b1, toWire(a2, 1), 999_999).slide, 2);
});

test("timer travels as elapsed time, not clock time", () => {
  const started = setTimer(initial("a"), 1_000, "a");
  const wire = toWire(started, 61_000);
  assert.equal(wire.elapsed, 60_000);
  const atB = receive(initial("b"), wire, 5_000);                    // b 의 시계는 엉뚱하다
  assert.equal(5_000 - atB.startedAt, 60_000);
});

test("stopped timer stays stopped", () => {
  const s = setTimer(setTimer(initial("a"), 5, "a"), null, "a");
  assert.equal(toWire(s, 100).elapsed, null);
  assert.equal(receive(initial("b"), toWire(s, 100), 7).startedAt, null);
});

test("junk from the channel is ignored", () => {
  const s = step(initial("a"), 1, 7, "a");
  for (const junk of [null, {}, { slide: "1", seq: 9, by: "z", elapsed: null },
    { slide: 1, seq: 9.5, by: "z", elapsed: null }, { slide: 1, seq: 9, by: 3, elapsed: null },
    { slide: 1, seq: 9, by: "z", elapsed: "soon" }]) {
    assert.equal(receive(s, junk, 0), s);
  }
});
