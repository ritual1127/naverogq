# 말이 끝난 뒤 따라붙은 숨·잡음 꼬리를 자른다 — 마지막 낱말 끝에서 소리가 -40dB 아래로 0.12초 머무는 곳(+0.10초),
# 못 찾으면 마지막 낱말 끝 +0.35초에서 끊고 0.05초 페이드. 자른 뒤 다시 받아써서 오류율 확인
import os, sys, re, json, torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import numpy as np, soundfile as sf
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding="utf-8")
rep = json.load(open("final2/report.json", encoding="utf-8"))
asr = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
TXT = {"v1": "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다.", "v2": "그러면 실격 사유는 오른쪽에, 빠뜨린 치수 자리는 도면 위에 번호로 표시합니다.",
       "v3": "번호를 누르면, 그 자리를 바로 확대해서 보여 줍니다.", "v4a": "지난 데모데이 이후에 새로 만든 기능, 수정 예시입니다.",
       "v4b": "누르면, 빠진 치수를 도면에서 읽은 좌표 그대로 초록색으로 그려 줍니다.", "v4c": "에이아이가 그림을 지어내는 게 아니라서, 위치와 값이 정확합니다."}
norm = lambda s: re.sub(r"[^가-힣a-z0-9]", "", s.lower().replace("ai", "에이아이"))
def cer(r, h):
    r, h = norm(r), norm(h); d = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        p, d[0] = d[0], i
        for j, hc in enumerate(h, 1): p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (rc != hc))
    return d[len(h)] / len(r)
os.makedirs("final3", exist_ok=True)
out = {}
for k, info in rep["lines"].items():
    y, sr = sf.read(f"final2/{k}.wav", dtype="float32")
    lw = info["words"][-1][2]                                   # 마지막 낱말이 끝나는 시각
    fr = int(0.01 * sr)
    rms = np.sqrt(np.convolve(y ** 2, np.ones(fr) / fr, mode="same"))
    thr = rms.max() * 10 ** (-40 / 20)
    cut = None
    i0, i1, need = int(lw * sr), min(len(y), int((lw + 0.35) * sr)), int(0.12 * sr)
    i = i0
    while i < i1:
        if np.all(rms[i:i + need] < thr): cut = i + int(0.10 * sr); break
        i += fr
    cut = min(len(y), cut if cut is not None else i1)
    z = y[:cut].copy()
    n = int(0.05 * sr); z[-n:] *= np.linspace(1, 0, n)
    sf.write(f"final3/{k}.wav", z, sr)
    segs, _ = asr.transcribe(f"final3/{k}.wav", language="ko", word_timestamps=True, beam_size=5)
    ws = [(w.word.strip(), round(w.start, 2), round(w.end, 2)) for s in segs for w in s.words if w.word.strip()]
    tail_after = len(y) / sr - cut / sr
    out[k] = {**{x: info[x] for x in ("spk", "target", "tempo", "pick", "sim", "mos")}, "dur": round(cut / sr, 3),
              "cer": round(cer(TXT[k], "".join(w for w, _, _ in ws)), 3), "words": ws}
    print(k, "자른 꼬리", round(tail_after, 2), "초 → 길이", out[k]["dur"], "오류율", out[k]["cer"], "| 끝 낱말", ws[-1])
json.dump({"target": rep["target"], "lines": out}, open("final3/report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
