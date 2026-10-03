// 발표 도우미의 상태 계산. 화면도 네트워크도 모르는 순수 함수라 node 로 시험한다.
// 모든 기기가 같은 규칙으로 판정해야 같은 장에 모인다.

export const initial = (by) => ({ slide: 0, startedAt: null, seq: 0, by });

// 다음 · 이전 장. 범위를 넘으면 그대로 돌려준다 — 순번이 안 올라 다른 기기를 흔들지 않는다.
export function step(state, delta, count, by) {
  const slide = Math.max(0, Math.min(count - 1, state.slide + delta));
  return slide === state.slide ? state : { ...state, slide, seq: state.seq + 1, by };
}

export const setTimer = (state, startedAt, by) => ({ ...state, startedAt, seq: state.seq + 1, by });

// 시계가 아니라 순번으로 정한다. 같으면 기기 ID 가 큰 쪽 — 어느 기기에서 판정해도 답이 같다.
export const newer = (a, b) => a.seq > b.seq || (a.seq === b.seq && a.by > b.by);

// 타이머는 "시작한 지 몇 ms" 로 보낸다. 받는 쪽이 자기 시계에서 빼므로 기기마다 시계가 달라도 된다.
export const toWire = (s, now) => ({
  slide: s.slide, seq: s.seq, by: s.by,
  elapsed: s.startedAt === null ? null : now - s.startedAt,
});

// 채널로 온 값은 남의 기기가 보낸 것이다. 모양이 틀리면 버린다.
export function receive(state, w, now) {
  const ok = w && Number.isInteger(w.slide) && Number.isInteger(w.seq) && typeof w.by === "string"
    && (w.elapsed === null || Number.isFinite(w.elapsed));
  if (!ok) return state;
  const s = { slide: w.slide, seq: w.seq, by: w.by, startedAt: w.elapsed === null ? null : now - w.elapsed };
  return newer(s, state) ? s : state;
}
