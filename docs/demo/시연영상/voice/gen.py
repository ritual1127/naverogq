# 영상 대사 2판 — 한 가지 길(Chatterbox 가 그 사람 녹음의 말투로 바로 읽기)로 통일하고, 그 사람의 실제 말 빠르기에 맞춘다.
# 빠르기 = 문장 하나를 말하는 동안의 음절/초(녹음의 문장마다 잰 값의 중앙값). 후보 8개 → 받아쓰기 오류 0 → 닮음 · 자연스러움 · 빠르기 차이로 고름
import os, sys, re, json, random, subprocess, statistics as st
import torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import numpy as np, librosa, soundfile as sf, torchaudio as ta
sys.stdout.reconfigure(encoding="utf-8")
REC = {"andaeyeol": "01_안대열.m4a", "jangwooyoung": "02_장우영 녹음.m4a", "parkjiwan": "03_박지완 녹음.m4a", "kimseungjun": "04_김승준 녹음.m4a"}
LINES = [
    ("v1", "andaeyeol", "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다."),
    ("v2", "jangwooyoung", "그러면 실격 사유는 오른쪽에, 빠뜨린 치수 자리는 도면 위에 번호로 표시합니다."),
    ("v3", "parkjiwan", "번호를 누르면, 그 자리를 바로 확대해서 보여 줍니다."),
    ("v4a", "kimseungjun", "지난 데모데이 이후에 새로 만든 기능, 수정 예시입니다."),
    ("v4b", "kimseungjun", "누르면, 빠진 치수를 도면에서 읽은 좌표 그대로 초록색으로 그려 줍니다."),
    ("v4c", "kimseungjun", "에이아이가 그림을 지어내는 게 아니라서, 위치와 값이 정확합니다."),
]
K = 8
OUT, FIN = "cand2", "final2"
os.makedirs(OUT, exist_ok=True); os.makedirs(FIN, exist_ok=True)
syl = lambda s: len(re.findall(r"[가-힣]", s)) + len(re.findall(r"[A-Za-z]", s)) * 0.6 + len(re.findall(r"[0-9]", s)) * 1.2
norm = lambda s: re.sub(r"[^가-힣a-z0-9]", "", s.lower().replace("ai", "에이아이"))
def cer(ref, hyp):
    r, h = norm(ref), norm(hyp); d = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        p, d[0] = d[0], i
        for j, hc in enumerate(h, 1): p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (rc != hc))
    return d[len(h)] / max(1, len(r))

from faster_whisper import WhisperModel
asr = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
def words(y_or_path):
    segs, _ = asr.transcribe(y_or_path, language="ko", word_timestamps=True, beam_size=5)
    return [w for s in segs for w in s.words if w.word.strip()]

# 1. 그 사람의 문장별 말 빠르기
target = {}
for spk, f in REC.items():
    ws = words(f"C:/Users/smile/OneDrive/Desktop/녹음파일들/{f}")
    rates, cur = [], []
    for w in ws:
        cur.append(w)
        if re.search(r"[.?!]$", w.word.strip()):
            span = cur[-1].end - cur[0].start
            if span > 1.5 and "만나요" not in "".join(x.word for x in cur): rates.append(sum(syl(x.word) for x in cur) / span)
            cur = []
    target[spk] = round(st.median(rates), 2)
print("문장 하나를 말하는 빠르기(음절/초)", target, flush=True)

# 2. 후보
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
tts = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
for key, spk, text in LINES:
    for s in range(K):
        p = f"{OUT}/{key}_{s}.wav"
        if os.path.exists(p): continue
        torch.manual_seed(s); random.seed(s); np.random.seed(s)
        wav = tts.generate(text, language_id="ko", audio_prompt_path=f"refs/{spk}.wav", exaggeration=0.5, cfg_weight=0.5, temperature=0.8)
        ta.save(p, wav.cpu(), tts.sr)
del tts; torch.cuda.empty_cache()

# 3. 평가
from transformers import AutoFeatureExtractor, WavLMForXVector
fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()
utmos = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True).cuda().eval()
def emb(y):
    x = fe(y, sampling_rate=16000, return_tensors="pt").to("cuda")
    with torch.no_grad(): return torch.nn.functional.normalize(sv(**x).embeddings, dim=-1)[0]
