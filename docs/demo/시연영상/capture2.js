// 10분판 시연 장면 셋을 실제 CADLens 화면으로 찍는다 — explain(지적 읽기) · recheck(고쳐서 다시 올리기) · report(신고 · 언어).
// capture.js 와 같은 방식이다. 앱의 CSS 애니메이션을 멈춰 두고 프레임마다 시간을 직접 맞춘다(가상 시계).
// 커서 · 카메라 · 자막 · 누른 자리는 사진에 찍지 않고 manifest 에 적어 두면 compose.html 이 그 위에 그린다.
// 소리는 없다 — 발표하는 사람이 그 위에 말한다(presenter/talk10.js 의 그 장 대사).
//   로컬 서버를 먼저 띄운다(README.md) →  node capture2.js  → cap2/<장면>/  (약 5분)
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright-core');
const { cursorAt, ease } = require('./story.js');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const APP = 'http://127.0.0.1:8010/';
const PUBLIC = 'https://naverogq.onrender.com';
const DRAW = path.join(__dirname, '..', '영상시연');
const BEFORE = path.join(DRAW, '1차', '본체.dxf');        // W4 · 5분판 영상과 같은 도면 — 실격 1 · 지적 7
const AFTER = path.join(DRAW, '고친뒤', '본체.dxf');      // 지적대로 고친 것 — 거칠기 기호 · Ø20.5 · 선 굵기 · 요목표 · 비교표
const FPS = 60, VW = 1600, VH = 900, DSF = 2;               // 카메라가 2배까지 당기므로 2배로 찍는다
const OUT = path.join(__dirname, 'cap2');

const VC = `window.__vc = { m: new Map(),
  adopt(v) { for (const a of document.getAnimations()) if (!this.m.has(a)) { a.pause(); this.m.set(a, v); } },
  set(t) { for (const [a, v] of this.m) { if (a.playState === 'idle') { this.m.delete(a); continue; }
                                         a.currentTime = Math.max(0, (t - v) * 1000); } },
  reset() { for (const a of document.getAnimations()) { try { a.finish(); } catch (e) {} } this.m.clear(); } };`;

// 한 장면 — 시간(t)을 앞으로 밀며 찍는다. 움직이는 동안은 프레임마다, 멈춰 있으면 마지막 사진을 그대로 쓴다.
class Rec {
  constructor(page, name, cur) {
    Object.assign(this, { page, name, cur, t: 0, n: 0, last: null, frames: [], segs: [], clicks: [], xfade: [], shots: [], caps: [] });
    this.dir = path.join(OUT, name);
    fs.rmSync(this.dir, { recursive: true, force: true });
    fs.mkdirSync(this.dir, { recursive: true });
  }
  f(t) { return Math.round(t * FPS); }
  async snap() {
    const name = `${String(this.n++).padStart(5, '0')}.jpg`;
    await this.page.screenshot({ path: path.join(this.dir, name), type: 'jpeg', quality: 93, animations: 'allow', caret: 'hide' });
    return (this.last = name);
  }
  async live(dur, each) {
    for (let f = this.f(this.t); f < this.f(this.t + dur); f++) {
      const t = f / FPS;
      if (each) await each(t);
      await this.page.evaluate((t) => { __vc.adopt(t); __vc.set(t); }, t);
      this.frames[f] = await this.snap();
    }
    this.t += dur;
  }
  hold(dur) {
    for (let f = this.f(this.t); f < this.f(this.t + dur); f++) this.frames[f] = this.last;
    this.t += dur;
  }
  async wait(dur, moving = 0.5) { await this.live(Math.min(dur, moving)); if (dur > moving) this.hold(dur - moving); }
  async move(to, dur, arc = 0.06) {                       // 사람 손처럼 — story.js 와 같은 곡선
    const seg = { t0: this.t, t1: this.t + dur, from: { ...this.cur }, to: { ...to }, arc };
    this.segs.push(seg);
    await this.live(dur, (t) => { const p = cursorAt([seg], t); return this.page.mouse.move(p.x, p.y); });
    this.cur = { ...to };
  }
  async scroll(dy, dur) {
    const y0 = await this.page.evaluate(() => scrollY), t0 = this.t;
    await this.live(dur, (t) => this.page.evaluate((y) => scrollTo({ top: y, behavior: 'instant' }),
                                                    Math.round(y0 + dy * ease((t - t0) / dur))));
  }
  async click(fade = 0.16) {
    await this.page.mouse.down();
    await this.page.mouse.up();
    this.clicks.push(+this.t.toFixed(4));
    if (fade) this.xfade.push({ t0: +this.t.toFixed(4), d: fade });
  }
  cam(t0, t1, p, z, lin = false) { this.shots.push({ t0, t1, p, z, lin }); }
  cap(t0, t1, n, m, s) { this.caps.push({ n, t0, t1, m, s }); }
  save(extra) {
    const n = this.f(this.t);
    const frames = [];
    for (let f = 0; f < n; f++) {
      if (!this.frames[f]) throw new Error(`${this.name} 빈 프레임 ${f}`);
      frames.push({ a: { base: this.frames[f] } });
    }
    this.shots.sort((a, b) => a.t0 - b.t0);
    fs.writeFileSync(path.join(this.dir, 'manifest.json'), JSON.stringify({
      fps: FPS, n, vw: VW, vh: VH, dsf: DSF, segs: this.segs, clicks: this.clicks, xfade: this.xfade,
      shots: this.shots, caps: this.caps, capWho: '실제 화면', frames, ...extra }, null, 1));
    console.log(this.name, { seconds: +this.t.toFixed(2), shots: this.n });
  }
}

