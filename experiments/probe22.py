"""Probe 22: which additional deduction items can actually be read?

Candidates: line weights/types (KS line standard), decimal marker (comma vs
period), view labels and scale display, dimension precision, surface-roughness
values, datum references on geometric tolerances.
"""
import collections
import glob
import os
import win32com.client as w32

BASE = r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면"
FILES = [os.path.join(BASE, n) for n in ("3축.idw", "2V벨트풀리.idw", "5커버(2개).idw")]

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants
D = w32.constants.__dict__.get("__dicts__", [{}])[0]


def nm(v):
    return ([k for k, x in D.items() if x == v] or [str(v)])[0]


def members(o, label):
    try:
        ms = sorted(x for x in dir(o) if not x.startswith("_") and x[0].isupper())
        print(f"     {label} members: {', '.join(ms)}")
    except Exception as e:
        print(f"     {label} dir failed: {e}")


for path in FILES:
    print("\n" + "=" * 74)
    print(os.path.basename(path))
    print("=" * 74)
    d = w32.CastTo(app.Documents.Open(path, False), "DrawingDocument")
    sh = d.Sheets.Item(1)
    st = d.StylesManager.ActiveStandardStyle

    print("\n-- 제도 표준 --")
    for a in ("DecimalMarkerType", "LinearUnits", "GlobalLineScale",
              "InternationalStandardReference", "Name"):
        try:
            v = getattr(st, a)
            print(f"   {a} = {v!r} {nm(v) if isinstance(v, int) else ''}")
        except Exception as e:
            print(f"   {a}: {type(e).__name__}")

    print("\n-- 뷰 라벨/척도 표시 --")
    for vi in range(1, min(sh.DrawingViews.Count, 6) + 1):
        v = sh.DrawingViews.Item(vi)
        bits = {}
        for a in ("Name", "ScaleString", "ShowLabel", "ShowScale", "Label",
                  "ViewType", "ScaleFromBase"):
            try:
                x = getattr(v, a)
                bits[a] = x if a != "Label" else (getattr(x, "Text", "?") if x else None)
            except Exception:
                bits[a] = "ERR"
        print(f"   {bits.get('Name')!r:12} scale={bits.get('ScaleString')!r:8} "
              f"type={nm(bits.get('ViewType'))[:28]:28} "
              f"ShowLabel={bits.get('ShowLabel')} ShowScale={bits.get('ShowScale')} "
              f"label={bits.get('Label')!r}")

    print("\n-- 선 굵기/종류 분포 (KS 선 규격) --")
    lw, lt = collections.Counter(), collections.Counter()
    for vi in range(1, sh.DrawingViews.Count + 1):
        try:
            for dc in sh.DrawingViews.Item(vi).DrawingCurves:
                try:
                    lw[round(dc.LineWeight, 4)] += 1
                except Exception:
                    lw["ERR"] += 1
                try:
                    lt[nm(dc.LineType)] += 1
                except Exception:
                    lt["ERR"] += 1
        except Exception:
            pass
    print(f"   LineWeight: {dict(lw)}")
    print(f"   LineType  : {dict(lt)}")

    print("\n-- 치수 정밀도/소수 자릿수 --")
    dd = sh.DrawingDimensions
    prec = collections.Counter()
    comma = 0
    for i in range(1, dd.Count + 1):
        try:
            dim = dd.Item(i)
            prec[nm(dim.Precision)] += 1
            if "," in (dim.Text.Text or ""):
                comma += 1
        except Exception:
            pass
    print(f"   Precision: {dict(prec)}")
    print(f"   쉼표 소수점 사용 치수: {comma} / {dd.Count}")

    print("\n-- 표면거칠기 기호 내용 --")
    try:
        sts = sh.SurfaceTextureSymbols
        print(f"   count={sts.Count}")
        if sts.Count:
            s0 = sts.Item(1)
            members(s0, "SurfaceTextureSymbol")
            for a in ("Roughness", "RoughnessMax", "RoughnessMin", "SurfaceType",
                      "MachiningAllowance", "Lay", "AllAround"):
                try:
                    print(f"     {a} = {getattr(s0, a)!r}")
                except Exception:
                    pass
    except Exception as e:
        print("   FAIL", e)

    print("\n-- 기하공차 프레임 내용 (데이텀 포함?) --")
    try:
        fcfs = sh.FeatureControlFrames
        print(f"   count={fcfs.Count}")
        if fcfs.Count:
            f0 = fcfs.Item(1)
            members(f0, "FeatureControlFrame")
            for a in ("FeatureControlFrameRows", "AllAround", "Note"):
                try:
                    print(f"     {a} = {getattr(f0, a)!r}")
                except Exception:
                    pass
            try:
                rows = f0.FeatureControlFrameRows
                print(f"     rows={rows.Count}")
                r0 = rows.Item(1)
                members(r0, "Row")
                for a in ("Symbol", "Tolerance", "Datum", "DatumOne", "DatumTwo",
                          "DatumThree", "ToleranceValue"):
                    try:
                        v = getattr(r0, a)
                        print(f"       {a} = {v!r} {nm(v) if isinstance(v, int) else ''}")
                    except Exception:
                        pass
            except Exception as e:
                print("     rows failed:", type(e).__name__, str(e)[:80])
    except Exception as e:
        print("   FAIL", e)
    d.Close(True)
print("\nDONE")
