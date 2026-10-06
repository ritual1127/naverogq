# Qwen3-TTS 1.7B Base — 참고 녹음 + 그 녹음의 정확한 글(ICL)로 그 사람 목소리를 본떠 읽는다. 대사마다 6개
import os, sys, json, random
import torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import numpy as np, soundfile as sf
from qwen_tts import Qwen3TTSModel
sys.stdout.reconfigure(encoding="utf-8")
LINES = [
    ("v1", "andaeyeol", "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다."),
    ("v2", "jangwooyoung", "그러면 실격 사유는 오른쪽에, 빠뜨린 치수 자리는 도면 위에 번호로 표시합니다."),
    ("v3", "parkjiwan", "번호를 누르면, 그 자리를 바로 확대해서 보여 줍니다."),
    ("v4a", "kimseungjun", "지난 데모데이 이후에 새로 만든 기능, 수정 예시입니다."),
    ("v4b", "kimseungjun", "누르면, 빠진 치수를 도면에서 읽은 좌표 그대로 초록색으로 그려 줍니다."),
    ("v4c", "kimseungjun", "에이아이가 그림을 지어내는 게 아니라서, 위치와 값이 정확합니다."),
]
# 다른 대사 묶음 — LINES=lines.json(키: [사람, 글]) OUT=폴더 로 준다. 3분 영상은 docs/demo/3분영상/lines.json
if os.environ.get("LINES"):
    LINES = [(k, spk, text) for k, (spk, text) in json.load(open(os.environ["LINES"], encoding="utf-8")).items()]
K = int(os.environ.get("K", 6))
OUT = os.environ.get("OUT", "qcand"); os.makedirs(OUT, exist_ok=True)
refs = json.load(open("qrefs/text.json", encoding="utf-8"))
m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa")
print("languages", m.model.get_supported_languages() if hasattr(m.model, "get_supported_languages") else "?", flush=True)
prompts = {spk: m.create_voice_clone_prompt(ref_audio=f"qrefs/{spk}.wav", ref_text=refs[spk]) for spk in refs}
for key, spk, text in LINES:
    for s in range(K):
        p = f"{OUT}/{key}_{s}.wav"
        if os.path.exists(p): continue
        torch.manual_seed(s); random.seed(s); np.random.seed(s)
        wavs, sr = m.generate_voice_clone(text=text, language="Korean", voice_clone_prompt=prompts[spk])
        sf.write(p, wavs[0], sr)
        print(key, s, round(len(wavs[0]) / sr, 2), flush=True)
