"""Probe 21: can we read the things the exam actually scores?

Surface-texture symbols and geometric-tolerance frames are 오작 (instant fail)
if missing, so being able to count them reliably is the whole point.
"""
import glob
import os
import win32com.client as w32

BASE = r"C:\Users\smile\OneDrive\Desktop\캐드 파일"
files = [p for p in glob.glob(os.path.join(BASE, "**", "*.idw"), recursive=True)
         if "OldVersions" not in p]

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants

# every annotation collection a Sheet exposes, per probe4's dir() dump
COLLS = ["SurfaceTextureSymbols", "FeatureControlFrames", "DatumIdentifierSymbols",
         "DatumTargetSymbols", "Centerlines", "Centermarks", "DrawingNotes",
         "PartsLists", "Balloons", "HoleTables", "RevisionTables", "WeldingSymbols",
         "EdgeSymbols", "SketchedSymbols", "TransitionSymbols", "RevisionClouds",
         "LeaderNotes", "Leaders", "GeneralNotes"]

print("sheet size / scale / projection + annotation counts\n")
for p in files:
    try:
        d = w32.CastTo(app.Documents.Open(p, False), "DrawingDocument")
    except Exception as e:
        print(f"{os.path.basename(p)}: OPEN FAIL {type(e).__name__}")
        continue
    sh = d.Sheets.Item(1)
    print("=" * 72)
    print(f"{os.path.basename(p)}")
    try:
        st = d.StylesManager.ActiveStandardStyle
        proj = "제1각법" if st.FirstAngleProjection else "제3각법"
    except Exception:
        proj = "?"
    print(f"  sheet {sh.Width:.0f} x {sh.Height:.0f} mm  Size={sh.Size}  "
          f"orientation={getattr(sh, 'Orientation', '?')}  {proj}")
    scales = []
    for vi in range(1, sh.DrawingViews.Count + 1):
        v = sh.DrawingViews.Item(vi)
        try:
            scales.append(v.ScaleString)
        except Exception:
            pass
    print(f"  views={sh.DrawingViews.Count} scales={sorted(set(scales))}")
    got = {}
    for c in COLLS:
        try:
            got[c] = getattr(sh, c).Count
        except Exception:
            got[c] = None
    for c in COLLS:
        v = got[c]
        if v is None:
            continue
        mark = "  <-- " if v else ""
        print(f"     {c:26} {v}{mark}")
    missing = [c for c in COLLS if got[c] is None]
    if missing:
        print(f"     (no such collection: {', '.join(missing)})")

    # what do the notes actually say? 주서 is scored
    try:
        for i in range(1, min(sh.DrawingNotes.Count, 4) + 1):
            n = sh.DrawingNotes.Item(i)
            txt = (n.Text or "").replace("\r", " ").replace("\n", " ")[:110]
            print(f"     note {i}: {txt!r}")
    except Exception as e:
        print("     notes unreadable:", type(e).__name__)
    d.Close(True)
print("\nDONE")
