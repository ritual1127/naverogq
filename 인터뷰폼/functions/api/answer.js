// 답변 하나를 D1에 넣고(POST), 열쇠를 아는 사람만 통계로 본다(GET).
// 이름·학번·도면 파일은 여기 들어오지 않는다. 들어온 답만 그대로 남긴다.
//
// 1000건이 쌓여도 통계 화면은 SQL 여섯 번이면 끝난다. 답 하나씩 읽지 않는다.
// 표는 GROUP BY 로 세고, 직접 적은 것과 한 사람씩 보기는 쪽으로 나눈다.

// [키, 화면에 쓸 이름, 종류] — 순서가 곧 통계 화면의 순서다. 폼의 name 과 같아야 한다.
// pick = 하나 고르기 · multi = 여러 개 고르기 · note = 직접 적기
const FIELDS = [
  ["grade", "학년", "pick"],
  ["cert", "전산응용기계제도기능사", "pick"],
  ["cad2d", "2D 프로그램", "pick"],
  ["cad3d", "3D 프로그램", "pick"],
  ["practiced", "그려 본 도면", "pick"],
  ["freq", "그리는 빈도", "pick"],

  ["t2d", "2D 부품도에 걸리는 시간", "pick"],
  ["t3d", "3D 등각투상도에 걸리는 시간", "pick"],
  ["tplot", "출력에 걸리는 시간", "pick"],
  ["timeout", "시간 모자란 적", "pick"],

  ["missed", "빠뜨리거나 틀린 것", "multi"],
  ["missed_etc", "목록에 없던 것", "note"],

  ["recent_one", "제일 최근에 틀린 것", "note"],
  ["when_found", "그걸 언제 알았나", "pick"],
  ["what_did", "알고 나서 한 것", "pick"],
  ["redraw_time", "고치는 데 걸린 시간", "pick"],
  ["lost_score", "깎인 점수", "pick"],
  ["repeat", "처음 있는 일인가", "pick"],

  ["check_how", "지금 확인하는 방법", "multi"],
  ["check_time", "확인에 쓰는 시간", "pick"],
  ["caught", "확인해서 실제로 잡아 봤나", "pick"],

  ["spent", "안 틀리려고 써 본 것", "multi"],
  ["spent_time", "쓴 시간", "pick"],
  ["spent_money", "쓴 돈", "pick"],

  ["ks", "KS 규격집에서 자주 찾는 것", "multi"],
  ["slowest", "제일 오래 걸리는 작업", "pick"],
  ["annoying", "제일 짜증 나는 순간", "pick"],
  ["teacher", "선생님이 제일 많이 하는 지적", "note"],

  ["file", "도면 파일 줄 수 있나", "pick"],
  ["free", "하고 싶은 말", "note"],
];
const LABEL = Object.fromEntries(FIELDS.map(([k, l]) => [k, l]));

const MAX = 2000;        // 한 칸 최대 글자수
const MAX_PICKS = 60;    // 한 항목에서 고를 수 있는 최대 개수
const PER_PAGE = 20;     // 한 사람씩 보기 — 한 쪽에 몇 명
const NOTES_SHOWN = 50;  // 직접 적은 것 — 항목마다 최근 몇 줄
const NOTES_COPIED = 30; // 복사 글에 넣는 줄 수
// 이 중 하나라도 없으면 저장하지 않는다. 빈 줄이 쌓이면 나중에 못 읽는다.
const NEED_ONE_OF = ["recent_one", "missed", "when_found", "spent"];

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return new Response("본문이 JSON이 아니다", { status: 400 });
  }
  if (!body || typeof body !== "object") {
    return new Response("본문이 비었다", { status: 400 });
  }

  const answer = {};
  const picks = [];   // [field, value]
  const notes = [];   // [field, text]
  for (const [k, , kind] of FIELDS) {
    const v = body[k];
    if (kind === "multi") {
      if (!Array.isArray(v)) continue;
      if (v.length > MAX_PICKS) {
        return new Response(`${k} 가 ${MAX_PICKS}개를 넘는다`, { status: 413 });
      }
      const got = v.filter((x) => typeof x === "string" && x.trim() && x.length <= 200)
        .map((x) => x.trim());
      if (!got.length) continue;
      answer[k] = got;
      for (const one of got) picks.push([k, one]);
    } else {
      if (typeof v !== "string") continue;
      if (v.length > MAX) {
        return new Response(`${k} 가 ${MAX}자를 넘는다`, { status: 413 });
      }
      const t = v.trim();
      if (!t) continue;
      answer[k] = t;
      (kind === "note" ? notes : picks).push([k, t]);
    }
  }
  if (!NEED_ONE_OF.some((k) => answer[k])) {
    return new Response("답이 하나도 없다", { status: 400 });
  }

  answer.at = new Date().toISOString();
  const ins = await env.DB.prepare("INSERT INTO answers (at, data) VALUES (?, ?)")
    .bind(answer.at, JSON.stringify(answer)).run();
  const id = ins.meta.last_row_id;

  const rows = [
    ...picks.map(([f, v]) =>
      env.DB.prepare("INSERT INTO picks (answer_id, field, value) VALUES (?, ?, ?)")
        .bind(id, f, v)),
    ...notes.map(([f, t]) =>
      env.DB.prepare("INSERT INTO notes (answer_id, field, text) VALUES (?, ?, ?)")
        .bind(id, f, t)),
  ];
  if (rows.length) await env.DB.batch(rows);

  return Response.json({ ok: true });
}

