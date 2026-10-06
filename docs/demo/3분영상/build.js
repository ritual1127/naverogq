// 데모데이 ② 3분 데모 영상 — 발표 도우미 10분판의 슬라이드 + 실제 화면 시연 영상 넷 + 팀원 목소리(AI 합성)를 잇는다.
//   node build.js          (먼저 voice/ 에 고른 목소리가 있어야 한다 — README.md)
// 결과: CADLens_3분_데모.mp4 (1920×1080 60fps, -16 LUFS, 3분 안). 목소리가 나오는 동안 오른쪽 위에 "○○ 목소리 · AI 음성".
const fs = require('fs'), path = require('path'), http = require('http');
const { spawnSync } = require('child_process');
const { chromium } = require('../시연영상/node_modules/playwright-core');

const HERE = __dirname;
const PRESENTER = path.join(HERE, '..', '..', '..', 'presenter');
const CAP2 = path.join(HERE, '..', '시연영상', 'cap2');
const VOICE = path.join(HERE, 'voice');
const BUILD = path.join(HERE, 'build');
const OUT = path.join(HERE, 'CADLens_3분_데모.mp4');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const LINES = JSON.parse(fs.readFileSync(path.join(HERE, 'lines.json'), 'utf8'));
const NAME = { kimseungjun: '김승준', parkjiwan: '박지완', andaeyeol: '안대열', jangwooyoung: '장우영' };

const ff = (args) => {
  const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...args], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error('ffmpeg ' + args.join(' ') + '\n' + r.stderr);
};
const dur = (f) => Number(spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], { encoding: 'utf8' }).stdout);
const voice = (key) => path.join(VOICE, `${key}.wav`);
const clicks = (clip) => JSON.parse(fs.readFileSync(path.join(CAP2, clip, 'manifest.json'), 'utf8'));

// 장면 — slide 는 10분판 몇 번째 장, clip 은 presenter/video 의 영상. lines 는 [대사 키, 놓을 시각(초, 없으면 앞 대사 뒤 0.45초)]
function scenes() {
  const ex = clicks('explain'), re = clicks('recheck'), rp = clicks('report');
  return [
    { slide: 1, lines: [['k1']], lead: 0.5 },
    { slide: 2, lines: [['k2'], ['k3']] },
    { slide: 3, lines: [['k4']] },
    { slide: 4, lines: [['k5']] },
    { clip: 'demo', voiced: true },                                      // 이미 부분마다 목소리가 든 32초 영상
    { clip: 'explain', lines: [['p1', ex.clicks[0] + 0.3], ['p2', ex.clicks[1] + 0.5], ['p3', ex.clicks[3] + 0.4]] },
    { clip: 'recheck', lines: [['p4', 0.5], ['p5', re.ff[1] + 0.3]] },
    { clip: 'report', lines: [['p6', rp.clicks[0] + 0.2], ['p7', rp.clicks[rp.clicks.length - 3] - 0.4]] },
    { slide: 9, lines: [['p8']] },
    { slide: 10, lines: [['a1'], ['a2']] },
    { slide: 12, lines: [['j1']] },
    { slide: 13, lines: [['j2']] },
    { slide: 19, lines: [['k6']], tail: 1.6 },
  ];
}

