"""Probe 20: how long does one analysis actually take?

Design Automation bills by runtime, so cost per file is our measured time plus
cloud file-transfer overhead. Autodesk's published example uses a 400 MB file;
these are the user's real ones.
"""
import os
import time

import check

FILES = [
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\1본체.ipt",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\3축.idw",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\5커버(2개).idw",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\편심구동장치(조립)_(배포)\조립품1.iam",
]

CREDITS_PER_HOUR = 6.0     # Inventor on Design Automation
USD_PER_CREDIT = 1.0       # from Autodesk's own worked example: 1 min = $0.10

print(f"{'file':28} {'MB':>6} {'sec':>7} {'USD/job':>9}  findings")
print("-" * 72)
rows = []
for p in FILES:
    if not os.path.exists(p):
        print(f"{os.path.basename(p)[:26]:28} MISSING")
        continue
    mb = os.path.getsize(p) / 1e6
    t0 = time.perf_counter()
    try:
        facts, findings, summary = check.analyze(p)
        n = summary["total"]
    except Exception as e:
        print(f"{os.path.basename(p)[:26]:28} FAILED {type(e).__name__}")
        continue
    dt = time.perf_counter() - t0
    usd = dt / 3600 * CREDITS_PER_HOUR * USD_PER_CREDIT
    rows.append((dt, mb, usd))
    print(f"{os.path.basename(p)[:26]:28} {mb:6.1f} {dt:7.1f} {usd:9.4f}  {n}")

if rows:
    avg = sum(r[0] for r in rows) / len(rows)
    print("-" * 72)
    print(f"average runtime: {avg:.1f} s")
    # cloud adds upload/download of the file plus container spin-up
    for overhead in (30, 60):
        per = (avg + overhead) / 3600 * CREDITS_PER_HOUR * USD_PER_CREDIT
        print(f"  with {overhead}s cloud overhead -> ${per:.3f}/file  "
              f"= ${per * 100:.2f} per 100 files  = ${per * 1000:.0f} per 1000 files")
