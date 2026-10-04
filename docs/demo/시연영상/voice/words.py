import os, sys, json, torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding="utf-8")
m = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
res = {}
for k in ["p1", "p2", "p3", "p4a", "p4b"]:
    segs, _ = m.transcribe(f"final/{k}.wav", language="ko", word_timestamps=True, beam_size=5)
    ws = [(w.word.strip(), round(w.start, 2), round(w.end, 2)) for s in segs for w in s.words]
    res[k] = ws
    print(k, " ".join(f"{w}[{a}-{b}]" for w, a, b in ws))
json.dump(res, open("final/words.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
import re
T = {"p1": "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다.", "p2": "그러면 실격 사유와 빠뜨린 치수 자리가, 도면 위에 번호로 나옵니다.",
     "p3": "번호를 누르면, 그 자리로 바로 갑니다.", "p4a": "그리고 지난 데모데이 이후 새로 만든 수정 예시는, 빠진 치수를 도면 좌표 그대로 초록색으로 그려 줍니다.",
     "p4b": "그림을 지어내는 에이아이가 아니라서, 위치와 값이 정확합니다."}
n = lambda s: re.sub(r"[^가-힣a-z0-9]", "", s.lower().replace("ai", "에이아이"))
for k, ws in res.items():
    h, r = n("".join(w for w, _, _ in ws)), n(T[k])
    d = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        p, d[0] = d[0], i
        for j, hc in enumerate(h, 1): p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (rc != hc))
    print("FINAL CER", k, round(d[len(h)] / len(r), 3))
