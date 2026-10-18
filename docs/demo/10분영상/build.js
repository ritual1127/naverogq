// 2차 제출 · 본선용 10분 발표 영상 — 발표 도우미 10분판 19장 + 실제 화면 시연 넷 + 팀원 넷의 목소리(AI 합성)를 잇는다.
//   node build.js          (먼저 voice/ 에 고른 목소리가 있어야 한다 — README.md)
//   node build.js slides   (영상 대신 장 사진만 build/ 에 — 미리 보기)
// 결과: CADLens_10분_발표.mp4 (1920×1080 60fps, -16 LUFS, 10분 안) · 같은 이름 .srt(자막) · youtube.txt(제목 · 설명 · 챕터) · thumb.jpg
// 목소리가 나오는 동안 오른쪽 위에 "○○ 목소리 · AI 음성"(대회 AI 사용 공개). 장 사이는 0.3초 겹쳐 넘긴다.
const fs = require('fs'), path = require('path'), http = require('http');
const { spawnSync } = require('child_process');
const { chromium } = require('../시연영상/node_modules/playwright-core');
const { VOICE: DEMO_VOICE } = require('../시연영상/story.js');

const HERE = __dirname;
const PRESENTER = path.join(HERE, '..', '..', '..', 'presenter');
const CAP2 = path.join(HERE, '..', '시연영상', 'cap2');
const VOICE = path.join(HERE, 'voice');
const BUILD = path.join(HERE, 'build');
const OUT = path.join(HERE, 'CADLens_10분_발표.mp4');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const LINES = JSON.parse(fs.readFileSync(path.join(HERE, 'lines.json'), 'utf8'));
const SUBS = JSON.parse(fs.readFileSync(path.join(HERE, 'subs.json'), 'utf8'));
const NAME = { kimseungjun: '김승준', parkjiwan: '박지완', andaeyeol: '안대열', jangwooyoung: '장우영' };
const XF = 0.3;                      // 장 사이 겹쳐 넘김
const GAP = 0.7, SPLIT = 0.35;       // 줄 사이 · 한 줄을 나눠 합성한 문장 사이 — 0.55 로는 숫자 장이 빠듯했다
const LEAD = 0.8, TAIL = 1.2, HOLD = 1.6;   // 장 처음 · 장 끝 쉼, 그래프 · 숫자 장은 끝에 조금 더 머문다
const LIMIT = 600;

const ff = (args) => {
  const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...args], { encoding: 'utf8', maxBuffer: 1 << 26 });
  if (r.status !== 0) throw new Error('ffmpeg ' + args.join(' ').slice(0, 400) + '\n' + r.stderr);
};
const dur = (f) => Number(spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], { encoding: 'utf8' }).stdout);
const voice = (key) => path.join(VOICE, `${key}.wav`);
const clicks = (clip) => JSON.parse(fs.readFileSync(path.join(CAP2, clip, 'manifest.json'), 'utf8'));
const base = (k) => k.replace(/[ab]$/, '');