(async () => {
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
  await ctx.route('**/api/sticker/**', async (route) => {          // 공개 화면과 같은 OGQ 스티커 — 통계를 세지 않는 주소
    const name = route.request().url().split('/api/sticker/')[1];
    await route.fulfill({ response: await route.fetch({ url: `${PUBLIC}/api/sticker/${name}` }) });
  });
  let release = () => {}, held = Promise.resolve();
  await ctx.route('**/api/analyze', async (route) => {             // 검사 결과는 찍을 준비가 될 때까지 붙잡는다
    const r = await route.fetch(); const body = await r.body();
    await held; await route.fulfill({ response: r, body });
  });
  await ctx.route('**/api/ai-extra/**', () => {});                 // 늦게 오는 AI 답이 목록을 다시 그리지 않게
  await ctx.route('**/api/feedback', (route) => route.abort());     // 신고는 보내지 않는다 — 혹시 눌려도 안 나가게

  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.error('pageerror', e.message));
  await page.goto(APP, { waitUntil: 'networkidle' });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(['wait', 'fail', 'error', 'pass', 'short', 'fixed'].map((n) => new Promise((r) => {
      const i = new Image(); i.onload = i.onerror = r; i.src = '/api/sticker/' + n; })));
  });
  await page.evaluate(VC);
  const rect = (sel) => page.evaluate((s) => {
    const e = typeof s === 'string' ? document.querySelector(s) : null; if (!e) return null;
    const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height };
  }, sel);
  const shown = (sel) => page.evaluate((s) => {                 // 같은 선택자가 숨은 메뉴에도 있으면 보이는 것
    const e = [...document.querySelectorAll(s)].find((x) => x.getBoundingClientRect().width > 0);
    if (!e) return null;
    const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height };
  }, sel);
  const at = (r, u = 0.5, v = 0.5) => ({ x: Math.round(r.x + r.w * u), y: Math.round(r.y + r.h * v) });
  const mid = (r) => at(r);
  const settle = async () => {                                    // 찍지 않는 사이에 화면을 가라앉힌다
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    await page.evaluate(() => __vc.reset());
  };
  const findCard = (word) => page.evaluate((w) => {                // 제목에 그 말이 든 지적 카드의 번호
    const el = [...document.querySelectorAll('#finds .finding')].find((x) => x.querySelector('.ftitle').textContent.includes(w));
    return el ? el.dataset.i : null;
  }, word);

  // ---------------------------------------------------------------- 찍기 전 — 고치기 전 도면을 한 번 검사해 둔다
  const drop = async (file) => {
    const b64 = fs.readFileSync(file).toString('base64');
    await page.evaluate(async (b64) => {
      const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const dt = new DataTransfer();
      dt.items.add(new File([bin], '본체.dxf', { type: '' }));
      document.querySelector('#drop').dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
    }, b64);
    await page.waitForSelector('#res:not([hidden])');
    await page.waitForSelector('#busy[hidden]', { state: 'attached' });
    await page.evaluate(async () => { for (const img of document.querySelectorAll('#res img')) { try { await img.decode(); } catch (e) {} } });
    await settle();
  };
  await drop(BEFORE);
  await page.mouse.move(1180, 830);
  await page.waitForTimeout(600);
  await settle();

  // ---------------------------------------------------------------- ① explain — 지적을 열고, 정해 둔 질문, 채점 항목
  {
    const R = new Rec(page, 'explain', { x: 1180, y: 830 });
    const list = await rect('#finds');
    const dimI = await findCard('치수 누락'), aiI = await findCard('제3각법');
    const dimHead = await rect(`#finds .finding[data-i="${dimI}"] .fhead`);
    R.cam(0.2, 1.4, { x: list.x + list.w / 2, y: 600 }, 1.62);
    await R.wait(0.5);
    await R.move(at(dimHead, 0.32, 0.38), 1.1);
    await R.wait(0.2);
    await R.click();                                              // 치수 누락 — 이유 · 고치는 법 · 위치
    const dimBody = await rect(`#fb-${dimI}`);
    R.cam(R.t + 0.1, R.t + 1.2, { x: dimBody.x + dimBody.w / 2, y: dimBody.y + dimBody.h / 2 - 50 }, 1.85);
    R.cap(R.t + 0.2, R.t + 4.2, 5, '지적을 열면 이유와 고치는 법', '어디를 고치면 되는지 위치까지');
    await R.wait(3.6, 0.4);
    const aiHead0 = await rect(`#finds .finding[data-i="${aiI}"] .fhead`);
    const dy = Math.round(aiHead0.y - 236);                        // AI 지적이 위쪽에 오게 내린다
    R.cam(R.t, R.t + 1.3, { x: list.x + list.w / 2, y: 470 }, 1.62);
    await R.scroll(dy, 1.3);
    const aiHead = await rect(`#finds .finding[data-i="${aiI}"] .fhead`);
    await R.move(at(aiHead, 0.3, 0.38), 0.9);
    await R.wait(0.2);
    await R.click();                                              // AI 지적 — 정해 둔 질문 셋
    const asks = await rect(`#finds .finding[data-i="${aiI}"] .askbar`);
    const q3 = await rect(`#finds .finding[data-i="${aiI}"] .asks button:nth-child(3)`);
    R.cam(R.t + 0.2, R.t + 1.4, { x: asks.x + asks.w / 2, y: asks.y + asks.h / 2 + 30 }, 1.9);
    await R.wait(1.3, 0.4);
    await R.move(at(q3, 0.5, 0.55), 0.9);
    await R.wait(0.2);
    await R.click();                                              // '고친 뒤 확인은?' — 채점할 때 만들어 둔 답
    const ans = await rect(`#finds .finding[data-i="${aiI}"] .askbar`);
    R.cam(R.t + 0.1, R.t + 1.0, { x: ans.x + ans.w / 2, y: ans.y + ans.h / 2 }, 1.95);
    R.cap(R.t - 1.4, R.t + 3.9, 6, '궁금한 건 정해 둔 질문 버튼으로', '답은 채점할 때 미리 만들어 둔 것, AI와 대화하는 창은 없습니다');
    await R.wait(4.0, 0.4);
    R.cam(R.t, R.t + 1.4, { x: list.x + list.w / 2, y: 520 }, 1.55);
    await R.scroll(-dy, 1.4);
    const tab = await rect('#tab-items');
    await R.move(at(tab, 0.5, 0.5), 0.9);
    await R.wait(0.2);
    await R.click();                                              // 채점 항목 — 70점 규칙 · 30점 AI
    const items = await rect('#items');
    R.cam(R.t + 0.2, R.t + 1.4, { x: items.x + items.w / 2, y: items.y + items.h * 0.42 }, 1.75);
    R.cam(R.t + 1.4, R.t + 8.6, { x: items.x + items.w / 2, y: items.y + items.h * 0.42 }, 1.82, true);
    R.cap(R.t + 0.3, R.t + 8.6, 7, '100점 중 70점은 규칙, 30점은 AI', 'AI가 매긴 투상도 칸에는 AI 표시');
    await R.move({ x: Math.round(items.x + items.w - 30), y: Math.round(items.y + items.h + 40) }, 0.9, 0.04);
    await R.wait(8.0, 0.3);
    R.save({ cursor: { in: 0.15, out: [R.t - 1.3, R.t - 0.9] } });
  }

  // ---------------------------------------------------------------- 사이 — 처음 모습으로 (찍지 않는다)
  await page.click('#tab-find');
  await page.evaluate(() => {
    for (const h of document.querySelectorAll('#finds .fhead[aria-expanded="true"]')) h.click();
    scrollTo({ top: 0, behavior: 'instant' });
  });
  await page.mouse.move(1180, 830);
  await settle();

  // ---------------------------------------------------------------- ② recheck — 고친 파일을 같은 이름으로 다시 올리기
  {
    const R = new Rec(page, 'recheck', { x: 1180, y: 830 });
    const reup = await rect('#reup');
    R.cam(0.2, 1.3, { x: 1150, y: 300 }, 1.45);
    R.cap(0.5, 3.9, 8, '지적대로 고친 파일을 같은 이름으로 다시 올리면');
    await R.wait(0.4);
    await R.move(at(reup, 0.42, 0.5), 1.1);
    await R.wait(0.2);
    const chooser = page.waitForEvent('filechooser');
    await R.click(0);
    const fileAt = R.t;
    await R.wait(0.85, 0.85);                                     // 고친 파일을 고르는 동안 — compose 가 파일 카드를 그린다
    let resolve; held = new Promise((r) => { resolve = r; }); release = resolve;
    // 경로 대신 내용을 넘긴다 — 한글 경로를 Chrome 이 못 읽어 빈 파일이 올라간 적이 있다
    await (await chooser).setFiles({ name: '본체.dxf', mimeType: 'application/octet-stream', buffer: fs.readFileSync(AFTER) });
    await page.waitForSelector('#busy:not([hidden])');
    await page.evaluate(async (t) => {
      clearInterval(busyTimer);                                   // 경과 초는 빨리 감는 구간이라 0초에 둔다
      for (const img of document.querySelectorAll('#busy img')) { try { await img.decode(); } catch (e) {} }
      __vc.adopt(t);
    }, R.t);
    const ff0 = R.t;
    const busyCard = await rect('.busy-card');
    R.cam(R.t, R.t + 0.6, mid(busyCard), 1.7);
    await R.live(1.5);
    release();
    await page.waitForSelector('#busy[hidden]', { state: 'attached' });
    await page.waitForSelector('#cmp .cmp-score');
    await page.evaluate(async () => { for (const img of document.querySelectorAll('#res img')) { try { await img.decode(); } catch (e) {} } });
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    await page.evaluate(() => { for (const a of document.getAnimations()) if (a.effect && a.effect.target && a.effect.target.id === 'pan') a.finish(); });
    // 영상에 쓰기 전에 결과를 확인한다 — 고친 뒤 78점 · 실격 해결 · 고쳐짐 4 · 그대로 2 · 새로 생김 0 (로컬 서버로 미리 잰 값)
    const got = await page.evaluate(() => ({ score: RAW.scorecard.auto_score, dq: RAW.scorecard.disqualified,
      tags: [...document.querySelectorAll('#cmp .cmp-tag b')].map((b) => +b.textContent) }));
    if (got.score !== 78 || got.dq || got.tags.join() !== '4,2,0') throw new Error('재검사 결과가 예상과 다르다 ' + JSON.stringify(got));
    R.xfade.push({ t0: +R.t.toFixed(4), d: 0.24 });
    const ff1 = R.t;
    const cmp = await rect('#cmp'), score = await rect('#score');
    R.cam(R.t + 0.1, R.t + 1.3, { x: cmp.x + cmp.w / 2, y: cmp.y + cmp.h / 2 }, 1.9);
    R.cap(R.t + 0.4, R.t + 15.4, 9, '지난번 결과와 비교해서 보여 줍니다', '실격이 풀렸고, 고친 네 가지는 고쳐짐으로');
    await R.wait(7.0, 1.0);
    R.cam(R.t, R.t + 1.5, { x: score.x + score.w / 2, y: (score.y + cmp.y + cmp.h) / 2 }, 1.45);
    await R.wait(7.4, 0.2);
    R.save({ cursor: { in: 0.15, out: [ff0 - 0.5, ff0 - 0.1] },
             file: { t0: fileAt + 0.05, drop: ff0 - 0.3, name: '본체.dxf', sub: '고친 파일', ext: 'DXF' },
             ff: [ff0 - 0.2, ff1 + 0.2] });
  }

  // ---------------------------------------------------------------- ③ report — 도면에서 네모로 골라 신고 창 · 언어 넷
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
  await page.mouse.move(1180, 830);
  await settle();
  {
    const R = new Rec(page, 'report', { x: 1180, y: 830 });
    const pick = await rect('#pickBtn'), stage = await rect('#stage');
    R.cam(0.2, 1.3, { x: 560, y: 380 }, 1.6);
    await R.wait(0.4);
    await R.move(at(pick, 0.45, 0.5), 1.0);
    await R.wait(0.2);
    await R.click();                                              // 부분 지정 — 도면에서 끌어 고른다
    R.cap(R.t + 0.1, R.t + 7.0, 10, '결과가 틀린 것 같으면 도면에서 골라 신고', '고른 부분이 그림으로 같이 갑니다');
    await R.wait(0.6, 0.5);
    const a = { x: Math.round(stage.x + stage.w * 0.17), y: Math.round(stage.y + stage.h * 0.40) };
    const b = { x: Math.round(stage.x + stage.w * 0.47), y: Math.round(stage.y + stage.h * 0.80) };
    R.cam(R.t, R.t + 0.8, { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, 1.6);
    await R.move(a, 0.8);
    await R.wait(0.15, 0.15);
    await page.mouse.down();
    R.clicks.push(+R.t.toFixed(4));
    await R.move(b, 1.4, 0.02);
    await page.mouse.up();
    await page.waitForSelector('#note:not([hidden])');
    await page.evaluate(async () => { const i = document.querySelector('#noteShotImg'); if (i && i.src) { try { await i.decode(); } catch (e) {} } });
    R.xfade.push({ t0: +R.t.toFixed(4), d: 0.16 });
    const card = await rect('#note .modal-card'), shotBox = await rect('#noteShotBox');
    R.cam(R.t + 0.1, R.t + 1.1, mid(card), Math.min(1.9, 960 / (card.h * 0.92)));
    R.cam(R.t + 1.6, R.t + 2.8, mid(shotBox), 2.0);                 // 끌어 고른 부분이 그림으로 붙었다
    await R.wait(3.8, 0.6);
    const x = await rect('#note .modal-x');
    await R.move(at(x), 0.8);
    await R.wait(0.2);
    await R.click();                                              // 보내지 않고 닫는다
    R.cam(R.t + 0.1, R.t + 1.1, { x: 1000, y: 400 }, 1.5);
    R.cap(R.t + 0.5, R.t + 6.9, 11, '한국어, English, 日本語, 中文', '화면과 지적이 그 언어로 바뀝니다');
    await R.wait(0.5, 0.4);
    for (const lang of ['en', 'ja', 'zh']) {
      const btn = await shown(`[data-lang="${lang}"]`);
      await R.move(at(btn), lang === 'en' ? 0.9 : 0.45, 0.04);
      await R.wait(0.15, 0.15);
      await R.click(0.2);
      await R.wait(1.35, 0.4);
    }
    await R.wait(0.6, 0.1);
    R.save({ cursor: { in: 0.15, out: [R.t - 0.5, R.t - 0.1] } });
  }

  // ---------------------------------------------------------------- 사진 — 정확도 페이지 (stills.py 가 잘라 쓴다)
  await page.evaluate(() => { localStorage.setItem('cadcheck.lang', 'ko'); });
  await page.goto(APP + 'accuracy', { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(OUT, 'accuracy.png'), fullPage: true });

  await browser.close();
  process.exit(0);
})().catch((e) => { console.error(e); process.exit(1); });
