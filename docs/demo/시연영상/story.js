// 시연 영상의 콘티 — 찍는 쪽(capture.js) · 그리는 쪽(compose.html) · 소리를 섞는 쪽(render.js)이 같은 값을 쓴다.
// 좌표는 앱 화면(1600×900 CSS px) 기준. 시간은 영상 초.
// 그림은 목소리에 맞춘다 — 각 대사의 낱말 시각(Whisper 로 잰 값, voice/words.json)으로 누르는 순간을 정했다.
(function (root) {
  const FPS = 60;

  // 대사 — 부분마다 그 사람 목소리(AI 합성). 파일은 voice/, 길이는 초
  const VOICE = [
    { id: "p1", who: "안대열", t: 1.00, dur: 3.008, say: "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다." },
    { id: "p2", who: "장우영", t: 4.90, dur: 4.242, say: "그러면 실격 사유와 빠뜨린 치수 자리가, 도면 위에 번호로 나옵니다." },
    { id: "p3", who: "박지완", t: 9.54, dur: 3.207, say: "번호를 누르면, 그 자리로 바로 갑니다." },
    { id: "p4a", who: "김승준", t: 13.15, dur: 7.818, say: "그리고 지난 데모데이 이후 새로 만든 수정 예시는, 빠진 치수를 도면 좌표 그대로 초록색으로 그려 줍니다." },
    { id: "p4b", who: "김승준", t: 21.27, dur: 4.715, say: "그림을 지어내는 AI가 아니라서, 위치와 값이 정확합니다." },
  ];
  const at = (id) => VOICE.find((v) => v.id === id);
  const end = (id) => at(id).t + at(id).dur;

  const T = {
    enter: 0.55,                                     // 커서와 파일이 들어온다 (목소리는 1초부터 — 첫 화면을 1초 보여 준다)
    dragArrive: 2.70,
    drop: 3.12,                                      // "놓기만" 이 끝나는 순간 (1.00 + 2.14)
    busyEnd: 4.55, resIn: 4.85,                      // 검사 중 → 결과 (빨리 감기)
    chipClick: 10.49,                                // "누르면" 이 끝나는 순간 (9.54 + 0.98)
    fixClick: 16.30,                                 // "예시는" 이 끝나는 순간 (13.15 + 3.22) — 초록은 "빠진 치수를" 과 같이 뜬다
  };
  T.travel1 = [T.chipClick - 1.35, T.chipClick - 0.30];    // "그러면 … 나옵니다" 가 끝나자 번호로 간다
  T.travel2 = [T.fixClick - 1.30, T.fixClick - 0.35];
  T.away = [T.fixClick + 0.60, T.fixClick + 1.20];
  T.fadeOut = [T.fixClick + 1.25, T.fixClick + 1.65];
  T.valuePush = at("p4b").t + 0.10;                // "위치와 값이" — 초록 치수 값으로 다가간다
  T.pullBack = end("p4b") + 0.25;
  T.end = T.pullBack + 3.8;

  // 화면 아래 자막 — 목소리와 같이 뜨고 진다
  const CAPS = [
    { n: 1, who: "안대열", t0: at("p1").t - 0.15, t1: end("p1") + 0.35, m: "도면 파일을 끌어다 놓으면" },
    { n: 2, who: "장우영", t0: at("p2").t - 0.15, t1: end("p2") + 0.30, m: "실격 사유와 빠뜨린 치수 자리", s: "도면 위에 번호로 찍어 줍니다" },
    { n: 3, who: "박지완", t0: at("p3").t - 0.15, t1: end("p3") + 0.30, m: "번호를 누르면 그 자리로" },
    { n: 4, who: "김승준", t0: at("p4a").t - 0.15, t1: end("p4b") + 0.40, m: "수정 예시 — W4 이후 새 기능", s: "도면에서 읽은 좌표 그대로, 빠진 치수를 초록으로" },
  ];

  // 사람 손처럼 — 앞쪽이 빠르고 끝에서 천천히 멈추는 곡선, 살짝 휜 길
  const mj = (x) => x * x * x * (10 - 15 * x + 6 * x * x);
  const ease = (u) => mj(Math.pow(Math.min(1, Math.max(0, u)), 0.82));

  function segPos(s, t) {
    const u = (t - s.t0) / (s.t1 - s.t0), e = ease(u);
    const dx = s.to.x - s.from.x, dy = s.to.y - s.from.y, d = Math.hypot(dx, dy) || 1;
    const off = (s.arc || 0) * d * Math.sin(Math.PI * e);
    return { x: s.from.x + dx * e - (dy / d) * off, y: s.from.y + dy * e + (dx / d) * off };
  }

  // segs: [{t0,t1,from,to,arc}] 시간순. 구간 사이는 앞 구간의 끝에 멈춰 있다.
  function cursorAt(segs, t) {
    if (t <= segs[0].t0) return { ...segs[0].from };
    for (let i = 0; i < segs.length; i++) {
      const s = segs[i];
      if (t < s.t1) return t >= s.t0 ? segPos(s, t) : { ...segs[i - 1].to };
    }
    return { ...segs[segs.length - 1].to };
  }

  function buildSegs(p) {   // p: 측정한 목표 지점들
    return [
      { t0: T.enter, t1: T.dragArrive, from: { x: 1915, y: 640 }, to: p.drop, arc: 0.07 },
      { t0: T.travel1[0], t1: T.travel1[1], from: p.drop, to: p.chip, arc: -0.06 },
      { t0: T.travel2[0], t1: T.travel2[1], from: p.chip, to: p.fix, arc: 0.07 },
      { t0: T.away[0], t1: T.away[1], from: p.fix, to: p.rest, arc: 0.05 },
    ];
  }

  const api = { FPS, T, VOICE, CAPS, ease, cursorAt, buildSegs };
  if (typeof module === 'object' && module.exports) module.exports = api; else root.STORY = api;
})(this);