// 강한 신호 — 이미 시간이나 돈을 쓴 사람. "아무것도 안 씀"만 고른 사람은 아니다.
const STRONG_SQL = `SELECT COUNT(DISTINCT answer_id) AS c FROM picks WHERE
  (field='spent'       AND value<>'아무것도 안 씀') OR
  (field='spent_time'  AND value<>'안 씀')        OR
  (field='spent_money' AND value<>'안 씀')`;

const LATE = ["내고 나서 내가", "선생님이 말해 줌", "친구가 말해 줌", "점수 나오고 알았음"];

async function load(env, page) {
  const [total, tally, answered, strong, noteRows, rawRows] = await env.DB.batch([
    env.DB.prepare("SELECT COUNT(*) AS n, MAX(at) AS last FROM answers"),
    env.DB.prepare(
      "SELECT field, value, COUNT(*) AS c FROM picks GROUP BY field, value ORDER BY c DESC"),
    env.DB.prepare(
      "SELECT field, COUNT(DISTINCT answer_id) AS c FROM picks GROUP BY field"),
    env.DB.prepare(STRONG_SQL),
    env.DB.prepare(`SELECT field, text FROM (
        SELECT field, text, ROW_NUMBER() OVER (PARTITION BY field ORDER BY answer_id DESC) AS rn
        FROM notes) WHERE rn <= ?`).bind(NOTES_SHOWN),
    env.DB.prepare("SELECT id, at, data FROM answers ORDER BY id DESC LIMIT ? OFFSET ?")
      .bind(PER_PAGE, page * PER_PAGE),
  ]);

  const counts = new Map();     // field -> [[value, c], ...]
  for (const r of tally.results) {
    if (!counts.has(r.field)) counts.set(r.field, []);
    counts.get(r.field).push([r.value, r.c]);
  }
  const base = Object.fromEntries(answered.results.map((r) => [r.field, r.c]));
  const notes = new Map();      // field -> [text, ...]
  for (const r of noteRows.results) {
    if (!notes.has(r.field)) notes.set(r.field, []);
    notes.get(r.field).push(r.text);
  }
  const pick = (f, v) => (counts.get(f) || []).find(([x]) => x === v)?.[1] || 0;

  return {
    n: total.results[0].n,
    last: total.results[0].last,
    counts, base, notes,
    strong: strong.results[0].c,
    late: LATE.reduce((s, v) => s + pick("when_found", v), 0),
    nocheck: pick("check_how", "아무것도 안 함"),
    willGive: pick("file", "줄 수 있어"),
    maybeGive: pick("file", "찾아보고 알려 줄게"),
    raw: rawRows.results.map((r) => ({ id: r.id, at: r.at, data: JSON.parse(r.data) })),
    page,
  };
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const key = url.searchParams.get("key");
  if (!env.ADMIN_KEY) {
    return new Response("ADMIN_KEY 가 설정되어 있지 않다", { status: 500 });
  }
  // 비밀값을 CLI 로 넣으면 줄바꿈이 붙어 올 수 있어 양쪽을 다듬어 비교한다.
  if (!key || key.trim() !== env.ADMIN_KEY.trim()) {
    return new Response("열쇠가 틀렸다", { status: 401 });
  }

  const format = url.searchParams.get("format");
  const page = Math.max(0, parseInt(url.searchParams.get("p") || "0", 10) || 0);

  if (format === "json") {
    const rows = await env.DB.prepare(
      "SELECT id, at, data FROM answers ORDER BY id DESC LIMIT ? OFFSET ?")
      .bind(PER_PAGE * 5, page * PER_PAGE * 5).all();
    return Response.json(rows.results.map((r) => ({ id: r.id, ...JSON.parse(r.data) })));
  }

  const d = await load(env, page);
  if (format === "md") {
    return new Response(report(d), {
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }
  return new Response(page_(d, key), {
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

const esc = (s) => String(s ?? "").replace(/[&<>"]/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (n, d) => (d ? Math.round((n / d) * 1000) / 10 : 0);
const when = (s) => String(s || "").slice(0, 16).replace("T", " ");

// ── AI에 붙여넣는 글 ────────────────────────────────────────────────
function report(d) {
  const L = [];
  L.push("아래는 특성화고 기계과 학생들에게 받은 설문 결과다.");
  L.push("전산응용기계제도(2D 부품도 + 3D 등각투상도, 실기 5시간)를 그릴 때");
  L.push("무엇을 빠뜨리는지, 언제 알아채는지, 지금 무엇으로 확인하는지를 물었다.");
  L.push("무엇이 가장 큰 문제인지, 우리가 놓친 패턴이 있는지 짚어 달라.");
  L.push("");
  L.push(`# 설문 통계 — 응답 ${d.n}건 (마지막 ${when(d.last)} UTC)`);
  L.push("");
  L.push("## 요약");
  L.push(`- 강한 신호(이미 시간이나 돈을 쓴 사람): ${d.strong}명 (${pct(d.strong, d.n)}%)`);
  L.push(`- 낸 뒤에야 틀린 걸 알았다: ${d.late}명 (${pct(d.late, d.n)}%)`);
  L.push(`- 제출 전 확인을 아예 안 한다: ${d.nocheck}명 (${pct(d.nocheck, d.n)}%)`);
  L.push(`- 도면 파일을 줄 수 있다: ${d.willGive}명 (찾아본다 ${d.maybeGive}명)`);
  L.push("");
  L.push("## 고른 것");
  for (const [k, label, kind] of FIELDS) {
    if (kind === "note") continue;
    const rows = d.counts.get(k) || [];
    if (!rows.length) continue;
    const b = d.base[k] || 0;
    L.push("");
    L.push(`### ${label} (${kind === "multi" ? "여러 개 고르기" : "하나 고르기"}, 답한 사람 ${b}명)`);
    for (const [v, c] of rows) L.push(`- ${v}: ${c}명 (${pct(c, b)}%)`);
  }
  L.push("");
  L.push("## 직접 적은 것 (사람 말 그대로)");
  for (const [k, label, kind] of FIELDS) {
    if (kind !== "note") continue;
    const lines = d.notes.get(k) || [];
    L.push("");
    L.push(`### ${label} (최근 ${Math.min(lines.length, NOTES_COPIED)}줄 / 전체 ${lines.length}줄)`);
    if (!lines.length) L.push("- (없음)");
    for (const t of lines.slice(0, NOTES_COPIED)) L.push(`- "${t.replace(/"/g, "'")}"`);
  }
  L.push("");
  L.push("※ 강한 신호는 이미 시간이나 돈을 쓴 사람만 센다. \"나오면 써 볼게요\"는 신호가 아니다.");
  return L.join("\n");
}

// ── 화면 ────────────────────────────────────────────────────────────
function bars(d, k, kind) {
  const rows = d.counts.get(k) || [];
  if (!rows.length) return `<p class="none">아직 아무도 안 골랐다</p>`;
  const b = d.base[k] || 0;
  const top = rows[0][1];
  return `<table class="bars">` + rows.map(([v, c]) => `
    <tr><th>${esc(v)}</th>
      <td class="b"><span style="width:${top ? (c / top) * 100 : 0}%"></span></td>
      <td class="c">${c}명 <em>${pct(c, b)}%</em></td></tr>`).join("") + `</table>
    <p class="base">${kind === "multi" ? "여러 개 고르기" : "하나 고르기"} · 답한 사람 ${b}명</p>`;
}

function page_(d, key) {
  const N = d.n;
  const q = (p) => `?key=${encodeURIComponent(key)}&amp;p=${p}`;
  const sigNote = N === 0 ? "아직 없다"
    : d.strong === 0 ? "0명 — 강의 기준으로는 <b>문제를 다시 골라야 한다</b>"
    : d.strong < Math.ceil(N * 0.6) ? "5명 중 3명 기준에 못 미친다"
    : "기준을 넘는다";

  const kpi = (label, num, note) =>
    `<div class="kpi"><b>${num}</b><span>${esc(label)}</span><i>${note}</i></div>`;

  const sections = FIELDS.filter(([, , t]) => t !== "note").map(([k, l, t]) =>
    `<section><h3>${esc(l)}</h3>${bars(d, k, t)}</section>`).join("");

  const notes = FIELDS.filter(([, , t]) => t === "note").map(([k, l]) => {
    const lines = d.notes.get(k) || [];
    return `<section><h3>${esc(l)} <em>최근 ${lines.length}줄</em></h3>` +
      (lines.length
        ? `<ol class="lines">${lines.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`
        : `<p class="none">아직 없다</p>`) + `</section>`;
  }).join("");

  const isStrong = (a) => (a.spent || []).some((x) => x !== "아무것도 안 씀") ||
    (a.spent_time && a.spent_time !== "안 씀") ||
    (a.spent_money && a.spent_money !== "안 씀");

  const raw = d.raw.map((r) => `
    <details><summary>#${r.id} · ${esc(when(r.at))} UTC${
      isStrong(r.data) ? '<span class="tag">강한 신호</span>' : ""}</summary>
      ${FIELDS.filter(([k]) => r.data[k] !== undefined).map(([k]) => {
        const v = r.data[k];
        return `<p class="one"><b>${esc(LABEL[k])}</b> ${
          esc(Array.isArray(v) ? v.join(" · ") : v)}</p>`;
      }).join("")}
    </details>`).join("");

  const first = d.page * PER_PAGE + 1;
  const last = d.page * PER_PAGE + d.raw.length;
  const nav = `<p class="nav">
    ${d.page > 0 ? `<a href="${q(d.page - 1)}">← 앞</a>` : `<span>← 앞</span>`}
    <b>${N ? `${first}–${last}` : 0} / ${N}</b>
    ${last < N ? `<a href="${q(d.page + 1)}">뒤 →</a>` : `<span>뒤 →</span>`}</p>`;

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>인터뷰 통계 · ${N}건</title>
<style>
 :root{--bg:#f4f4f2;--card:#fff;--ink:#17181a;--dim:#65696f;--line:#e0e0dd;
   --soft:#f0f0ed;--accent:#1f6feb;--bar:#1f6feb22}
 @media(prefers-color-scheme:dark){:root{--bg:#131418;--card:#1c1e23;--ink:#eceef2;
   --dim:#a3a8b2;--line:#2f323a;--soft:#24262c;--accent:#5b9cff;--bar:#5b9cff2e}}
 body{margin:0;background:var(--bg);color:var(--ink);
   font:16px/1.6 -apple-system,"Pretendard","Malgun Gothic",sans-serif}
 .wrap{max-width:840px;margin:0 auto;padding:26px 18px 70px}
 h1{font-size:21px;margin:0 0 4px}
 .sub{color:var(--dim);font-size:14px;margin:0 0 18px}
 .tools{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
 .tools button,.tools a{border:1px solid var(--line);background:var(--card);color:var(--ink);
   border-radius:10px;padding:10px 14px;font:inherit;font-size:14px;cursor:pointer;
   text-decoration:none}
 .tools button.main{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
 .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin:0 0 10px}
 .kpi{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:14px}
 .kpi b{display:block;font-size:25px;line-height:1.2}
 .kpi span{display:block;font-size:13.5px;color:var(--dim)}
 .kpi i{display:block;font-style:normal;font-size:12.5px;color:var(--accent);margin-top:4px}
 h2{font-size:14px;color:var(--accent);margin:30px 0 10px}
 section{background:var(--card);border:1px solid var(--line);border-radius:13px;
   padding:14px 16px;margin:0 0 10px}
 section h3{font-size:14.5px;margin:0 0 10px}
 section h3 em{font-style:normal;color:var(--dim);font-weight:400}
 table.bars{width:100%;border-collapse:collapse}
 .bars th{text-align:left;font-weight:500;font-size:14px;padding:3px 10px 3px 0;
   width:38%;vertical-align:middle}
 .bars td.b{padding:3px 0}
 .bars td.b span{display:block;height:16px;border-radius:5px;background:var(--bar);
   border-left:3px solid var(--accent);min-width:3px}
 .bars td.c{text-align:right;font-size:13.5px;color:var(--dim);white-space:nowrap;padding-left:10px}
 .bars td.c em{font-style:normal;color:var(--accent)}
 .base{font-size:12.5px;color:var(--dim);margin:8px 0 0}
 .none{color:var(--dim);font-size:14px;margin:0}
 ol.lines{margin:0;padding-left:22px}
 ol.lines li{margin:3px 0;font-size:15px}
 details{background:var(--card);border:1px solid var(--line);border-radius:13px;
   padding:12px 16px;margin:0 0 8px}
 summary{cursor:pointer;font-size:14.5px}
 .tag{background:var(--soft);border:1px solid var(--accent);color:var(--accent);
   border-radius:999px;padding:1px 8px;font-size:12px;margin-left:6px}
 .one{margin:6px 0;font-size:14.5px;color:var(--dim)}
 .one b{color:var(--ink);font-weight:600;margin-right:6px}
 .nav{display:flex;gap:14px;align-items:center;justify-content:center;
   font-size:14px;color:var(--dim);margin:14px 0 0}
 .nav a{color:var(--accent);text-decoration:none}
 .nav span{opacity:.35}
 .foot{color:var(--dim);font-size:13px;margin-top:26px}
 #rep{position:absolute;left:-9999px;top:0}
</style></head><body><div class="wrap">
<h1>인터뷰 통계</h1>
<p class="sub">받은 답 ${N}건 · 마지막 ${N ? esc(when(d.last)) + " UTC" : "-"}</p>

<div class="tools">
  <button class="main" id="copy" type="button">전체 지표 복사 (AI에 붙여넣기)</button>
  <a href="?key=${encodeURIComponent(key)}&amp;format=md" target="_blank">글로 보기</a>
  <a href="?key=${encodeURIComponent(key)}&amp;format=json" target="_blank">JSON</a>
</div>

<div class="kpis">
  ${kpi("받은 답", N, "5건이 W2 산출물")}
  ${kpi("강한 신호", d.strong, sigNote)}
  ${kpi("낸 뒤에야 알았다", d.late, N ? pct(d.late, N) + "%" : "-")}
  ${kpi("확인을 아예 안 함", d.nocheck, N ? pct(d.nocheck, N) + "%" : "-")}
  ${kpi("도면 준다고 함", d.willGive, "찾아본다 " + d.maybeGive + "명")}
</div>

<h2>고른 것 — 항목별</h2>
${sections}

<h2>직접 적은 것 — 그대로</h2>
${notes}

<h2>한 사람씩 보기</h2>
${raw || '<p class="none">아직 없다.</p>'}
${nav}

<p class="foot">강한 신호는 <b>이미 시간이나 돈을 쓴 사람</b>이다. "나오면 써 볼게요"는 신호가 아니다.</p>

<textarea id="rep" readonly>${esc(report(d))}</textarea>
<script>
document.getElementById('copy').addEventListener('click', async function () {
  var t = document.getElementById('rep'), b = this;
  try {
    await navigator.clipboard.writeText(t.value);
  } catch (e) {
    t.style.position = 'static'; t.style.left = '0';
    t.select(); document.execCommand('copy');
    t.style.position = 'absolute'; t.style.left = '-9999px';
  }
  b.textContent = '복사됐다 — 그대로 붙여넣어';
  setTimeout(function () { b.textContent = '전체 지표 복사 (AI에 붙여넣기)'; }, 2500);
});
</script>
</div></body></html>`;
}
