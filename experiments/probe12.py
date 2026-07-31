"""Probe 12: survey EVERY real drawing. Are dimensions really absent, or am I
reading the wrong place? Also look in sheet/view sketches and notes.
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

print(f"{'file':38} {'sh':>2} {'views':>5} {'DIMS':>5} {'notes':>5} "
      f"{'shSk':>4} {'vwSk':>4} {'symb':>4} {'tb':>12} {'border'}")
print("-" * 120)
for p in files:
    try:
        d = w32.CastTo(app.Documents.Open(p, False), "DrawingDocument")
    except Exception as e:
        print(f"{os.path.basename(p)[:36]:38} OPEN FAIL {type(e).__name__}")
        continue
    try:
        tot_dims = tot_notes = tot_shsk = tot_vwsk = tot_sym = 0
        views = 0
        tb = border = None
        for si in range(1, d.Sheets.Count + 1):
            sh = d.Sheets.Item(si)
            tot_dims += sh.DrawingDimensions.Count
            views += sh.DrawingViews.Count
            for coll, acc in (("DrawingNotes", "notes"), ("Sketches", "shsk"),
                              ("SketchedSymbols", "sym")):
                try:
                    n = getattr(sh, coll).Count
                except Exception:
                    n = 0
                if acc == "notes":
                    tot_notes += n
                elif acc == "shsk":
                    tot_shsk += n
                else:
                    tot_sym += n
            for vi in range(1, sh.DrawingViews.Count + 1):
                try:
                    tot_vwsk += sh.DrawingViews.Item(vi).Sketches.Count
                except Exception:
                    pass
            if tb is None:
                try:
                    tb = sh.TitleBlock.Name if sh.TitleBlock else "None"
                except Exception:
                    tb = "ERR"
            if border is None:
                try:
                    border = sh.Border.Name if sh.Border else "None"
                except Exception:
                    border = "ERR"
        print(f"{os.path.basename(p)[:36]:38} {d.Sheets.Count:>2} {views:>5} "
              f"{tot_dims:>5} {tot_notes:>5} {tot_shsk:>4} {tot_vwsk:>4} {tot_sym:>4} "
              f"{str(tb)[:12]:>12} {border}")
    finally:
        d.Close(True)

print("\n=== also: do the PARTS have dimensions in their sketches? ===")
for p in [x for x in glob.glob(os.path.join(BASE, "**", "*.ipt"), recursive=True)
          if "OldVersions" not in x][:8]:
    try:
        pd = w32.CastTo(app.Documents.Open(p, False), "PartDocument")
        cd = pd.ComponentDefinition
        sks = cd.Sketches.Count
        dims = sum(cd.Sketches.Item(i).DimensionConstraints.Count
                   for i in range(1, sks + 1))
        under = 0
        for i in range(1, sks + 1):
            sk = cd.Sketches.Item(i)
            if sk.ConstraintStatus == C.kUnderConstrainedConstraintStatus:
                under += 1
        print(f"  {os.path.basename(p)[:40]:42} sketches={sks:>2} "
              f"dimConstraints={dims:>3} underConstrained={under:>2} "
              f"holes={cd.Features.HoleFeatures.Count:>2} "
              f"material={cd.Material.Name!r}")
        pd.Close(True)
    except Exception as e:
        print(f"  {os.path.basename(p)[:40]:42} FAIL {type(e).__name__}: {str(e)[:60]}")
print("\nDONE")
