# 후보 36개를 늘이고 줄이지 않고(시간 늘이기는 탐지기가 잡는 흠을 남겼다) 다듬은 뒤, 두 탐지기가 모두 "사람" 쪽으로 보는 것을 고른다.
# 다듬기: 앞 = Silero VAD 말 시작 0.10초 전(앞에 따로 떨어진 짧은 소리 덩어리는 숨·딸깍으로 보고 버림), 끝 = 마지막 낱말 뒤 -40dB 0.12초, -18 LUFS
import os, sys, re, json, glob, subprocess
import torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import numpy as np, soundfile as sf, librosa
from faster_whisper import WhisperModel
from faster_whisper.vad import get_speech_timestamps, VadOptions
from transformers import pipeline, AutoFeatureExtractor, WavLMForXVector
sys.stdout.reconfigure(encoding="utf-8")
TXT = {"v1": "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다.", "v2": "그러면 실격 사유는 오른쪽에, 빠뜨린 치수 자리는 도면 위에 번호로 표시합니다.",
       "v3": "번호를 누르면, 그 자리를 바로 확대해서 보여 줍니다.", "v4a": "지난 데모데이 이후에 새로 만든 기능, 수정 예시입니다.",
       "v4b": "누르면, 빠진 치수를 도면에서 읽은 좌표 그대로 초록색으로 그려 줍니다.", "v4c": "에이아이가 그림을 지어내는 게 아니라서, 위치와 값이 정확합니다."}
SPK = {"v1": "andaeyeol", "v2": "jangwooyoung", "v3": "parkjiwan", "v4a": "kimseungjun", "v4b": "kimseungjun", "v4c": "kimseungjun"}
# 다른 대사 묶음 — LINES=lines.json IN=후보폴더 OUT=다듬은폴더 (qgen.py 와 같은 env). 3분 영상은 docs/demo/3분영상/lines.json
if os.environ.get("LINES"):
    L = json.load(open(os.environ["LINES"], encoding="utf-8"))
    TXT, SPK = {k: t for k, (_, t) in L.items()}, {k: s for k, (s, _) in L.items()}
REC ={"andaeyeol": "01_안대열.m4a", "jangwooyoung": "02_장우영 녹음.m4a", "parkjiwan": "03_박지완 녹음.m4a", "kimseungjun": "04_김승준 녹음.m4a"}
TARGET = json.load(open("final2/report.json", encoding="utf-8"))["target"]
PROS = json.load(open("prosody.json", encoding="utf-8"))["person"]
syl = lambda s: len(re.findall(r"[가-힣]", s)) + len(re.findall(r"[A-Za-z]", s)) * 0.6
norm = lambda s: re.sub(r"[^가-힣a-z0-9]", "", s.lower().replace("ai", "에이아이"))
def cer(r, h):
    r, h = norm(r), norm(h); d = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        p, d[0] = d[0], i
        for j, hc in enumerate(h, 1): p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (rc != hc))
    return d[len(h)] / len(r)
asr = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
def words(path):
    segs, _ = asr.transcribe(path, language="ko", word_timestamps=True, beam_size=5)
    return [(w.word.strip(), round(w.start, 2), round(w.end, 2)) for s in segs for w in s.words if w.word.strip()]
OUT = os.environ.get("OUT", "qproc"); os.makedirs(OUT, exist_ok=True)
IN = os.environ.get("IN", "qcand")
def process(src, dst):
    y, sr = sf.read(src, dtype="float32"); y = y if y.ndim == 1 else y.mean(axis=1)
    ts = get_speech_timestamps(librosa.resample(y, orig_sr=sr, target_sr=16000), VadOptions(threshold=0.5, min_speech_duration_ms=120, min_silence_duration_ms=150, speech_pad_ms=0))
    ts = [(t["start"] / 16000, t["end"] / 16000) for t in ts]
    while len(ts) > 1 and ts[0][1] - ts[0][0] < 0.30 and ts[1][0] - ts[0][1] > 0.20: ts = ts[1:]   # 앞의 짧은 덩어리 = 숨 · 딸깍
    a = max(0.0, ts[0][0] - 0.10)
    y = y[int(a * sr):]
    tmp = dst.replace(".wav", "_t.wav"); sf.write(tmp, y, sr)
    lw = words(tmp)[-1][2]
    fr = int(0.01 * sr); rms = np.sqrt(np.convolve(y ** 2, np.ones(fr) / fr, mode="same")); thr = rms.max() * 10 ** (-40 / 20)
    i, i1, need, cut = int(lw * sr), min(len(y), int((lw + 0.35) * sr)), int(0.12 * sr), None
    while i < i1:
        if np.all(rms[i:i + need] < thr): cut = i + int(0.10 * sr); break
        i += fr
    y = y[:min(len(y), cut or i1)].copy()
    n = int(0.02 * sr); y[:n] *= np.linspace(0, 1, n); n = int(0.05 * sr); y[-n:] *= np.linspace(1, 0, n)
    sf.write(tmp, y, sr)
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "loudnorm=I=-18:TP=-2:LRA=7:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    ln = f"loudnorm=I=-18:TP=-2:LRA=7:linear=true:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-af", ln, "-ar", "48000", "-ac", "1", dst], check=True)
    os.remove(tmp)
    return round(a, 3)
