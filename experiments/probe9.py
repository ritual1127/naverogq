import os
import win32com.client as w32
import ezdxf

FIX = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
DWG = os.path.join(FIX, "probe_drawing.dwg")
OUT = os.path.join(FIX, "from_dwg.dxf")

print("=== (a) DWG -> DXF via Inventor ===")
app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
d = w32.CastTo(app.Documents.Open(DWG, False), "DrawingDocument")
print("  sheets:", [d.Sheets.Item(i).Name for i in range(1, d.Sheets.Count + 1)])
try:
    d.SaveAs(OUT, True)
    print("  SaveAs dxf OK:", os.path.exists(OUT), os.path.getsize(OUT))
except Exception as e:
    print("  SaveAs dxf FAIL:", str(e)[:200])
d.Close(True)

print("\n=== (b) circles, including inside blocks ===")
src = OUT if os.path.exists(OUT) else os.path.join(FIX, "probe_drawing.dxf")
doc = ezdxf.readfile(src)
msp = doc.modelspace()


def walk(layout, depth=0, seen=None):
    seen = seen if seen is not None else set()
    for e in layout:
        t = e.dxftype()
        if t == "INSERT":
            if depth > 4 or e.dxf.name in seen:
                continue
            try:
                for sub in e.virtual_entities():
                    yield from walk([sub], depth + 1, seen | {e.dxf.name})
            except Exception:
                pass
        else:
            yield e


flat = {}
circles = []
for e in walk(msp):
    t = e.dxftype()
    flat[t] = flat.get(t, 0) + 1
    if t in ("CIRCLE", "ARC"):
        circles.append(e)
print("  flattened entity types:", flat)
print("  circles/arcs found after flattening:", len(circles))
for c in circles[:6]:
    print(f"     {c.dxftype()} center=({c.dxf.center.x:.3f},{c.dxf.center.y:.3f}) "
          f"r={c.dxf.radius:.4f} layer={c.dxf.layer!r}")

print("\n=== also check paperspace layouts ===")
for name in doc.layout_names():
    lay = doc.layouts.get(name)
    n = sum(1 for _ in lay)
    cs = sum(1 for e in walk(lay) if e.dxftype() in ("CIRCLE", "ARC"))
    dims = sum(1 for e in lay if e.dxftype() == "DIMENSION")
    print(f"  layout {name!r}: {n} entities, {cs} circles/arcs (flattened), {dims} dims")

print("\n=== (c) DIMENSION tolerance data ===")
for name in doc.layout_names():
    for e in doc.layouts.get(name).query("DIMENSION"):
        print(f"  -- dim in {name!r}")
        print("     measurement:", e.get_measurement())
        print("     dimtype:", e.dimtype, "text:", repr(e.dxf.get("text")))
        st = e.dxf.get("dimstyle")
        print("     dimstyle:", st)
        for attr in ("dimtol", "dimtp", "dimtm", "dimlim", "dimtdec", "dimrnd"):
            has = e.dxf.hasattr(attr)
            print(f"     entity override {attr}: has={has} val={e.dxf.get(attr, None)!r}")
        try:
            style = doc.dimstyles.get(st)
            print("     from dimstyle:", {a: style.dxf.get(a, None)
                                          for a in ("dimtol", "dimtp", "dimtm", "dimlim")})
        except Exception as ex:
            print("     dimstyle lookup failed:", ex)
        try:
            ovr = e.override()
            print("     resolved override dimtol/dimtp/dimtm:",
                  ovr.get("dimtol"), ovr.get("dimtp"), ovr.get("dimtm"))
        except Exception as ex:
            print("     override() failed:", type(ex).__name__, ex)
print("\nDONE")