// 장면 — slide 는 10분판 몇 번째 장, clip 은 presenter/video 의 영상. lines 는 [대사 키, 놓을 시각(초, 없으면 앞 대사 뒤)]
function scenes() {
  const ex = clicks('explain'), re = clicks('recheck'), rp = clicks('report');
  const s = (n, keys, opt = {}) => ({ slide: n, lines: keys.map((k) => [k]), ...opt });
  return [
    s(1, ['01_1'], { lead: 1.2, chapter: '표지 · 문제 — 끝나기 17분 전' }),    // 유튜브 챕터는 한 칸이 10초 이상이어야 해 표지와 합친다
    s(2, ['02_1', '02_2a', '02_2b', '02_3']),
    s(3, ['03_1a', '03_1b', '03_2', '03_3'], { tail: HOLD }),
    s(4, ['04_1a', '04_1b', '04_2', '04_3'], { chapter: 'CADLens 소개' }),
    { clip: 'demo', voiced: true, chapter: '시연 — 올리기 · 번호 · 수정 예시' },
    { clip: 'explain', lines: [['06_1', ex.clicks[0] + 0.3], ['06_2', ex.clicks[1] + 0.5], ['06_3', ex.clicks[3] + 0.4]], chapter: '시연 — 지적 읽기 · 다시 올리기 · 신고 · 언어' },
    { clip: 'recheck', lines: [['07_1', 0.5], ['07_2', re.ff[1] + 0.3], ['07_3']] },
    { clip: 'report', lines: [['08_1', rp.clicks[0] + 0.2], ['08_2', rp.clicks[rp.clicks.length - 3] - 0.4]] },
    s(9, ['09_1', '09_2', '09_3a', '09_3b'], { tail: HOLD, chapter: '검사 속도 16.9초 → 9.9초' }),
    s(10, ['10_1', '10_2', '10_3', '10_4'], { tail: HOLD, chapter: '실제 도면 23장 · 숫자 다시 세기' }),
    s(11, ['11_1', '11_2', '11_3'], { tail: HOLD }),
    s(12, ['12_1', '12_2', '12_3', '12_4'], { tail: HOLD, chapter: '공개 첫 주 · 북극성 지표' }),
    s(13, ['13_1', '13_2', '13_3'], { tail: HOLD }),
    s(14, ['14_1', '14_2', '14_3', '14_4'], { tail: HOLD, chapter: '아직 안 된 것' }),
    s(15, ['15_1', '15_2', '15_3a', '15_3b', '15_4a', '15_4b', '15_5'], { chapter: '8주 동안 바뀐 생각' }),
    s(16, ['16_1', '16_2a', '16_2b', '16_3', '16_4a', '16_4b', '16_5'], { chapter: '본선까지 · 운영 비용' }),
    s(17, ['17_1a', '17_1b', '17_2a', '17_2b', '17_3']),
    s(18, ['18_1a', '18_1b', '18_2'], { tail: HOLD, chapter: '팀 소개 · 마무리' }),
    s(19, ['19_1', '19_2'], { tail: 2.4 }),
  ];
}

