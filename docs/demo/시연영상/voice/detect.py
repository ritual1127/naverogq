# "AI 같음" 을 재는 잣대 찾기 — 합성 음성 탐지기 셋을 먼저 검증한다(진짜 녹음 = 사람, Microsoft TTS = 합성으로 가르는가)
# 그다음 Chatterbox(지금) · Qwen3 후보의 "사람일 확률"과 억양 폭(반음 표준편차)을 그 사람 실제 말과 견준다
import os, sys, re, json, glob
import torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import numpy as np, librosa
from transformers import pipeline
sys.stdout.reconfigure(encoding="utf-8")
REC = {"andaeyeol": "01_안대열.m4a", "jangwooyoung": "02_장우영 녹음.m4a", "parkjiwan": "03_박지완 녹음.m4a", "kimseungjun": "04_김승준 녹음.m4a"}
SPK = {"v1": "andaeyeol", "v2": "jangwooyoung", "v3": "parkjiwan", "v4a": "kimseungjun", "v4b": "kimseungjun", "v4c": "kimseungjun"}
real = []
for spk, f in REC.items():
    y, _ = librosa.load(f"C:/Users/smile/OneDrive/Desktop/녹음파일들/{f}", sr=16000)
    y = y[: int(28 * 16000)]
    for i in range(0, len(y) - 16000 * 4, 16000 * 5): real.append((spk, y[i:i + 16000 * 5]))
synth_ms = [librosa.load(f, sr=16000)[0] for f in sorted(glob.glob("cand/*_edge*.mp3"))]
groups = {"real": [y for _, y in real], "microsoft": synth_ms,
          "chatterbox": [librosa.load(f"final3/{k}.wav", sr=16000)[0] for k in SPK],
          "qwen3": [librosa.load(f, sr=16000)[0] for f in sorted(glob.glob("qcand/*.wav"))]}
MODELS = ["Gustking/wav2vec2-large-xlsr-deepfake-audio-classification", "mo-thecreator/Deepfake-audio-detection", "MelodyMachine/Deepfake-audio-detection-V2"]
def real_prob(clf, y):
    out = clf({"raw": y, "sampling_rate": 16000}, top_k=None)
    d = {o["label"].lower(): o["score"] for o in out}
    key = next((k for k in d if k in ("real", "bonafide", "bona-fide", "human", "genuine")), None)
    if key is None:                                    # 라벨이 숫자 등이면 fake 의 반대
        fk = next((k for k in d if "fake" in k or "spoof" in k), None)
        return 1 - d[fk] if fk else float("nan")
    return d[key]
res = {}
for name in MODELS:
    try:
        clf = pipeline("audio-classification", model=name, device=0)
    except Exception as e:
        print("못 불러옴", name, e); continue
    print("==", name, "labels", clf.model.config.id2label)
    g = {k: [real_prob(clf, y) for y in v] for k, v in groups.items()}
    for k, v in g.items(): print(f"   {k:11} 사람일 확률 평균 {np.mean(v):.3f}  (최소 {np.min(v):.3f} · 최대 {np.max(v):.3f}, n={len(v)})")
    res[name] = {"groups": {k: [round(float(x), 4) for x in v] for k, v in g.items()},
                 "files": {"chatterbox": [f"final3/{k}.wav" for k in SPK], "qwen3": sorted(glob.glob("qcand/*.wav"))}}
    del clf; torch.cuda.empty_cache()
json.dump(res, open("detect.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 억양 폭 — 유성음 F0 의 반음 표준편차
def st_std(y):
    f, v, _ = librosa.pyin(y, fmin=60, fmax=400, sr=16000, frame_length=1024)
    f = f[v & ~np.isnan(f)]
    return float(np.std(12 * np.log2(f / np.median(f)))) if len(f) > 20 else float("nan")
person = {}
for spk, f in REC.items():
    y, _ = librosa.load(f"C:/Users/smile/OneDrive/Desktop/녹음파일들/{f}", sr=16000)
    person[spk] = round(st_std(y[: int(28 * 16000)]), 2)
print("실제 억양 폭(반음 표준편차)", person)
pros = {"person": person, "chatterbox": {}, "qwen3": {}}
for k in SPK:
    pros["chatterbox"][k] = round(st_std(librosa.load(f"final3/{k}.wav", sr=16000)[0]), 2)
    pros["qwen3"][k] = {os.path.basename(f): round(st_std(librosa.load(f, sr=16000)[0]), 2) for f in sorted(glob.glob(f"qcand/{k}_*.wav"))}
    print(k, SPK[k], "실제", person[SPK[k]], "| chatterbox", pros["chatterbox"][k], "| qwen3", pros["qwen3"][k])
json.dump(pros, open("prosody.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
