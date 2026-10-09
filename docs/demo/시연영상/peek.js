// 첫 화면 '이렇게 나와요' 그림(static/peek.webp)을 실제 결과 화면에서 만든다 — 10-10 계획 1번 · 점검표 W6 FIX 01.
// 예제 sample_body.dxf(팀이 만든 도면, ../영상시연/1차/본체.dxf 와 같은 파일)를 검사하고 수정 예시를 켠 뒤 번호 1로
// 확대한 화면에서, 도면 칸(번호 · 초록 수정 예시)과 실격 카드가 같이 들어오게 자른다.
// 손대는 것은 stills.py 와 같은 셋 — 자르기, 도면 칸의 가는 선 굵히기, 번호와 수정 예시에 파란 테두리. 화면 속 글자나 판정은 그대로.
//   로컬 서버를 README 1번처럼 띄운 뒤 이 폴더에서: node peek.js
// 결과 화면이 바뀌면(예제 판정 · 화면 배치) 다시 찍는다 — 그림과 실제 결과가 다르면 처음 온 사람이 속았다고 느낀다.
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright-core');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const APP = 'http://127.0.0.1:8010/';
const OUT = path.join(__dirname, '..', '..', '..', 'static', 'peek.webp');
const K = 3;                                                    // 찍는 배율
const VIEW = { width: 1200, height: 760 };                      // 이 창 크기에서 잰 자리들이다
const CLIP = { x: 24, y: 158, width: 1152, height: 384 };       // 도면 칸 위쪽 + 실격 카드
const RINGS = [{ circle: [483, 290, 64] },                      // 번호 1
               { box: [119, 468, 299, 525] }];                  // 초록 Ø20.5
const ACCENT = 'rgb(42,120,214)';                               // stills.py 와 같은 강조색
const WIDTH = 960;                                              // 첫 화면에서 최대 424px 로 보인다 — 2배 남짓

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true,
    args: ['--hide-scrollbars', '--force-color-profile=srgb'] });
  const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: K, locale: 'ko-KR',
    colorScheme: 'light', reducedMotion: 'reduce' });
  await ctx.addInitScript(() => {
    try { localStorage.clear(); localStorage.setItem('cadcheck.intro', '1');
          localStorage.setItem('cadcheck.lang', 'ko'); localStorage.setItem('cadcheck.theme', 'light'); } catch (e) {}
  });
  // 늦게 오는 AI 답변·번역은 지적 목록을 다시 그려 화면이 바뀐다 — 찍는 동안은 오지 않게 붙잡는다
  await ctx.route('**/api/ai-extra/**', () => {});
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.error('pageerror', e.message));
  await page.goto(APP, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.click('#sgrid .scard[data-n="sample_body.dxf"]');
  await page.waitForSelector('#res:not([hidden])');
  await page.waitForTimeout(2500);
  await page.click('#fixBtn');
  await page.click('#finds .mchip[data-n="1"]');
  // 번호 칩을 누르려고 창이 아래로 굴렀다 — 실격 카드가 보이게 맨 위로 되돌린다(도면 칸은 확대된 그대로)
  await page.evaluate(() => window.scrollTo(0, 0));
  // 도면을 30px 위로 끌어 번호와 수정 예시가 실격 카드와 같은 높이에 들어오게 한다(사람이 끌어 옮기는 것과 같다)
  await page.evaluate(() => { oy -= 30; apply(); });
  await page.waitForTimeout(800);
  await page.mouse.move(VIEW.width - 2, VIEW.height - 2);
  const zoom = await page.textContent('#zoomv');
  const stage = await page.evaluate(() => { const b = document.querySelector('#stage').getBoundingClientRect();
    return [b.left, b.top, b.right, b.bottom]; });
  const shot = (await page.screenshot({ clip: CLIP })).toString('base64');

  const blank = await ctx.newPage();
  const url = await blank.evaluate(async ({ shot, K, CLIP, stage, RINGS, ACCENT, WIDTH }) => {
    const img = new Image(); img.src = 'data:image/png;base64,' + shot; await img.decode();
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
    const g = c.getContext('2d'); g.drawImage(img, 0, 0);
    const at = (x, y) => [(x - CLIP.x) * K, (y - CLIP.y) * K];
    // 도면 칸 안에서만 밝은 선을 2px 씩 넓힌다(5×5 최댓값). 줄였을 때 가는 선이 사라지지 않게
    const [sx, sy] = at(stage[0], stage[1]);
    g.save(); g.beginPath(); g.rect(sx, sy, (stage[2] - stage[0]) * K, (stage[3] - stage[1]) * K); g.clip();
    g.globalCompositeOperation = 'lighten';
    for (let dx = -2; dx <= 2; dx++) for (let dy = -2; dy <= 2; dy++) if (dx || dy) g.drawImage(img, dx, dy);
    g.restore();
    g.strokeStyle = ACCENT; g.lineWidth = 4 * K;
    for (const r of RINGS) {
      g.beginPath();
      if (r.circle) { const [x, y] = at(r.circle[0], r.circle[1]); g.arc(x, y, r.circle[2] * K, 0, Math.PI * 2); }
      else { const [x0, y0] = at(r.box[0], r.box[1]); g.roundRect(x0, y0, (r.box[2] - r.box[0]) * K, (r.box[3] - r.box[1]) * K, 16 * K); }
      g.stroke();
    }
    // 반씩 줄여 가며 작게 — 한 번에 1/3 넘게 줄이면 글자가 깨진다
    let src = c;
    while (src.width / 2 >= WIDTH) {
      const h = document.createElement('canvas'); h.width = Math.round(src.width / 2); h.height = Math.round(src.height / 2);
      const hg = h.getContext('2d'); hg.imageSmoothingQuality = 'high'; hg.drawImage(src, 0, 0, h.width, h.height); src = h;
    }
    const o = document.createElement('canvas'); o.width = WIDTH; o.height = Math.round(src.height * WIDTH / src.width);
    const og = o.getContext('2d'); og.imageSmoothingQuality = 'high'; og.drawImage(src, 0, 0, o.width, o.height);
    return o.toDataURL('image/webp', 0.82);
  }, { shot, K, CLIP, stage, RINGS, ACCENT, WIDTH });
  const buf = Buffer.from(url.split(',')[1], 'base64');
  fs.writeFileSync(OUT, buf);
  console.log(`static/peek.webp ${WIDTH}px · ${(buf.length / 1024).toFixed(1)}KB · 확대 ${zoom} · 도면 칸 ${stage.map(Math.round)}`);
  await browser.close();
})();
