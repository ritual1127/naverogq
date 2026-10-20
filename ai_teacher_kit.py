"""교사 대조 키트 — 실제 수험생 도면마다 AI 가 매긴 투상도 30점 지적을 선생님이 맞음 · 틀림으로 표시하는 HTML 한 장.

    python ai_teacher_kit.py                 # 실제도면/labels.json 의 23장
    python ai_teacher_kit.py A01,A05,3축     # 몇 장만

도면 그림이 들어가므로 저장소 밖(`실제도면/교사대조/`, .gitignore)에만 만든다. 공개 링크로 올리지 않고 선생님께
파일로 드린다. AI 결과는 공개 서버와 같은 `ai_review.judge()` 로 받는다 — 캐시를 쓰므로 다시 만들어도 뉴런을
안 쓴다. 답변 · 번역은 부르지 않는다(도면 한 장에 채점 한 번, 60 ~ 110 뉴런).

선생님이 「결과 저장」을 누르면 JSON 이 내려받아진다. 그 파일을 `ai_teacher_compare.py` 에 넣으면 지표가 나온다.
"""
import base64
import datetime
import hashlib
import html
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "실제도면", "교사대조")


def _jpeg(png, longest=1600):
    from PIL import Image

    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.thumbnail((longest, longest))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def collect(names):
    import ai_bench
    ai_bench.load_env()
    import ai_review
    import dwg

    drawings = {}
    for name in names:
        path = os.path.join(ROOT, "실제도면", "원본", name + ".dxf")
        facts = dwg.analyze(path)
        out = ai_review.judge(facts, timeout=45, defer=True)
        if out is None:
            print(f"{name}: AI 채점 실패 — 건너뜀", flush=True)
            continue
        out.pop("later", None)
        drawings[name] = {
            "score": out["score"], "verdict": out.get("verdict", ""), "model": out.get("model"),
            "findings": [{"title": f["title"], "detail": f.get("detail", ""), "fix": f.get("fix", ""),
                          "deduct": f.get("deduct", 0), "severity": f.get("severity", "")}
                         for f in out["findings"]],
            "image": _jpeg(ai_review.png_of(facts)),
        }
        print(f"{name}: AI {out['score']}/30 · 지적 {len(out['findings'])}개", flush=True)
    return drawings


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>CADLens 교사 대조 — 투상도 30점</title>
<style>
body{margin:0;background:#f4f6f9;color:#1d232b;font:15px/1.7 "Malgun Gothic","Apple SD Gothic Neo",sans-serif;word-break:keep-all}
.wrap{max-width:1000px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:22px;margin:0 0 6px}.lead{color:#4a5260;margin:0 0 14px}
.bar{position:sticky;top:0;z-index:2;display:flex;gap:8px;flex-wrap:wrap;align-items:center;background:#fff;
  border:1px solid #dde3ec;border-radius:12px;padding:10px 12px;margin:0 0 16px}
.bar input{font:inherit;padding:6px 10px;border:1px solid #cfd6e0;border-radius:8px}
.bar .sp{margin-left:auto;color:#4a5260;font-weight:700}
button{font:inherit;font-weight:700;border:0;border-radius:8px;padding:7px 14px;background:#2a4a7a;color:#fff;cursor:pointer}
button.ghost{background:#fff;color:#2a4a7a;border:1px solid #b9c7dd}
.card{background:#fff;border:1px solid #dde3ec;border-radius:14px;padding:16px;margin:0 0 18px;break-inside:avoid}
.card h2{font-size:18px;margin:0 0 8px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.card h2 small{font-size:14px;color:#4a5260;font-weight:400}
.card img{display:block;width:100%;border:1px solid #e3e8ef;border-radius:8px;background:#fff}
.verdict{margin:10px 0;color:#4a5260}
.f{border-top:1px solid #eef1f5;padding:10px 0}.f b{color:#111}
.f .d{color:#4a5260;font-size:14px}
.marks{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.marks label{border:1px solid #cfd6e0;border-radius:999px;padding:3px 12px;cursor:pointer;font-size:14px}
.marks input{margin:0 4px 0 0}
.note{width:100%;box-sizing:border-box;margin-top:6px;font:inherit;font-size:14px;padding:6px 10px;border:1px solid #cfd6e0;border-radius:8px}
.own{display:grid;grid-template-columns:auto 1fr;gap:8px 12px;align-items:center;margin-top:12px;padding-top:12px;border-top:2px solid #2a4a7a}
.own input[type=number]{width:90px;font:inherit;padding:6px 10px;border:1px solid #cfd6e0;border-radius:8px}
.own textarea{font:inherit;font-size:14px;min-height:56px;padding:6px 10px;border:1px solid #cfd6e0;border-radius:8px}
.none{color:#1f7a4d;font-weight:700}
@media print{.bar{position:static}.card{page-break-inside:avoid}button{display:none}}
</style></head><body><div class="wrap">
<h1>CADLens 교사 대조 — 「투상도 선택과 배열」 30점</h1>
<p class="lead">선생님, 도면마다 ① AI 지적이 맞는지 고르시고 ② 선생님이 이 도면에 주실 투상도 점수(30점 만점)와
③ AI 가 놓친 것을 적어 주세요. 다 하신 뒤 「결과 저장」을 누르면 파일이 내려받아집니다 — 그 파일을 보내 주시면 됩니다.
도면은 동의를 받아 이름을 지우고 받은 연습 도면입니다. <b>이 파일을 다른 곳에 올리지 말아 주세요.</b>
작성 중인 내용은 이 브라우저에만 저장됩니다.</p>
<div class="bar"><label>검토하신 분 <input id="who" placeholder="예: ○○공고 기계과 선생님"></label>
<button id="save">결과 저장</button><button class="ghost" onclick="print()">인쇄</button><span class="sp" id="done"></span></div>
<div id="list"></div></div>
<script>
const KIT=__KIT__;
const KEY='cadlens.teacher.'+KIT.id;
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const MARK=[['right','맞음'],['wrong','틀림'],['unsure','애매']];
document.getElementById('list').innerHTML=Object.entries(KIT.drawings).map(([n,d])=>`<section class="card" data-n="${esc(n)}">
<h2>${esc(n)} <small>AI ${d.score}/30 · 지적 ${d.findings.length}개</small></h2>
<img src="${d.image}" alt="${esc(n)} 도면" loading="lazy">
<p class="verdict">AI 총평 — ${esc(d.verdict)}</p>
${d.findings.length?d.findings.map((f,i)=>`<div class="f"><b>${i+1}. ${esc(f.title)}</b> · ${f.deduct}점 감점
<div class="d">${esc(f.detail)}${f.fix?' — 고칠 것: '+esc(f.fix):''}</div>
<div class="marks">${MARK.map(([v,t])=>`<label><input type="radio" name="${esc(n)}-${i}" value="${v}">${t}</label>`).join('')}</div>
<input class="note" data-i="${i}" placeholder="틀렸다면 왜인지 짧게(선택)"></div>`).join(''):'<p class="none">AI 지적 없음 (30점)</p>'}
<div class="own"><span>선생님 점수</span><span><input type="number" min="0" max="30" step="1" class="score"> / 30</span>
<span>AI 가 놓친 것</span><textarea class="missed" placeholder="없으면 비워 두세요"></textarea></div></section>`).join('');
function gather(){
  const out={kit:KIT.id,reviewer:document.getElementById('who').value.trim(),saved_at:new Date().toISOString(),drawings:{}};
  document.querySelectorAll('.card').forEach(c=>{const n=c.dataset.n,d=KIT.drawings[n];
    const s=c.querySelector('.score').value;
    out.drawings[n]={score:s===''?null:Math.max(0,Math.min(30,+s)),missed:c.querySelector('.missed').value.trim(),
      findings:d.findings.map((f,i)=>({i,mark:(c.querySelector(`input[name="${CSS.escape(n)}-${i}"]:checked`)||{}).value||null,
        note:(c.querySelector(`.note[data-i="${i}"]`)||{}).value||''}))}});
  return out}
function restore(){
  if(st.reviewer)document.getElementById('who').value=st.reviewer;
  Object.entries(st.drawings||{}).forEach(([n,v])=>{const c=document.querySelector(`.card[data-n="${CSS.escape(n)}"]`);if(!c)return;
    if(v.score!=null)c.querySelector('.score').value=v.score;c.querySelector('.missed').value=v.missed||'';
    (v.findings||[]).forEach(f=>{if(f.mark){const r=c.querySelector(`input[name="${CSS.escape(n)}-${f.i}"][value="${f.mark}"]`);if(r)r.checked=true}
      const t=c.querySelector(`.note[data-i="${f.i}"]`);if(t)t.value=f.note||''})})}
function keep(){st=gather();try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}
  const n=Object.values(st.drawings).filter(d=>d.score!=null).length;
  document.getElementById('done').textContent=`점수 적은 도면 ${n} / ${Object.keys(KIT.drawings).length}`}
restore();keep();document.addEventListener('input',keep);document.addEventListener('change',keep);
document.getElementById('save').onclick=()=>{keep();const b=new Blob([JSON.stringify(st,null,1)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`CADLens_교사대조_${(st.reviewer||'검토').replace(/[\\\\/:*?"<>|\\s]+/g,'_')}_${st.saved_at.slice(0,10)}.json`;a.click()};
</script></body></html>"""


def build(drawings):
    """키트 HTML 과 AI 결과(JSON)를 쓴다. id 는 AI 결과로 만들어 대조할 때 같은 판인지 확인한다."""
    plain = {n: {k: v for k, v in d.items() if k != "image"} for n, d in drawings.items()}
    kit_id = hashlib.sha256(json.dumps(plain, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    kit = {"id": kit_id, "made": datetime.date.today().isoformat(), "drawings": drawings}
    os.makedirs(OUT, exist_ok=True)
    page = PAGE.replace("__KIT__", json.dumps(kit, ensure_ascii=False).replace("</", "<\\/"))
    page_path = os.path.join(OUT, f"CADLens_교사대조_{kit['made']}.html")
    with open(page_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(os.path.join(OUT, f"ai_results_{kit_id}.json"), "w", encoding="utf-8") as fh:
        json.dump({"id": kit_id, "made": kit["made"], "drawings": plain}, fh, ensure_ascii=False, indent=1)
    return page_path, kit_id


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, ROOT)
    if len(sys.argv) > 1:
        names = sys.argv[1].split(",")
    else:
        with open(os.path.join(ROOT, "실제도면", "labels.json"), encoding="utf-8") as fh:
            names = [os.path.splitext(os.path.basename(k))[0] for k in json.load(fh)]
    path, kit_id = build(collect(names))
    print(f"키트 {kit_id}: {path}")
    print(html.escape("선생님께 파일로 드리고, 받은 JSON 은 python ai_teacher_compare.py 로 셉니다."))
