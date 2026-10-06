// 발표 둘이 같이 쓰는 것 — 장 종류, 그래프 종류, 장마다 목표 시간. 발표 내용은 talk10.js(10분판)와
// talk5.js(데모데이 ② 5분판 — 10분판의 장을 가져와 줄인 것)에 있다. 10-06 전의 5분판은 git 기록에 있다.
// 고친 뒤에는 node --test presenter/*.test.mjs 로 오타 · 시간 초과를 잡는다.

export const KINDS = ["cover", "compare", "big", "video", "flow", "ask", "quote", "cards"];
export const CHARTS = ["hbar", "stack", "column", "timeline"];

// 영상이 스스로 말하는 장의 읽는 사람 — 대본 탭에 회색으로 보이고, 아무도 소리 내어 읽지 않는다
export const VOICE = "영상";

// W4 원고에서 잰 읽는 속도 — 1초에 4.5자(띄어쓰기 포함). pace 에 사람마다 다른 값을 주면 그 값(10분판).
// 영상 장은 영상 길이와 그 위에 사람이 하는 말 중 긴 쪽.
const CHARS_PER_SEC = 4.5;
export const targetSeconds = (slide, pace = {}) => Math.round(Math.max(slide.view?.seconds || 0,
  slide.lines.filter((l) => l.who !== VOICE).reduce((n, l) => n + l.say.length / (pace[l.who] || CHARS_PER_SEC), 0)));
