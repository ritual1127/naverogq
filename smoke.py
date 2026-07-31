import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
DRAWINGS = [
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\1본체.idw",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\2V벨트풀리.idw",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\3축.idw",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\5커버(2개).idw",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\슬라이더 부시 도면.idw",
]


def post(endpoint, payload):
    req = urllib.request.Request(
        BASE + endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"}


def get(endpoint):
    with urllib.request.urlopen(BASE + endpoint, timeout=60) as r:
        return json.load(r)


def line(label, sc, findings):
    if sc is None:
        print(f"  {label:26} 채점 없음")
        return
    verdict = "오작" if sc["disqualified"] else f"{sc['auto_score']:>2}/{sc['auto_max']}"
    print(f"  {label:26} {verdict:>6}  켜짐 {sc['enabled_count']:>2}/{sc['total_checks']}"
          f"  검출 {sc['summary']['total']}")
    for f in findings:
        print(f"        [{f['severity']:5}] {f['title']}")


h = get("/api/health")
print(f"검사 항목 {len(h['checks'])}개 · 기준 {h['exam']['sheet']} · "
      f"DWG변환 {'있음' if h['dwg_converter'] else '없음'}")
assert not any("DECIMAL" in c["id"] for c in h["checks"]), "소수점 검사가 남아있음"
print("소수점 검사 제거 확인 OK\n")

files = sys.argv[1:] or DRAWINGS

print("=== 전체 검사 ===")
for p in files:
    r = post("/api/analyze-path", {"path": p})
    if "_error" in r:
        print(f"  {p.split(chr(92))[-1]:26} {r['_error']}")
        continue
    line(r["file"], r.get("scorecard"), r.get("findings", []))

print("\n=== 검사 선택 동작 확인 (5커버) ===")
target = next((p for p in files if "5커버" in p), files[0])
for label, checks in (("전체", None),
                      ("치수누락만", ["EX_DIM_MISSING"]),
                      ("열처리만", ["EX_NO_HEAT"]),
                      ("오작 판정만", ["DQ_NO_SURFACE_SYMBOL", "DQ_NO_GEOMETRIC_TOL",
                                       "DQ_PROJECTION", "DQ_SHEET_SIZE", "DQ_SCALE"]),
                      ("전부 끄기", [])):
    payload = {"path": target}
    if checks is not None:
        payload["checks"] = checks
    r = post("/api/analyze-path", payload)
    if "_error" in r:
        print(f"  {label:26} {r['_error']}")
        continue
    line(label, r.get("scorecard"), r.get("findings", []))

print("\n=== 오작 파일 확인 (1본체) ===")
r = post("/api/analyze-path", {"path": DRAWINGS[0]})
sc = r.get("scorecard")
if sc:
    print(f"  disqualified={sc['disqualified']}  사유={sc['disqualifiers']}")
    assert sc["disqualified"], "1본체는 기하공차가 없어 실격이어야 함"
    keep = [c["id"] for c in h["checks"] if c["group"] != "오작"]
    sc2 = post("/api/analyze-path",
               {"path": DRAWINGS[0], "checks": keep})["scorecard"]
    print(f"  오작 검사 끈 뒤: disqualified={sc2['disqualified']} "
          f"점수={sc2['auto_score']}/{sc2['auto_max']}")
    assert not sc2["disqualified"], "오작 검사를 껐는데 실격이 유지됨"
    sc3 = post("/api/analyze-path",
               {"path": DRAWINGS[0], "checks": []})["scorecard"]
    print(f"  전부 끈 뒤: 켜짐 {sc3['enabled_count']}/{sc3['total_checks']} "
          f"점수={sc3['auto_score']}/{sc3['auto_max']} 검출={sc3['summary']['total']}")
    assert sc3["enabled_count"] == 0 and sc3["summary"]["total"] == 0, \
        "빈 선택이 '전체 검사'로 해석됨"
    assert sc3["auto_score"] == sc3["auto_max"], "검사를 다 껐는데 감점이 남음"
    print("  토글 반영 OK")
print("\nDONE")