const server = http.createServer((req, res) => {
  const p = path.join(PRESENTER, decodeURIComponent(req.url.split('?')[0].split('#')[0]));
  if (!p.startsWith(PRESENTER) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  const type = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4' };
  res.writeHead(200, { 'Content-Type': type[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

(async () => {
  fs.rmSync(BUILD, { recursive: true, force: true });
  fs.mkdirSync(BUILD, { recursive: true });
  await new Promise((r) => server.listen(8767, r));
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  // 슬라이드 — 발표 도우미를 전체화면으로 띄워 그 장만 찍는다(중계 없이, 이 기기 혼자)
  await page.route('**/supabase-js@2/**', (r) => r.abort());
  await page.goto('http://127.0.0.1:8767/index.html?talk=10#video3', { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.keyboard.press('KeyF');
  await page.evaluate(() => { document.getElementById('toast').hidden = true; });
  const shot = async (n) => {
    const dots = await page.$$('#dots button');
    await page.evaluate((i) => document.querySelectorAll('#dots button')[i].click(), n - 1);
    await page.waitForTimeout(400);
    await page.evaluate(() => { document.getElementById('toast').hidden = true; });
    const f = path.join(BUILD, `slide${n}.png`);
    await page.screenshot({ path: f });
    return f;
  };
  // 목소리 표시 — 오른쪽 위 작은 알약. 대회 AI 사용 공개(README 의 AI 표)
  const label = async (who) => {
    const f = path.join(BUILD, `label_${who}.png`);
    await page.setContent(`<html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"></head>
      <body style="margin:0;background:transparent"><div id="l" style="display:inline-flex;align-items:center;gap:12px;padding:12px 24px 12px 18px;border-radius:999px;
      background:rgba(11,17,31,.82);color:#fff;font:700 26px 'Pretendard Variable',sans-serif;letter-spacing:-.2px">
      <span style="width:12px;height:12px;border-radius:50%;background:#5ea2ef"></span>${NAME[who]} 목소리 · AI 음성</div></body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    await (await page.$('#l')).screenshot({ path: f, omitBackground: true });
    return f;
  };

  const parts = [];
  let total = 0;
  for (const [i, s] of scenes().entries()) {
    const seg = path.join(BUILD, `seg${String(i).padStart(2, '0')}.mp4`);
    const who = s.lines && LINES[s.lines[0][0]][0];
    // 대사를 놓을 시각과 장면 길이
    let t = s.lead ?? 0.6, end = 0;
    const placed = (s.lines || []).map(([key, at]) => {
      const start = at ?? (end ? end + 0.45 : t);
      end = start + dur(voice(key));
      return { key, start };
    });
    let base, len;
    if (s.slide) {
      base = ['-loop', '1', '-framerate', '60', '-i', await shot(s.slide)];
      len = end + (s.tail ?? 0.7);
    } else {
      const src = path.join(PRESENTER, 'video', `${s.clip}.mp4`);
      base = ['-i', src];
      len = Math.max(dur(src), end + 0.6);
    }
    const audioIn = placed.flatMap((p) => ['-i', voice(p.key)]);
    const lbl = who && !s.voiced ? await label(who) : null;
    const nA = placed.length;
    const firstAudio = 1 + (lbl ? 1 : 0);
    const v = lbl
      ? `[0:v]tpad=stop_mode=clone:stop_duration=${len.toFixed(3)},trim=duration=${len.toFixed(3)},setpts=PTS-STARTPTS[bv];` +
        `[bv][1:v]overlay=W-w-44:40:enable='between(t,${(placed[0].start - 0.3).toFixed(2)},${(end + 0.4).toFixed(2)})',format=yuv420p[v]`
      : `[0:v]tpad=stop_mode=clone:stop_duration=${len.toFixed(3)},trim=duration=${len.toFixed(3)},setpts=PTS-STARTPTS,format=yuv420p[v]`;
    let a;
    if (s.voiced) a = `[0:a]aformat=sample_rates=48000:channel_layouts=stereo,apad=whole_dur=${len.toFixed(3)}[a]`;
    else a = placed.map((p, j) => `[${firstAudio + j}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=${Math.round(p.start * 1000)}:all=1[a${j}]`).join(';') +
      `;${placed.map((_, j) => `[a${j}]`).join('')}amix=inputs=${nA}:normalize=0:dropout_transition=0,apad=whole_dur=${len.toFixed(3)}[a]`;
    ff([...base, ...(lbl ? ['-loop', '1', '-i', lbl] : []), ...audioIn,
        '-filter_complex', `${v};${a}`, '-map', '[v]', '-map', '[a]', '-t', len.toFixed(3), '-r', '60',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', seg]);
    parts.push(seg);
    console.log(`${String(i).padStart(2)} ${(s.slide ? 'slide ' + s.slide : s.clip).padEnd(9)} ${len.toFixed(2)}s  시작 ${total.toFixed(2)}s`,
                placed.map((p) => `${p.key}@${p.start.toFixed(2)}`).join(' '));
    total += len;
  }
  await browser.close();
  server.close();

  // 잇고 소리를 -16 LUFS 로(말소리 웹 기준). 두 번 재서 맞춘다
  const list = path.join(BUILD, 'list.txt');
  fs.writeFileSync(list, parts.map((p) => `file '${p.replace(/\\/g, '/')}'`).join('\n'));
  const joined = path.join(BUILD, 'joined.mp4');
  ff(['-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', joined]);
  const meas = spawnSync('ffmpeg', ['-hide_banner', '-i', joined, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], { encoding: 'utf8' }).stderr;
  const j = JSON.parse(meas.slice(meas.lastIndexOf('{'), meas.lastIndexOf('}') + 1));
  ff(['-i', joined, '-c:v', 'copy', '-af',
      `loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:measured_I=${j.input_i}:measured_TP=${j.input_tp}:measured_LRA=${j.input_lra}:measured_thresh=${j.input_thresh}`,
      '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', OUT]);
  console.log('->', OUT, dur(OUT).toFixed(2) + 's');
  if (dur(OUT) > 180) throw new Error('3분을 넘는다');
})().catch((e) => { console.error(e); process.exit(1); });
