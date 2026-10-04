# 고른 다섯 개를 앞뒤 무음을 자르고 소리 크기를 맞춘다(-18 LUFS, 피크 -2 dBTP, 48kHz). 원본 녹음의 UTMOS 도 같이 잰다.
import os, sys, json, subprocess, re, torch
os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
import librosa
sys.stdout.reconfigure(encoding="utf-8")
PICK = {"p1": "p1_A1.wav", "p2": "p2_A2.wav", "p3": "p3_B1.wav", "p4a": "p4a_B1.wav", "p4b": "p4b_B1.wav"}
os.makedirs("final", exist_ok=True)
trim = ("silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.08,areverse,"
        "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.12,areverse")
out = {}
for k, f in PICK.items():
    src, tmp, dst = f"cand/{f}", f"final/{k}_trim.wav", f"final/{k}.wav"
    # 무음 자르기 — 그 파일 가장 큰 소리보다 38dB 아래까지를 말로 본다. 말 앞 0.08초 · 뒤 0.15초는 남긴다(첫 자음이 안 잘리게)
    import numpy as np, soundfile as sf
    y, sr = sf.read(src, dtype="float32")
    y = y if y.ndim == 1 else y.mean(axis=1)
    fr = int(0.01 * sr)
    rms = np.sqrt(np.convolve(y ** 2, np.ones(fr) / fr, mode="same"))
    on = np.where(rms > rms.max() * 10 ** (-38 / 20))[0]
    a0, a1 = max(0, on[0] - int(0.08 * sr)), min(len(y), on[-1] + int(0.15 * sr))
    sf.write(tmp + ".raw.wav", y[a0:a1], sr)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp + ".raw.wav", "-af", "aresample=48000", "-ac", "1", tmp], check=True)
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "loudnorm=I=-18:TP=-2:LRA=7:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    j = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    ln = (f"loudnorm=I=-18:TP=-2:LRA=7:linear=true:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']},afade=t=in:d=0.02,areverse,afade=t=in:d=0.04,areverse")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-af", ln, "-ar", "48000", "-ac", "1", dst], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst], capture_output=True, text=True).stdout)
    out[k] = round(d, 3)
print("durations", out)
json.dump(out, open("final/durations.json", "w"), indent=1)
utmos = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True).cuda().eval()
for r in sorted(os.listdir("refs")):
    y, _ = librosa.load(f"refs/{r}", sr=16000)
    with torch.no_grad(): print("ref UTMOS", r, round(float(utmos(torch.tensor(y)[None].cuda(), 16000)[0]), 2))
