# 네 사람의 실제 말투를 숫자로 — 녹음(7월 소개 영상)을 낱말 시각까지 받아써서 잰다.
import os, sys, re, json, glob, statistics as st, torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding="utf-8")
m = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
syl = lambda s: len(re.findall(r"[가-힣]", s)) + len(re.findall(r"[A-Za-z]", s)) * 0.6 + len(re.findall(r"[0-9]", s)) * 1.2
out = {}
for path in sorted(glob.glob(r"C:/Users/smile/OneDrive/Desktop/녹음파일들/*.m4a")):
    name = re.sub(r"^\d+_|\s*녹음|\.m4a$", "", os.path.basename(path))
    segs, _ = m.transcribe(path, language="ko", word_timestamps=True, beam_size=5)
    ws = [w for s in segs for w in s.words if w.word.strip()]
    ws = [w for w in ws if "다음 영상" not in w.word]
    text = "".join(w.word for w in ws).strip()
    sents = [x.strip() for x in re.split(r"(?<=[.?!])\s+", text) if x.strip()]
    sents = [s for s in sents if "다음 영상" not in s and "만나요" not in s]
    speech = sum(w.end - w.start for w in ws)
    span = ws[-1].end - ws[0].start
    gaps = [(b.start - a.end, a.word.strip()) for a, b in zip(ws, ws[1:])]
    sent_gaps = [g for g, w in gaps if re.search(r"[.?!]$", w)]
    clause_gaps = [g for g, w in gaps if w.endswith(",") or (g > 0.18 and not re.search(r"[.?!]$", w))]
    total = sum(syl(s) for s in sents)
    out[name] = {
        "syll_per_sec_overall": round(total / span, 2), "syll_per_sec_articulation": round(total / speech, 2),
        "sent_len_syll": [round(syl(s)) for s in sents],
        "pause_sentence_ms": [round(g * 1000) for g in sent_gaps],
        "pause_clause_ms": [round(g * 1000) for g in clause_gaps if g > 0.12],
        "endings": [re.sub(r"[.?!]$", "", s.split()[-1]) for s in sents],
        "openers": [s.split()[0] for s in sents],
        "jeohui": len(re.findall(r"저희", text)), "sentences": sents,
    }
    o = out[name]
    print(f"== {name}: {o['syll_per_sec_overall']} 음절/초(쉼 포함) · {o['syll_per_sec_articulation']} 음절/초(말하는 동안)")
    print("   문장 길이(음절)", o["sent_len_syll"], " 문장 사이 쉼(ms)", o["pause_sentence_ms"], " 쉼표 쉼(ms)", o["pause_clause_ms"][:8])
    print("   끝맺음", o["endings"], " 첫 말", o["openers"], " '저희'", o["jeohui"])
json.dump(out, open("style.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 지금 영상 대사(합성)와 견준다
for f in ["p1", "p2", "p3", "p4a", "p4b"]:
    segs, _ = m.transcribe(f"final/{f}.wav", language="ko", word_timestamps=True)
    ws = [w for s in segs for w in s.words if w.word.strip()]
    tot = sum(syl(w.word) for w in ws); span = ws[-1].end - ws[0].start
    print(f"합성 {f}: {round(tot/span, 2)} 음절/초(쉼 포함)")