det = {n: pipeline("audio-classification", model=n, device=0) for n in
       ["mo-thecreator/Deepfake-audio-detection", "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification"]}
fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()
def emb(y):
    x = fe(y, sampling_rate=16000, return_tensors="pt").to("cuda")
    with torch.no_grad(): return torch.nn.functional.normalize(sv(**x).embeddings, dim=-1)[0]
person = {s: emb(librosa.load(f"C:/Users/smile/OneDrive/Desktop/녹음파일들/{f}", sr=16000)[0]) for s, f in REC.items()}
def st_std(y):
    f, v, _ = librosa.pyin(y, fmin=60, fmax=400, sr=16000, frame_length=1024)
    f = f[v & ~np.isnan(f)]
    return float(np.std(12 * np.log2(f / np.median(f)))) if len(f) > 20 else float("nan")
rows = []
for src in sorted(glob.glob(f"{IN}/*.wav")):
    key = os.path.basename(src).split("_")[0]
    dst = f"{OUT}/{os.path.basename(src)}"
    head = process(src, dst)
    y, _ = librosa.load(dst, sr=16000)
    ws = words(dst)
    r = {"key": key, "file": os.path.basename(src), "head": head, "dur": round(len(y) / 16000, 3),
         "cer": round(cer(TXT[key], "".join(w for w, _, _ in ws)), 3), "sim": round(float(emb(y) @ person[SPK[key]]), 3),
         "rate_dev": round(syl(TXT[key].replace("에이아이", "AI")) / (ws[-1][2] - ws[0][1]) / TARGET[SPK[key]] - 1, 3),
         "pros_dev": round(st_std(y) - PROS[SPK[key]], 2), "words": ws}
    for n, clf in det.items():
        d = {o["label"].lower(): o["score"] for o in clf({"raw": y, "sampling_rate": 16000}, top_k=None)}
        r["mo" if n.startswith("mo") else "gk"] = round(d["real"], 3)
    r["human"] = min(r["mo"], r["gk"])
    rows.append(r)
    print(f"{r['file']:10} 오류율 {r['cer']:.3f} 닮음 {r['sim']:.3f} 사람(mo) {r['mo']:.3f} 사람(gk) {r['gk']:.3f} 빠르기 {r['rate_dev']:+.3f} 억양 {r['pros_dev']:+.2f} 앞 {r['head']}", flush=True)
json.dump(rows, open(f"{OUT}/pick.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("PICK")
# 받아쓰기 오류율이 가장 낮은 것들 중에서 고른다. 숫자를 한글로 적은 대사("십칠 분")는 받아쓰기가 숫자로 적어
# 오류율이 0 이 안 될 수 있다 — 고른 것의 받아쓰기를 같이 찍어 눈으로 확인한다.
picks = {}
for key in TXT:
    c = [r for r in rows if r["key"] == key]
    low = min(r["cer"] for r in c)
    c = [r for r in c if r["cer"] <= low + 0.02]
    best = max(c, key=lambda r: (r["human"] >= 0.8, r["sim"] - 0.5 * abs(r["pros_dev"]) / PROS[SPK[key]] - 0.3 * abs(r["rate_dev"]) + 0.2 * r["human"]))
    picks[key] = best["file"]
    print(key, best["file"], {k: best[k] for k in ("cer", "sim", "mo", "gk", "rate_dev", "pros_dev", "dur", "head")})
    print("   ", "".join(w + " " for w, _, _ in best["words"]).strip())
json.dump(picks, open(f"{OUT}/picks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
