// compose.html 을 한 프레임씩 그려 ffmpeg 로 H.264 60fps 를 만들어 presenter/video/ 에 둔다(demo.mp4 · demo.jpg).
// node render.js [시작프레임 끝프레임 간격]  — 인자를 주면 영상 대신 그 프레임만 PNG 로 남긴다(확인용)
// node render.js explain [...]               — capture2.js 의 장면(cap2/explain) → explain.mp4 · explain.jpg (소리 없음)
const fs = require('fs'), path = require('path'), http = require('http');
const { spawn } = require('child_process');
const { chromium } = require('playwright-core');
const { VOICE, T } = require('./story.js');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FFMPEG = 'ffmpeg';                      // PATH 에 있어야 한다 (winget install Gyan.FFmpeg.Essentials)
const DEST = path.join(__dirname, '..', '..', '..', 'presenter', 'video');
const ROOT = __dirname;
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json',
                '.png': 'image/png', '.jpg': 'image/jpeg' };

const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

(async () => {
  await new Promise((r) => server.listen(8766, r));
  const browser = await chromium.launch({ executablePath: CHROME, headless: true,
    args: ['--hide-scrollbars', '--force-color-profile=srgb'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.error('pageerror', e.message));
  const args = process.argv.slice(2);
  const clip = args.length && !Number.isFinite(Number(args[0])) ? args.shift() : null;
  const name = clip || 'demo';
  await page.goto('http://127.0.0.1:8766/compose.html' + (clip ? `?cap=cap2/${encodeURIComponent(clip)}` : ''),
                  { waitUntil: 'networkidle' });
  const info = await page.evaluate(() => init());
  console.log('frames', info.n, 'font', info.fonts);
  if (!info.fonts) throw new Error('Pretendard 가 안 불러와졌다');

  const [a, b, step] = args.map(Number);
  if (Number.isFinite(a)) {
    const dir = path.join(ROOT, 'check', clip || '');
    fs.mkdirSync(dir, { recursive: true });
    for (let f = a; f <= Math.min(b, info.n - 1); f += step || 1) {
      await page.evaluate((f) => renderFrame(f), f);
      await page.screenshot({ path: path.join(dir, `f${String(f).padStart(4, '0')}.png`) });
    }
  } else {
    const out = clip ? path.join(DEST, `${name}.mp4`) : path.join(ROOT, 'video_only.mp4');
    const ff = spawn(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '60', '-c:v', 'png', '-i', '-',
      '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
      '-c:v', 'libx264', '-preset', 'slower', '-crf', '16', '-profile:v', 'high',
      '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
      '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const done = new Promise((r) => ff.on('close', r));
    for (let f = 0; f < info.n; f++) {
      await page.evaluate((f) => renderFrame(f), f);
      const png = await page.screenshot({ type: 'png' });
      if (f === 0) fs.writeFileSync(path.join(ROOT, 'poster.png'), png);   // 첫 장면 = 슬라이드에 영상이 뜨기 전 그림
      if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
      if (f % 120 === 0) console.log('frame', f);
    }
    ff.stdin.end();
    console.log('ffmpeg exit', await done);
    await new Promise((r) => spawn(FFMPEG, ['-y', '-loglevel', 'error', '-i', path.join(ROOT, 'poster.png'), '-q:v', '3',
      path.join(DEST, `${name}.jpg`)], { stdio: 'inherit' }).on('close', r));
    if (clip) { console.log('->', out); await browser.close(); server.close(); return; }   // 소리 없는 장면 — 발표하는 사람이 말한다
    // 목소리 — 대사마다 콘티 시각에 놓고 섞는다. 대사 파일은 -18 LUFS 로 맞춰 두었고 섞은 뒤 +2dB(약 -16 LUFS, 말소리 웹 기준)
    const ins = VOICE.flatMap((v) => ['-i', path.join(ROOT, 'voice', v.id + '.wav')]);
    const lanes = VOICE.map((v, i) => `[${i + 1}]adelay=${Math.round(v.t * 1000)}:all=1[a${i}]`).join(';');
    const mix = `${lanes};${VOICE.map((_, i) => `[a${i}]`).join('')}amix=inputs=${VOICE.length}:normalize=0:dropout_transition=0,` +
      `apad=whole_dur=${(info.n / 60).toFixed(3)},volume=2dB,alimiter=limit=0.84:level=false[a]`;
    await new Promise((r) => spawn(FFMPEG, ['-y', '-loglevel', 'error', '-i', out, ...ins, '-filter_complex', mix,
      '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest',
      '-movflags', '+faststart', path.join(DEST, 'demo.mp4')], { stdio: 'inherit' }).on('close', r));
    console.log('->', DEST);
  }
  await browser.close();
  server.close();
})().catch((e) => { console.error(e); process.exit(1); });
