# 두 모델을 같은 잣대로 — Qwen3-TTS 후보들과 지금 쓰는 Chatterbox 대사(final3)를 견준다.
# 닮음은 그 사람의 7월 녹음 전체(30초)와, 발음은 받아쓰기 오류율, 자연스러움은 UTMOS, 빠르기는 그 사람 문장 빠르기와의 차이
import os, sys, re, json, glob
import torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import numpy as np, librosa
from faster_whisper import WhisperModel
from transformers import AutoFeatureExtractor, WavLMForXVector
sys.stdout.reconfigure(encoding="utf-8")
LINES = {"v1": ("andaeyeol", "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다."),
         "v2": ("jangwooyoung", "그러면 실격 사유는 오른쪽에, 빠뜨린 치수 자리는 도면 위에 번호로 표시합니다."),
         "v3": ("parkjiwan", "번호를 누르면, 그 자리를 바로 확대해서 보여 줍니다."),
         "v4a": ("kimseungjun", "지난 데모데이 이후에 새로 만든 기능, 수정 예시입니다."),
         "v4b": ("kimseungjun", "누르면, 빠진 치수를 도면에서 읽은 좌표 그대로 초록색으로 그려 줍니다."),
         "v4c": ("kimseungjun", "에이아이가 그림을 지어내는 게 아니라서, 위치와 값이 정확합니다.")}
REC = {"andaeyeol": "01_안대열.m4a", "jangwooyoung": "02_장우영 녹음.m4a", "parkjiwan": "03_박지완 녹음.m4a", "kimseungjun": "04_김승준 녹음.m4a"}
TARGET = json.load(open("final2/report.json", encoding="utf-8"))["target"]
syl = lambda s: len(re.findall(r"[가-힣]", s)) + len(re.findall(r"[A-Za-z]", s)) * 0.6
norm = lambda s: re.sub(r"[^가-힣a-z0-9]", "", s.lower().replace("ai", "에이아이"))
def cer(r, h):
    r, h = norm(r), norm(h); d = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        p, d[0] = d[0], i
        for j, hc in enumerate(h, 1): p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (rc != hc))
    return d[len(h)] / len(r)
asr = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()
utmos = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True).cuda().eval()
def emb(y):
    x = fe(y, sampling_rate=16000, return_tensors="pt").to("cuda")
    with torch.no_grad(): return torch.nn.functional.normalize(sv(**x).embeddings, dim=-1)[0]
person = {spk: emb(librosa.load(f"C:/Users/smile/OneDrive/Desktop/녹음파일들/{f}", sr=16000)[0]) for spk, f in REC.items()}
def score(path, key):
    spk, text = LINES[key]
    y, _ = librosa.load(path, sr=16000)
    segs, _ = asr.transcribe(y, language="ko", word_timestamps=True, beam_size=5)
    ws = [w for s in segs for w in s.words if w.word.strip()]
    hyp = "".join(w.word for w in ws)
    rate = syl(text.replace("에이아이", "AI")) / max(0.1, ws[-1].end - ws[0].start) if ws else 0
    with torch.no_grad(): mos = float(utmos(torch.tensor(y)[None].cuda(), 16000)[0])
    return {"cer": round(cer(text, hyp), 3), "sim": round(float(emb(y) @ person[spk]), 3), "mos": round(mos, 2),
            "rate": round(rate, 2), "dev": round(rate / TARGET[spk] - 1, 3), "hyp": hyp}
rows = []
for key in LINES:
    base = score(f"final3/{key}.wav", key); base.update(model="chatterbox(지금)", file=f"final3/{key}.wav", key=key); rows.append(base)
    for f in sorted(glob.glob(f"qcand/{key}_*.wav")):
        r = score(f, key); r.update(model="qwen3", file=f, key=key); rows.append(r)
json.dump(rows, open("qeval.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{'대사':5} {'모델':16} {'오류율':>6} {'닮음':>6} {'UTMOS':>6} {'빠르기차':>8}  파일")
for key in LINES:
    for r in [x for x in rows if x["key"] == key]:
        print(f"{key:5} {r['model']:16} {r['cer']:6.3f} {r['sim']:6.3f} {r['mos']:6.2f} {r['dev']:+8.3f}  {os.path.basename(r['file'])}")
print("\n모델별 평균 (오류율 0 인 후보 중 가장 자연스러운 것 기준)")
for model in ["chatterbox(지금)", "qwen3"]:
    best = []
    for key in LINES:
        c = [r for r in rows if r["key"] == key and r["model"] == model]
        ok = [r for r in c if r["cer"] == 0] or c
        best.append(max(ok, key=lambda r: r["mos"] + r["sim"]))
    print(model, "UTMOS", round(np.mean([b["mos"] for b in best]), 2), "닮음", round(np.mean([b["sim"] for b in best]), 3),
          "오류율0", sum(b["cer"] == 0 for b in best), "/", len(best))
