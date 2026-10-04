// 시연 영상의 콘티 — 찍는 쪽(capture.js)과 그리는 쪽(compose.html)이 같은 값을 쓴다.
// 좌표는 앱 화면(1600×900 CSS px) 기준. 시간은 영상 초.
(function (root) {
  const FPS = 60;
  const T = {
    enter: 0.55, dragArrive: 2.85, drop: 3.25,       // 파일을 끌어 와 놓는다
    busyEnd: 4.70, resIn: 5.00,                      // 검사 중 → 결과 (빨리 감기)
    travel1: [6.90, 7.95], chipClick: 8.30,          // 번호로
    travel2: [10.35, 11.30], fixClick: 11.65,        // 수정 예시
    away: [12.25, 12.85], fadeOut: [12.90, 13.30],
    end: 23.0,
  };

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

  const api = { FPS, T, ease, cursorAt, buildSegs };
  if (typeof module === 'object' && module.exports) module.exports = api; else root.STORY = api;
})(this);
