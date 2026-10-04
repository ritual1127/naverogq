// 실제 CADLens 화면을 영상 콘티 시간에 맞춰 3배 해상도로 찍는다.
// 페이지의 CSS 애니메이션을 멈춰 두고 프레임마다 시간을 직접 맞춘다(가상 시계) — 찍는 속도와 상관없이 60fps 가 정확하다.
// 로컬 서버(통계는 임시 DB) · 스티커 그림만 공개 서버에서 받아 공개 화면과 같게. 띄우는 법은 README.md
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright-core');
const { FPS, T, cursorAt, buildSegs } = require('./story.js');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const APP = 'http://127.0.0.1:8010/';
const PUBLIC = 'https://naverogq.onrender.com';
const FILE = path.join(__dirname, '..', '영상시연', '1차', '본체.dxf');
const VW = 1600, VH = 900, DSF = 3;
const OUT = path.join(__dirname, 'cap');
const fi = (t) => Math.round(t * FPS);
const N = fi(T.end);

const VC = `window.__vc = { m: new Map(),
  adopt(v) { for (const a of document.getAnimations()) if (!this.m.has(a)) { a.pause(); this.m.set(a, v); } },
  set(t) { for (const [a, v] of this.m) { if (a.playState === 'idle') { this.m.delete(a); continue; }
                                         a.currentTime = Math.max(0, (t - v) * 1000); } } };`;

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: CHROME, headless: true,
    args: ['--hide-scrollbars', '--force-color-profile=srgb'] });
  const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: DSF,
    locale: 'ko-KR', colorScheme: 'light', reducedMotion: 'no-preference' });
  await ctx.addInitScript(() => {
    try { localStorage.clear(); localStorage.setItem('cadcheck.intro', '1');
          localStorage.setItem('cadcheck.lang', 'ko'); localStorage.setItem('cadcheck.theme', 'light'); } catch (e) {}
  });
  await ctx.route('**/api/health', async (route) => {
    const r = await route.fetch(); const j = await r.json(); j.stickers = true;
    await route.fulfill({ response: r, json: j });
  });
  await ctx.route('**/api/sticker/**', async (route) => {
    const name = route.request().url().split('/api/sticker/')[1];
    await route.fulfill({ response: await route.fetch({ url: `${PUBLIC}/api/sticker/${name}` }) });
  });
  let release; const held = new Promise((r) => { release = r; });
  let analyzeMs = 0;
  await ctx.route('**/api/analyze', async (route) => {
    const t0 = Date.now(); const r = await route.fetch(); const body = await r.body(); analyzeMs = Date.now() - t0;
    await held; await route.fulfill({ response: r, body });
  });
  // 늦게 오는 AI 답변·번역은 목록을 다시 그려 화면이 바뀐다 — 찍는 동안은 오지 않게 붙잡는다
  await ctx.route('**/api/ai-extra/**', () => {});

  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.error('pageerror', e.message));
  await page.goto(APP, { waitUntil: 'networkidle' });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(['wait', 'fail', 'error', 'pass', 'short', 'fixed'].map((n) => new Promise((r) => {
      const i = new Image(); i.onload = i.onerror = r; i.src = '/api/sticker/' + n; })));
  });
  await page.waitForTimeout(2500);
  await page.mouse.move(1595, 300);
  await page.waitForTimeout(500);
  await page.evaluate(VC);

  const rect = (sel) => page.evaluate((s) => {
    const e = document.querySelector(s); if (!e) return null;
    const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height };
  }, sel);
  const set = (t) => page.evaluate((t) => __vc.set(t), t);
  const adopt = (t) => page.evaluate((t) => __vc.adopt(t), t);
  const inside = (p, r) => p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;
  const frames = new Array(N).fill(null);
  const rects = {};
  const pts = {};
  let n = 0;
  async function shot(name, opt = {}) {
    await page.screenshot({ path: path.join(OUT, name), type: opt.png ? 'png' : 'jpeg',
      quality: opt.png ? undefined : 95, clip: opt.clip, animations: 'allow', caret: 'hide' });
    n++; if (n % 50 === 0) console.log('shots', n);
    return name;
  }

  // ---------------------------------------------------------------- 1. 첫 화면 · 끌어다 놓기
  rects.drop = await rect('#drop');
  rects.upcard = await rect('#upcard');
  const d = rects.drop;
  pts.drop = { x: Math.round(d.x + d.w * 0.5), y: Math.round(d.y + d.h * 0.4) };
  const P0 = { ...pts, chip: pts.drop, fix: pts.drop, rest: pts.drop };
  let segs = buildSegs(P0);
  const u = rects.upcard, M = 44;
  const clip = { x: Math.max(0, Math.floor(u.x - M)), y: Math.max(0, Math.floor(u.y - M)) };
  clip.width = Math.min(VW, Math.ceil(u.x + u.w + M)) - clip.x;
  clip.height = Math.min(VH, Math.ceil(u.y + u.h + M)) - clip.y;
  await adopt(0); await set(0);
  await shot('home_base.png', { png: true });
  let entered = null;
  for (let f = 0; f < fi(T.drop); f++) {
    const t = f / FPS;
    if (entered === null && inside(cursorAt(segs, t), d)) {
      entered = t;
      await page.evaluate((t) => {
        const el = document.querySelector('#drop');
        for (const k of ['dragenter', 'dragover'])
          el.dispatchEvent(new DragEvent(k, { bubbles: true, cancelable: true, dataTransfer: new DataTransfer() }));
        __vc.adopt(t);
      }, t);
    }
    await set(t);
    frames[f] = { a: { base: 'home_base.png', patch: { src: await shot(`home_${f}.jpg`, { clip }), ...clip } } };
  }

  // ---------------------------------------------------------------- 2. 놓기 → 검사 중
  const b64 = fs.readFileSync(FILE).toString('base64');
  await page.evaluate(async ({ t, b64 }) => {
    const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bin], '본체.dxf', { type: '' }));
    document.querySelector('#drop').dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
    clearInterval(busyTimer);                       // 경과 초는 실제로 기다린 만큼만 — 빨리 감는 구간이라 0초에 둔다
    __vc.adopt(t); __vc.set(t);
    for (const img of document.querySelectorAll('#busy img')) { try { await img.decode(); } catch (e) {} }
    __vc.adopt(t);
  }, { t: T.drop, b64 });
  rects.busyCard = await rect('.busy-card');
  for (let f = fi(T.drop); f < fi(T.resIn); f++) {
    await set(f / FPS);
    frames[f] = { a: { base: await shot(`busy_${f}.jpg`) } };
  }

  // ---------------------------------------------------------------- 3. 결과 — 스티커가 튀어나온다
  release();
  await page.waitForSelector('#res:not([hidden])');
  await page.waitForSelector('#busy[hidden]', { state: 'attached' });
  await page.evaluate(async (t) => {
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    // 도면을 처음 맞추는 0.28초 줌아웃은 녹아드는 장면 밑에서 깨져 보인다 — 맞춘 뒤 모습에서 시작한다
    for (const a of document.getAnimations()) if (a.effect && a.effect.target && a.effect.target.id === 'pan') a.finish();
    __vc.adopt(t); __vc.set(t);
    for (const img of document.querySelectorAll('#res img')) { try { await img.decode(); } catch (e) {} }
    __vc.adopt(t);
  }, T.busyEnd);
  await page.mouse.move(pts.drop.x, pts.drop.y);
  await adopt(T.busyEnd);
  const popEnd = T.busyEnd + 0.7;
  for (let f = fi(T.busyEnd); f < fi(popEnd); f++) {
    const t = f / FPS;
    await set(t);
    const b = { base: await shot(`res_${f}.jpg`) };
    if (t < T.resIn) {
      const k = (t - T.busyEnd) / (T.resIn - T.busyEnd);
      frames[f] = { a: frames[f].a, b, mix: k };
    } else frames[f] = { a: b };
  }
  await set(popEnd + 1);
  for (const s of ['#viewer', '#stage', '#score', '#finds', '.mchip', '#fixBtn', '.rbar', '#cmp', '.tabs'])
    rects[s.replace(/[#.]/, '')] = await rect(s);
  const resBase = await shot('res_base.png', { png: true });
  for (let f = fi(popEnd); f < fi(T.travel1[0]); f++) frames[f] = { a: { base: resBase } };

  // ---------------------------------------------------------------- 4. 번호로
  const c = rects.mchip;
  pts.chip = { x: Math.round(c.x + c.w * 0.46), y: Math.round(c.y + c.h * 0.5) };
  const fb = rects.fixBtn;
  pts.fix = { x: Math.round(fb.x + fb.w * 0.5), y: Math.round(fb.y + fb.h * 0.52) };
  pts.rest = { x: Math.round(fb.x - 70), y: Math.round(fb.y - 66) };
  segs = buildSegs(pts);
  async function travel(f0, f1) {
    for (let f = f0; f < f1; f++) {
      const t = f / FPS, p = cursorAt(segs, t);
      await page.mouse.move(p.x, p.y);
      await adopt(t); await set(t);
      frames[f] = { a: { base: await shot(`m_${f}.jpg`) } };
    }
  }
  await travel(fi(T.travel1[0]), fi(T.chipClick));
  await page.mouse.down(); await page.mouse.up();
  await adopt(T.chipClick);
  await travel(fi(T.chipClick), fi(T.chipClick + 0.5));
  await set(T.chipClick + 2);
  const zoomBase = await shot('zoom_base.png', { png: true });
  for (let f = fi(T.chipClick + 0.5); f < fi(T.travel2[0]); f++) frames[f] = { a: { base: zoomBase } };

  // ---------------------------------------------------------------- 5. 수정 예시
  await travel(fi(T.travel2[0]), fi(T.fixClick));
  await page.mouse.down(); await page.mouse.up();
  await adopt(T.fixClick);
  await travel(fi(T.fixClick), fi(T.fixClick + 0.4));
  for (let f = fi(T.fixClick + 0.4); f < fi(T.away[0]); f++) frames[f] = frames[fi(T.fixClick + 0.4) - 1];
  await travel(fi(T.away[0]), fi(T.away[1] + 0.3));
  await set(T.end);
  rects.fixNote = await rect('#fixNote');
  rects.viewerAfter = await rect('#viewer');
  rects.fixLayer = await rect('.fixlayer');
  const fixBase = await shot('fix_base.png', { png: true });
  for (let f = fi(T.away[1] + 0.3); f < N; f++) frames[f] = { a: { base: fixBase } };

  const missing = frames.findIndex((x) => !x);
  if (missing >= 0) throw new Error('빈 프레임 ' + missing);
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(
    { fps: FPS, n: N, vw: VW, vh: VH, dsf: DSF, T, pts, segs, rects, dragEnter: entered, analyzeMs, frames }, null, 1));
  console.log('done', { shots: n, entered, analyzeMs, rects });
  await browser.close();
  process.exit(0);
})().catch((e) => { console.error(e); process.exit(1); });
