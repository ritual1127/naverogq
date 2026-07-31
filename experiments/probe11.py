import sys
import win32com.client as w32

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\1본체.idw"

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants
D = w32.constants.__dict__.get("__dicts__", [{}])[0]


def nm(v):
    return ([k for k, x in D.items() if x == v] or [v])[0]


doc = w32.CastTo(app.Documents.Open(PATH, False), "DrawingDocument")
print("sheets:", doc.Sheets.Count)
for si in range(1, doc.Sheets.Count + 1):
    sh = doc.Sheets.Item(si)
    print(f"\n=== sheet {si}: {sh.Name!r} ===")
    dd = sh.DrawingDimensions
    print("  DrawingDimensions.Count =", dd.Count)
    for coll in ("GeneralDimensions", "BaselineDimensionSets", "ChainDimensionSets",
                 "OrdinateDimensionSets", "OrdinateDimensions"):
        try:
            print(f"    {coll}.Count = {getattr(dd, coll).Count}")
        except Exception as e:
            print(f"    {coll}: {type(e).__name__}")

    print("  -- what ARE the items in DrawingDimensions? --")
    kinds = {}
    for i in range(1, dd.Count + 1):
        try:
            t = dd.Item(i).Type
            kinds[nm(t)] = kinds.get(nm(t), 0) + 1
        except Exception as e:
            kinds[f"ERR {type(e).__name__}"] = kinds.get(f"ERR {type(e).__name__}", 0) + 1
    for k, v in sorted(kinds.items()):
        print(f"     {k}: {v}")

    print("  -- title block --")
    for attr in ("TitleBlock", "Border"):
        try:
            o = getattr(sh, attr)
            print(f"     {attr} = {o!r}")
            if o is not None:
                print(f"       .Name = {o.Name!r}")
        except Exception as e:
            print(f"     {attr} FAIL: {type(e).__name__}: {str(e)[:110]}")
    for coll in ("SketchedSymbols", "DrawingNotes", "PartsLists"):
        try:
            print(f"     {coll}.Count = {getattr(sh, coll).Count}")
        except Exception as e:
            print(f"     {coll}: {type(e).__name__}")

    print("  -- views and their curve counts --")
    for vi in range(1, sh.DrawingViews.Count + 1):
        v = sh.DrawingViews.Item(vi)
        try:
            n = v.DrawingCurves.Count
        except Exception:
            n = "ERR"
        print(f"     view {vi} {v.Name!r} scale={v.Scale} type={nm(v.ViewType)} curves={n}")

    print("  -- first 6 dims in detail --")
    shown = 0
    for i in range(1, dd.Count + 1):
        if shown >= 6:
            break
        try:
            dim = dd.Item(i)
        except Exception:
            continue
        shown += 1
        print(f"     #{i} Type={nm(dim.Type)}")
        for a in ("ModelValue", "Retrieved"):
            try:
                print(f"        {a} = {getattr(dim, a)!r}")
            except Exception as e:
                print(f"        {a}: {type(e).__name__}")
        try:
            print(f"        Text.Text = {dim.Text.Text!r}")
        except Exception as e:
            print(f"        Text: {type(e).__name__}")
        try:
            print(f"        Tolerance.ToleranceType = {nm(dim.Tolerance.ToleranceType)}")
        except Exception as e:
            print(f"        Tolerance: {type(e).__name__}")

doc.Close(True)
print("\nDONE")