refemb = {spk: emb(librosa.load(f"refs/{spk}.wav", sr=16000)[0]) for spk in REC}
picks = {}
for key, spk, text in LINES:
    rows = []
    for s in range(K):
        y, _ = librosa.load(f"{OUT}/{key}_{s}.wav", sr=16000)
        ws = words(y); hyp = "".join(w.word for w in ws)
        rate = syl(text.replace("에이아이", "AI")) / max(0.1, ws[-1].end - ws[0].start) if ws else 0
        with torch.no_grad(): mos = float(utmos(torch.tensor(y)[None].cuda(), 16000)[0])
        r = {"s": s, "cer": round(cer(text, hyp), 3), "sim": round(float(emb(y) @ refemb[spk]), 3), "mos": round(mos, 2),
             "rate": round(rate, 2), "dev": round(rate / target[spk] - 1, 3), "hyp": hyp}
        r["score"] = round(r["sim"] + 0.3 * (r["mos"] - 3) - 1.0 * abs(r["dev"]), 3)
        rows.append(r)
    ok = [r for r in rows if r["cer"] == 0] or rows
    best = max(ok, key=lambda r: r["score"])
    picks[key] = best
    print(key, spk, "목표", target[spk], "→ 고름", {k: best[k] for k in ("s", "cer", "sim", "mos", "rate", "dev")}, flush=True)
    for r in sorted(rows, key=lambda r: -r["score"])[:3]: print("    ", {k: r[k] for k in ("s", "cer", "sim", "mos", "rate", "dev")})

# 4. 빠르기를 그 사람에 맞추고(±3% 넘으면 음높이는 그대로 늘이거나 줄임) · 무음 정리 · -18 LUFS
for key, spk, text in LINES:
    b = picks[key]; src = f"{OUT}/{key}_{b['s']}.wav"
    y, sr = sf.read(src, dtype="float32"); y = y if y.ndim == 1 else y.mean(axis=1)
    fr = int(0.01 * sr); rms = np.sqrt(np.convolve(y ** 2, np.ones(fr) / fr, mode="same"))
    on = np.where(rms > rms.max() * 10 ** (-38 / 20))[0]
    y = y[max(0, on[0] - int(0.08 * sr)): min(len(y), on[-1] + int(0.15 * sr))]
    sf.write(f"{FIN}/{key}_raw.wav", y, sr)
    tempo = max(0.88, min(1.12, target[spk] / b["rate"])) if abs(b["dev"]) > 0.03 else 1.0
    af = (f"atempo={tempo:.4f}," if tempo != 1.0 else "") + "aresample=48000"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f"{FIN}/{key}_raw.wav", "-af", af, "-ac", "1", f"{FIN}/{key}_t.wav"], check=True)
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", f"{FIN}/{key}_t.wav", "-af", "loudnorm=I=-18:TP=-2:LRA=7:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    ln = (f"loudnorm=I=-18:TP=-2:LRA=7:linear=true:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']},afade=t=in:d=0.02,areverse,afade=t=in:d=0.04,areverse")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f"{FIN}/{key}_t.wav", "-af", ln, "-ar", "48000", "-ac", "1", f"{FIN}/{key}.wav"], check=True)
    picks[key]["tempo"] = round(tempo, 4)

# 5. 다 만든 파일을 다시 받아써서 확인 · 낱말 시각
res = {}
for key, spk, text in LINES:
    ws = words(f"{FIN}/{key}.wav"); hyp = "".join(w.word for w in ws)
    dur = sf.info(f"{FIN}/{key}.wav").duration
    rate = syl(text.replace("에이아이", "AI")) / (ws[-1].end - ws[0].start)
    res[key] = {"spk": spk, "dur": round(dur, 3), "cer": round(cer(text, hyp), 3), "rate": round(rate, 2), "target": target[spk],
                "tempo": picks[key]["tempo"], "pick": picks[key]["s"], "sim": picks[key]["sim"], "mos": picks[key]["mos"],
                "words": [(w.word.strip(), round(w.start, 2), round(w.end, 2)) for w in ws]}
    print("FINAL", key, {k: v for k, v in res[key].items() if k != "words"})
    print("      ", " ".join(f"{w}[{a}-{b}]" for w, a, b in res[key]["words"]))
json.dump({"target": target, "lines": res}, open(f"{FIN}/report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
