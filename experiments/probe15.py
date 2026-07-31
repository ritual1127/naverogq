"""Probe 15: can Inventor read a REAL AutoCAD .dwg well enough to skip ODA?

Earlier I only tested a DWG that Inventor itself had written, which is not the
same thing. These are files the user actually uploaded.
"""
import os
import sys
import win32com.client as w32

DWGS = [r"C:\Users\smile\AppData\Local\cad-checker\uploads\b5e902f77758\075em07z.dwg",
        r"C:\Users\smile\AppData\Local\cad-checker\uploads\fd6abc35d106\부품2.dwg"]
OUT = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
os.makedirs(OUT, exist_ok=True)

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants
D = w32.constants.__dict__.get("__dicts__", [{}])[0]


def nm(v):
    return ([k for k, x in D.items() if x == v] or [str(v)])[0]


def try_(label, fn):
    try:
        v = fn()
        print(f"    OK   {label} = {v!r}")
        return v
    except Exception as e:
        print(f"    --   {label}: {type(e).__name__}: {str(e)[:110]}")
        return None


for path in DWGS:
    print("\n" + "=" * 72)
    print(os.path.basename(path), os.path.getsize(path), "bytes")
    print("=" * 72)
    try:
        raw = app.Documents.Open(path, False)
    except Exception as e:
        print("  OPEN FAILED:", type(e).__name__, str(e)[:200])
        continue
    print("  DocumentType:", raw.DocumentType, nm(raw.DocumentType))
    try:
        doc = w32.CastTo(raw, "DrawingDocument")
        print("  cast to DrawingDocument OK, sheets =", doc.Sheets.Count)
    except Exception as e:
        print("  cast FAIL:", str(e)[:150])
        raw.Close(True)
        continue

    for si in range(1, doc.Sheets.Count + 1):
        sh = doc.Sheets.Item(si)
        print(f"\n  --- sheet {si}: {sh.Name!r} ---")
        for coll in ("DrawingViews", "DrawingDimensions", "DrawingNotes",
                     "Sketches", "AutoCADBlocks", "SketchedSymbols"):
            try:
                print(f"    {coll}.Count = {getattr(sh, coll).Count}")
            except Exception as e:
                print(f"    {coll}: {type(e).__name__}")

        # AutoCAD content lives in blocks -- look inside one
        try:
            blocks = sh.AutoCADBlocks
            for bi in range(1, min(blocks.Count, 3) + 1):
                b = blocks.Item(bi)
                print(f"    block {bi}: {getattr(b, 'Name', '?')!r}")
                print("      members:", ", ".join(
                    sorted(x for x in dir(b) if not x.startswith("_") and x[0].isupper())))
        except Exception as e:
            print("    AutoCADBlocks walk failed:", type(e).__name__, str(e)[:100])

        # sheet sketches often hold imported 2D geometry
        try:
            for ki in range(1, min(sh.Sketches.Count, 2) + 1):
                sk = sh.Sketches.Item(ki)
                print(f"    sketch {ki} {sk.Name!r}: entities={sk.SketchEntities.Count} "
                      f"dims={sk.DimensionConstraints.Count}")
                kinds = {}
                for e in sk.SketchEntities:
                    t = nm(e.Type)
                    kinds[t] = kinds.get(t, 0) + 1
                print("      entity types:", kinds)
        except Exception as e:
            print("    sketch walk failed:", type(e).__name__, str(e)[:100])

    print("\n  --- export attempts ---")
    for ext in ("dxf", "idw"):
        out = os.path.join(OUT, f"conv_{os.path.splitext(os.path.basename(path))[0]}.{ext}")
        if os.path.exists(out):
            try:
                os.remove(out)
            except Exception:
                pass
        try:
            doc.SaveAs(out, True)
            ok = os.path.exists(out)
            print(f"    SaveAs .{ext}: {'OK ' + str(os.path.getsize(out)) if ok else 'NO FILE WRITTEN'}")
        except Exception as e:
            print(f"    SaveAs .{ext}: FAIL {str(e)[:130]}")
    doc.Close(True)

print("\nDONE")