const server = http.createServer((req, res) => {
  const p = path.join(PRESENTER, decodeURIComponent(req.url.split('?')[0].split('#')[0]));
  if (!p.startsWith(PRESENTER) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  const type = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4' };
  res.writeHead(200, { 'Content-Type': type[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

const ts = (t, sep) => {             // 0:00 꼴(챕터) 또는 00:00:00,000 꼴(자막)
  if (!sep) { const s = Math.floor(t + 1e-6); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; }
  const ms = Math.round(t * 1000);
  const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}${sep}${String(ms % 1000).padStart(3, '0')}`;
};

(async () => {
  const only = process.argv[2];
  fs.rmSync(BUILD, { recursive: true, force: true });
  fs.mkdirSync(BUILD, { recursive: true });
  await new Promise((r) => server.listen(8768, r));
  const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--force-color-profile=srgb'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const lp = await browser.newPage({ viewport: { width: 1920, height: 1080 } });     // 목소리 표시를 그리는 탭(슬라이드 탭과 따로)

  // 슬라이드 — 발표 도우미를 전체화면으로 띄워 그 장만 찍는다(중계 없이, 이 기기 혼자)
  await page.route('**/supabase-js@2/**', (r) => r.abort());
  await page.goto('http://127.0.0.1:8768/index.html?talk=10#video10', { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.keyboard.press('KeyF');
  await page.evaluate(() => { document.getElementById('toast').hidden = true; });
  const shot = async (n) => {
    await page.evaluate((i) => document.querySelectorAll('#dots button')[i].click(), n - 1);
    await page.waitForTimeout(500);
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => { document.getElementById('toast').hidden = true; });
    const f = path.join(BUILD, `slide${String(n).padStart(2, '0')}.png`);
    await page.screenshot({ path: f });
    return f;
  };
  if (only === 'slides') {
    for (let n = 1; n <= 19; n++) await shot(n);
    await browser.close(); server.close();
    return console.log('->', BUILD);
  }
  // 목소리 표시 — 오른쪽 위 작은 알약. 대회 AI 사용 공개(README 의 AI 표)
  const label = async (who) => {
    const f = path.join(BUILD, `label_${who}.png`);
    if (fs.existsSync(f)) return f;
    await lp.setContent(`<html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"></head>
      <body style="margin:0;background:transparent"><div id="l" style="display:inline-flex;align-items:center;gap:12px;padding:12px 24px 12px 18px;border-radius:999px;
      background:rgba(11,17,31,.82);color:#fff;font:700 26px 'Pretendard Variable',sans-serif;letter-spacing:-.2px">
      <span style="width:12px;height:12px;border-radius:50%;background:#5ea2ef"></span>${NAME[who]} 목소리 · AI 음성</div></body></html>`);
    await lp.evaluate(() => document.fonts.ready);
    await lp.waitForTimeout(300);
    await (await lp.$('#l')).screenshot({ path: f, omitBackground: true });
    return f;
  };

  const parts = [];
  const subs = [];                   // [장면 번호, 장면 안 시작, 끝, 글]
  const plan = [];
  for (const [i, s] of scenes().entries()) {
    const seg = path.join(BUILD, `seg${String(i).padStart(2, '0')}.mp4`);
    const who = s.lines && LINES[s.lines[0][0]][0];
    // 대사를 놓을 시각과 장면 길이 — 정한 시각이 앞 대사와 겹치면 뒤로 민다
    let end = 0, prev = null;
    const placed = (s.lines || []).map(([key, at]) => {
      const gap = prev && base(prev) === base(key) ? SPLIT : GAP;
      const start = Math.max(at ?? 0, prev ? end + gap : (at ?? (s.lead ?? LEAD)));
      end = start + dur(voice(key));
      prev = key;
      subs.push([i, start, end, SUBS[key]]);
      return { key, start };
    });
    if (s.voiced) for (const v of DEMO_VOICE) subs.push([i, v.t, v.t + v.dur, v.say]);
    let input, len;
    if (s.slide) {
      input = ['-loop', '1', '-framerate', '60', '-i', await shot(s.slide)];
      len = end + (s.tail ?? TAIL);
    } else {
      const src = path.join(PRESENTER, 'video', `${s.clip}.mp4`);
      input = ['-i', src];
      len = Math.max(dur(src), end + 0.7);
    }
    const audioIn = placed.flatMap((p) => ['-i', voice(p.key)]);
    const lbl = who && !s.voiced ? await label(who) : null;
    const firstAudio = 1 + (lbl ? 1 : 0);
    const L = len.toFixed(3);
    const v = `[0:v]scale=1920:1080:flags=lanczos,fps=60,tpad=stop_mode=clone:stop_duration=${L},trim=duration=${L},setpts=PTS-STARTPTS` +
      (lbl ? `[bv];[bv][1:v]overlay=W-w-44:40:enable='between(t,${(placed[0].start - 0.3).toFixed(2)},${(end + 0.4).toFixed(2)})',format=yuv420p[v]` : ',format=yuv420p[v]');
    const a = s.voiced
      ? `[0:a]aformat=sample_rates=48000:channel_layouts=stereo,apad=whole_dur=${L}[a]`
      : placed.map((p, j) => `[${firstAudio + j}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=${Math.round(p.start * 1000)}:all=1[a${j}]`).join(';') +
        `;${placed.map((_, j) => `[a${j}]`).join('')}amix=inputs=${placed.length}:normalize=0:dropout_transition=0,apad=whole_dur=${L}[a]`;
    ff([...input, ...(lbl ? ['-loop', '1', '-i', lbl] : []), ...audioIn,
        '-filter_complex', `${v};${a}`, '-map', '[v]', '-map', '[a]', '-t', L, '-r', '60',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
        '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', seg.replace('.mp4', '.mkv')]);
    parts.push(seg.replace('.mp4', '.mkv'));
    plan.push({ i, name: s.slide ? `slide ${s.slide}` : s.clip, len, chapter: s.chapter });
    console.log(`${String(i).padStart(2)} ${(s.slide ? 'slide ' + s.slide : s.clip).padEnd(9)} ${len.toFixed(2)}s`, placed.map((p) => `${p.key}@${p.start.toFixed(2)}`).join(' '));
  }
  await browser.close();
  server.close();

  // 장면마다 시작 시각 — 겹쳐 넘기는 만큼 앞당겨진다
  const lens = parts.map(dur);
  const at = []; let acc = 0;
  for (let i = 0; i < lens.length; i++) { at.push(i ? acc - i * XF : 0); acc += lens[i]; }
  const total = acc - (lens.length - 1) * XF;
  console.log('total', total.toFixed(2) + 's');
  if (total > LIMIT) throw new Error(`10분을 넘는다 — ${total.toFixed(1)}초`);

  // 잇기 — 그림은 xfade, 소리는 acrossfade 로 0.3초 겹친다. 장 끝과 시작은 말이 없는 자리라 겹쳐도 말이 안 겹친다
  const inV = parts.map((_, i) => `[${i}:v]settb=AVTB,setpts=PTS-STARTPTS[v${i}]`);
  const inA = parts.map((_, i) => `[${i}:a]asetpts=PTS-STARTPTS[a${i}]`);
  const chainV = [], chainA = [];
  let lv = 'v0', la = 'a0', off = 0;
  for (let i = 1; i < parts.length; i++) {
    off += lens[i - 1] - XF;
    chainV.push(`[${lv}][v${i}]xfade=transition=fade:duration=${XF}:offset=${off.toFixed(3)}[x${i}]`); lv = `x${i}`;
    chainA.push(`[${la}][a${i}]acrossfade=d=${XF}:c1=tri:c2=tri[y${i}]`); la = `y${i}`;
  }
  const joined = path.join(BUILD, 'joined.mkv');
  ff([...parts.flatMap((p) => ['-i', p]), '-filter_complex', [...inV, ...inA, ...chainV, ...chainA].join(';'),
      '-map', `[${lv}]`, '-map', `[${la}]`, '-r', '60',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
      '-c:a', 'pcm_s16le', joined]);

  // 소리를 -16 LUFS 로(말소리 웹 기준). 두 번 재서 맞춘다
  const meas = spawnSync('ffmpeg', ['-hide_banner', '-i', joined, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], { encoding: 'utf8' }).stderr;
  const j = JSON.parse(meas.slice(meas.lastIndexOf('{'), meas.lastIndexOf('}') + 1));
  ff(['-i', joined, '-c:v', 'copy', '-af',
      `loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:measured_I=${j.input_i}:measured_TP=${j.input_tp}:measured_LRA=${j.input_lra}:measured_thresh=${j.input_thresh}`,
      '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', OUT]);

  // 자막(.srt) · 챕터 · 썸네일
  const srt = subs.map(([i, a, b, t], n) => `${n + 1}\n${ts(at[i] + a, ',')} --> ${ts(at[i] + b, ',')}\n${t.replace(/[“”]/g, '"')}\n`).join('\n');
  fs.writeFileSync(OUT.replace('.mp4', '.srt'), srt);
  const chapters = plan.filter((p) => p.chapter).map((p) => `${ts(at[p.i])} ${p.chapter}`);
  fs.writeFileSync(path.join(HERE, 'chapters.txt'), chapters.join('\n') + '\n');
  // 유튜브에 붙일 제목 · 설명 — 목소리가 AI 합성임을 설명란 첫머리에 밝힌다
  fs.writeFileSync(path.join(HERE, 'youtube.txt'), [
    '제목', 'CADLens — 실기 도면 자동 검사 | 팀 네이놈 2차 발표 (10분)', '',
    '설명',
    '2026 전국마이스터고 스타프로젝트 · NAVER OGQ마켓 AI Competition 2차 제출 — 구미전자공업고등학교 팀 네이놈',
    '',
    'CADLens 는 전산응용기계제도기능사 실기처럼 그린 도면(DWG · DXF)을 올리면 오작(실격) 사유와 감점 자리를 도면 위 번호로 보여 주는 검사기입니다.',
    '▶ 써 보기 (회원가입 없음): https://naverogq.onrender.com',
    '▶ 코드 · 지표 · 겪은 문제 기록: https://github.com/ritual1127/naverogq',
    '',
    '※ 이 영상의 목소리는 모두 AI 합성입니다. 팀원 네 명이 남긴 소개 음성을 바탕으로 Qwen3-TTS 가 대본을 읽었고, 말하는 동안 화면 오른쪽 위에 "○○ 목소리 · AI 음성"을 띄웠습니다.',
    '※ 숫자는 2026-10-18 13:35 기준입니다(공개 지표 /api/stats · docs/metrics.md). 슬라이드마다 출처를 적었습니다.',
    '',
    ...chapters, ''].join('\n'));
  ff(['-i', path.join(BUILD, 'slide01.png'), '-vf', 'scale=1280:720:flags=lanczos', '-q:v', '2', path.join(HERE, 'thumb.jpg')]);
  console.log('->', OUT, dur(OUT).toFixed(2) + 's');
  console.log(chapters.join('\n'));
})().catch((e) => { console.error(e); process.exit(1); });
