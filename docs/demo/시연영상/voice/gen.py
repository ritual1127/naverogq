# 영상 4부분 대사를 각 팀원 목소리로 만든다 — 두 길로 후보를 내고 숫자로 고른다.
#  A: Chatterbox 다국어 TTS 가 참고 녹음으로 바로 복제
#  B: Microsoft 신경망 한국어 TTS(발음) → Chatterbox VC 로 팀원 음색만 바꿈
# 평가: 발음 = Whisper 로 받아써 글자 오류율(CER) · 닮음 = WavLM 화자 임베딩 코사인 · 자연스러움 = UTMOS
import os, sys, json, random, asyncio, re
import torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import numpy as np, librosa, soundfile as sf, torchaudio as ta
sys.stdout.reconfigure(encoding="utf-8")

LINES = [
    ("p1", "andaeyeol", "실기 도면을, 이렇게 끌어다 놓기만 하면 됩니다."),
    ("p2", "jangwooyoung", "그러면 실격 사유와 빠뜨린 치수 자리가, 도면 위에 번호로 나옵니다."),
    ("p3", "parkjiwan", "번호를 누르면, 그 자리로 바로 갑니다."),
    ("p4a", "kimseungjun", "그리고 지난 데모데이 이후 새로 만든 수정 예시는, 빠진 치수를 도면 좌표 그대로 초록색으로 그려 줍니다."),
    ("p4b", "kimseungjun", "그림을 지어내는 에이아이가 아니라서, 위치와 값이 정확합니다."),
]
K = int(os.environ.get("K", 5))
OUT = "cand"
os.makedirs(OUT, exist_ok=True)
stage = sys.argv[1] if len(sys.argv) > 1 else "all"


def seed_all(s):
    torch.manual_seed(s); random.seed(s); np.random.seed(s)


def f0(path):
    y, sr = librosa.load(path, sr=16000)
    f, v, _ = librosa.pyin(y, fmin=60, fmax=400, sr=sr)
    return float(np.nanmedian(f[v])) if np.any(v) else float("nan")


if stage in ("all", "A"):
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    m = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    for key, spk, text in LINES:
        for s in range(K):
            p = f"{OUT}/{key}_A{s}.wav"
            if os.path.exists(p): continue
            seed_all(s)
            wav = m.generate(text, language_id="ko", audio_prompt_path=f"refs/{spk}.wav",
                             exaggeration=0.5, cfg_weight=0.5, temperature=0.8)
            ta.save(p, wav.cpu(), m.sr)
            print("A", key, s, round(wav.shape[-1] / m.sr, 2), flush=True)
    del m; torch.cuda.empty_cache()

if stage in ("all", "B"):
    import edge_tts
    BASE = {"female": "ko-KR-SunHiNeural", "male": "ko-KR-InJoonNeural"}
    pitch = {spk: f0(f"refs/{spk}.wav") for spk in {l[1] for l in LINES}}
    print("ref median F0", {k: round(v) for k, v in pitch.items()}, flush=True)
    async def say(text, voice, path, rate):
        await edge_tts.Communicate(text, voice, rate=rate).save(path)
    from chatterbox.vc import ChatterboxVC
    vc = ChatterboxVC.from_pretrained("cuda")
    for key, spk, text in LINES:
        voice = BASE["female" if pitch[spk] > 165 else "male"]   # 참고 녹음 음높이가 가까운 쪽을 바탕으로
        for i, rate in enumerate(["+0%", "-6%"]):
            src = f"{OUT}/{key}_edge{i}.mp3"
            if not os.path.exists(src):
                asyncio.run(say(text.replace("에이아이", "AI"), voice, src, rate))
            p = f"{OUT}/{key}_B{i}.wav"
            if os.path.exists(p): continue
            wav = vc.generate(audio=src, target_voice_path=f"refs/{spk}.wav")
            ta.save(p, wav.cpu(), vc.sr)
            print("B", key, i, voice, rate, round(wav.shape[-1] / vc.sr, 2), flush=True)
    del vc; torch.cuda.empty_cache()

if stage in ("all", "eval"):
    from faster_whisper import WhisperModel
    from transformers import AutoFeatureExtractor, WavLMForXVector
    asr = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()
    utmos = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True).cuda().eval()

    def emb(y):
        x = fe(y, sampling_rate=16000, return_tensors="pt").to("cuda")
        with torch.no_grad():
            e = sv(**x).embeddings
        return torch.nn.functional.normalize(e, dim=-1)[0]

    norm = lambda s: re.sub(r"[^가-힣a-z0-9]", "", s.lower().replace("ai", "에이아이"))
    def cer(ref, hyp):
        r, h = norm(ref), norm(hyp)
        d = list(range(len(h) + 1))
        for i, rc in enumerate(r, 1):
            prev, d[0] = d[0], i
            for j, hc in enumerate(h, 1):
                prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rc != hc))
        return d[len(h)] / max(1, len(r))

    refemb = {}
    rows = []
    for key, spk, text in LINES:
        if spk not in refemb:
            refemb[spk] = emb(librosa.load(f"refs/{spk}.wav", sr=16000)[0])
        for name in sorted(os.listdir(OUT)):
            if not (name.startswith(key + "_") and name.endswith(".wav")): continue
            y, _ = librosa.load(f"{OUT}/{name}", sr=16000)
            hyp = " ".join(s.text for s in asr.transcribe(y, language="ko", beam_size=5)[0])
            sim = float(emb(y) @ refemb[spk])
            with torch.no_grad():
                mos = float(utmos(torch.tensor(y)[None].cuda(), 16000)[0])
            c = cer(text, hyp)
            rows.append({"key": key, "file": name, "dur": round(len(y) / 16000, 2), "cer": round(c, 3),
                         "sim": round(sim, 3), "mos": round(mos, 2), "score": round(sim + 0.3 * (mos - 3) - 1.5 * c, 3), "hyp": hyp})
            print(rows[-1], flush=True)
    json.dump(rows, open("eval.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nBEST")
    for key, _, _ in LINES:
        ok = [r for r in rows if r["key"] == key]
        best = max(ok, key=lambda r: (r["cer"] <= 0.06, r["score"]))
        print(key, best["file"], best["dur"], "cer", best["cer"], "sim", best["sim"], "mos", best["mos"])
