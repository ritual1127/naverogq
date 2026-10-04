// 시연 영상의 콘티 — 찍는 쪽(capture.js) · 그리는 쪽(compose.html) · 소리를 섞는 쪽(render.js)이 같은 값을 쓴다.
// 좌표는 앱 화면(1600×900 CSS px) 기준. 시간은 영상 초.
// 그림은 목소리에 맞춘다 — 각 대사의 낱말 시각(Whisper 로 잰 값, voice/words.json)으로 누르는 순간을 정했다.
(function (root) {
  const FPS = 60;

  // 대사 — 부분마다 그 사람 목소리(AI 합성 · 그 사람 녹음의 말투와 말 빠르기에 맞춤). 파일은 voice/, 길이는 초.
  // 놓이는 시각은 앞 대사가 끝나고 쉬는 만큼 — 같은 사람의 문장 사이 0.55초, 사람이 바뀔 때 0.45~0.5초
  const VOICE = [];
  const put = (id, who, gap, dur, say) => {
    const prev = VOICE[VOICE.length - 1];
    VOICE.push({ id, who, t: prev ? +(prev.t + prev.dur + gap).toFixed(3) : gap, dur, say });
  };
  put("v1", "안대열", 1.00, 3.31, "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다.");
  const resIn = 5.10;                                         // 결과 화면이 다 뜬 뒤에 장우영
  put("v2", "장우영", resIn + 0.05 - (1.00 + 3.31), 5.17, "그러면 실격 사유는 오른쪽에, 빠뜨린 치수 자리는 도면 위에 번호로 표시합니다.");
  put("v3", "박지완", 0.48, 4.03, "번호를 누르면, 그 자리를 바로 확대해서 보여 줍니다.");
  put("v4a", "김승준", 0.48, 3.55, "지난 데모데이 이후에 새로 만든 기능, 수정 예시입니다.");
  put("v4b", "김승준", 0.55, 4.27, "누르면, 빠진 치수를 도면에서 읽은 좌표 그대로 초록색으로 그려 줍니다.");
  put("v4c", "김승준", 0.55, 3.71, "AI가 그림을 지어내는 게 아니라서, 위치와 값이 정확합니다.");
  const at = (id) => VOICE.find((v) => v.id === id);
  const end = (id) => at(id).t + at(id).dur;

  // 누르는 순간 = 낱말이 끝나는 시각(voice/report.json 의 낱말 시각 · 꼬리는 voice/tail.py 로 자름)
  const T = {
    enter: 0.55,                                     // 커서와 파일이 들어온다 (목소리는 1초부터 — 첫 화면을 1초 보여 준다)
    drop: at("v1").t + 2.38,                         // "놓기만"
    busyEnd: resIn - 0.30, resIn,                    // 검사 중 → 결과 (빨리 감기)
    chipClick: at("v3").t + 1.20,                    // "번호를 누르면"
    fixClick: at("v4b").t + 0.46,                    // "누르면" — 초록은 "빠진 치수를" 과 같이 뜬다
  };
  T.dragArrive = T.drop - 0.42;
  T.travel1 = [T.chipClick - 1.35, T.chipClick - 0.30];    // 장우영 대사가 끝나자 번호로 간다
  T.travel2 = [at("v4a").t + 1.45, at("v4a").t + 2.45];    // "수정 예시" 라고 할 때 그 단추 위에 있다
  T.away = [T.fixClick + 0.60, T.fixClick + 1.20];
  T.fadeOut = [T.fixClick + 1.25, T.fixClick + 1.65];
  T.valuePush = at("v4c").t + 2.00;                // "위치와 값이" — 초록 치수 값으로 다가간다
  T.valuePushDur = 1.8;
  T.pullBack = end("v4c") + 0.60;
  T.end = T.pullBack + 3.8;

  // 화면 아래 자막 — 목소리와 같이 뜨고 진다
  const CAPS = [
    { n: 1, who: "안대열", t0: at("v1").t - 0.15, t1: end("v1") + 0.35, m: "도면 파일을 끌어다 놓으면" },
    { n: 2, who: "장우영", t0: at("v2").t - 0.15, t1: end("v2") + 0.30, m: "실격 사유는 오른쪽에", s: "빠뜨린 치수는 도면 위에 번호로" },
    { n: 3, who: "박지완", t0: at("v3").t - 0.15, t1: end("v3") + 0.30, m: "번호를 누르면 그 자리로", s: "바로 확대해서 보여 줍니다" },
    { n: 4, who: "김승준", t0: at("v4a").t - 0.15, t1: end("v4c") + 0.40, m: "수정 예시 — W4 이후 새 기능", s: "누르면 빠진 치수를 도면 좌표 그대로 초록으로" },
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
