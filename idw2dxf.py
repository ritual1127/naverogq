"""Inventor .idw 도면을 DXF로 내보낸다.

수집한 실제 도면은 Inventor 파일이라 CADLens가 못 읽는다. Inventor가 깔린
PC에서 한 번 돌려 DXF로 바꿔 두면 `실제도면/원본/`에서 그대로 검사·측정할 수 있다.
(P04 — 합성 도면 18장 말고 실제 도면으로 정확도를 재기 위한 준비)

    python idw2dxf.py "<idw 폴더>" [--out 실제도면/원본] [--prefix A]

파일 이름은 A01.dxf, A02.dxf … 로 새로 붙인다. 원래 이름이 누구 것인지
드러낼 수 있어서다. 어떤 idw가 어떤 번호가 됐는지는 --out 폴더의
`변환기록.csv`에만 남고, 이 파일도 저장소에 올라가지 않는다.
"""
import argparse
import csv
import os
import re
import sys

VERSION_IN_FILE = re.compile(r"(20\d\d) \(Build ")
UTF16_RUN = re.compile(rb"(?:[ -~]\x00){8,}")


def idw_version(path):
    """idw를 저장한 Inventor 릴리스 연도. 못 찾으면 None.

    Inventor는 자기보다 새 버전이 저장한 파일을 못 연다. 2027로 저장한 도면을
    2026이 열면 이유를 알려주지 않고 그냥 실패해서(E_FAIL), 미리 보고 알린다.
    """
    with open(path, "rb") as f:
        head = f.read(400000)
    years = [int(m.group(1))
             for run in UTF16_RUN.findall(head)
             for m in [VERSION_IN_FILE.match(run.decode("utf-16-le", "ignore"))]
             if m]
    return max(years) if years else None


def export(idw_paths, out_dir, prefix):
    import win32com.client

    inv = win32com.client.Dispatch("Inventor.Application")
    inv.SilentOperation = True
    here = re.match(r"(20\d\d)", str(inv.SoftwareVersion.DisplayName))
    here = int(here.group(1)) if here else None

    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for i, src in enumerate(sorted(idw_paths), 1):
        name = f"{prefix}{i:02d}.dxf"
        dst = os.path.abspath(os.path.join(out_dir, name))
        made_by = idw_version(src)
        if here and made_by and made_by > here:
            print(f"  {name} <- {os.path.basename(src)}: 건너뜀 — Inventor "
                  f"{made_by}로 저장한 도면인데 이 PC에는 {here}뿐입니다. "
                  f"Inventor는 자기보다 새 버전 파일을 못 엽니다.", file=sys.stderr)
            rows.append({"파일": name, "원본": os.path.basename(src),
                         "결과": f"실패(Inventor {made_by} 필요)"})
            continue

        doc = None
        try:
            doc = inv.Documents.Open(os.path.abspath(src), False)
            doc.SaveAs(dst, True)  # True = 사본 저장, 원본 idw는 안 건드린다
            ok = os.path.exists(dst)
        except Exception as e:  # noqa: BLE001 -- 한 장 실패해도 나머지는 계속 뽑는다
            ok = False
            print(f"  {name} <- {os.path.basename(src)}: 실패 {e}", file=sys.stderr)
        finally:
            if doc is not None:
                doc.Close(True)
        if ok:
            print(f"  {name} <- {os.path.basename(src)}")
        rows.append({"파일": name, "원본": os.path.basename(src),
                     "결과": "성공" if ok else "실패"})
    inv.Quit()

    log = os.path.join(out_dir, "변환기록.csv")
    with open(log, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["파일", "원본", "결과"])
        w.writeheader()
        w.writerows(rows)
    return rows


def demo():
    import tempfile
    marker = "2027 (Build 310192000, 192)".encode("utf-16-le")
    with tempfile.NamedTemporaryFile(suffix=".idw", delete=False) as f:
        f.write(b"x" * 100 + marker + b"\x00" * 20)
    assert idw_version(f.name) == 2027
    with tempfile.NamedTemporaryFile(suffix=".idw", delete=False) as g:
        g.write(b"no version here")
    assert idw_version(g.name) is None
    print("demo OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", help="idw 파일이 있는 폴더")
    ap.add_argument("--out", default=os.path.join("실제도면", "원본"))
    ap.add_argument("--prefix", default="A")
    ap.add_argument("--demo", action="store_true", help="자체 점검만 하고 끝낸다")
    a = ap.parse_args()
    if a.demo:
        demo()
        return 0
    if not a.src:
        ap.error("idw 폴더를 적어 주세요")

    idws = []
    for root, _dirs, files in os.walk(a.src):
        idws += [os.path.join(root, f) for f in files if f.lower().endswith(".idw")]
    if not idws:
        print(f"FAIL: {a.src} 아래에 .idw가 없습니다.", file=sys.stderr)
        return 1

    print(f"{len(idws)}장을 {a.out}로 내보냅니다. Inventor가 뜨는 데 시간이 걸립니다.")
    rows = export(idws, a.out, a.prefix)
    good = sum(r["결과"] == "성공" for r in rows)
    print(f"{good}/{len(rows)}장 성공")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
