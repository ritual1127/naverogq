import json
import urllib.request

BASE = "http://127.0.0.1:8000"
DRAWING = r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\5커버(2개).idw"


def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r:
        return json.load(r)


def post(p, payload):
    req = urllib.request.Request(
        BASE + p, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


h = get("/api/health")
print("=== /api/health keys ===")
print(json.dumps({k: (v if k != "checks" else f"<{len(v)} items>")
                  for k, v in h.items()}, ensure_ascii=False, indent=2))
print("\n=== checks[] sample ===")
print(json.dumps(h["checks"][:3], ensure_ascii=False, indent=2))
print("\n=== check groups ===")
seen = []
for c in h["checks"]:
    if c["group"] not in [g[0] for g in seen]:
        seen.append((c["group"], c["group_label"]))
for g, l in seen:
    n = sum(1 for c in h["checks"] if c["group"] == g)
    print(f"   {g:20} {l:24} {n}개")

r = post("/api/analyze-path", {"path": DRAWING})
print("\n=== /api/analyze-path response keys ===")
for k, v in r.items():
    if k == "svg":
        print(f"   svg              <string, {len(v)} chars>")
    elif isinstance(v, (dict, list)):
        print(f"   {k:16} {type(v).__name__} len={len(v)}")
    else:
        print(f"   {k:16} {v!r}")

print("\n=== scorecard ===")
print(json.dumps(r["scorecard"], ensure_ascii=False, indent=2)[:1400])
print("\n=== findings[0] ===")
print(json.dumps(r["findings"][0], ensure_ascii=False, indent=2))
print("\n=== stats ===")
print(json.dumps(r["stats"], ensure_ascii=False, indent=2))
print("\n=== marker_index ===")
print(json.dumps(r["marker_index"], ensure_ascii=False, indent=2))
print("\n=== all finding codes seen ===")
print(sorted({f["code"] for f in r["findings"]}))

