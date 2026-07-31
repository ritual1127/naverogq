import os
import glob
import win32com.client as w32

FIX = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
IDW = os.path.join(FIX, "probe_drawing.idw")
DWG = os.path.join(FIX, "probe_drawing.dwg")

print("=== is ODA File Converter installed? ===")
hits = []
for pat in (r"C:\Program Files\ODA\**\ODAFileConverter*.exe",
            r"C:\Program Files*\ODA*\**\*.exe"):
    hits += glob.glob(pat, recursive=True)
print("  ODA:", hits or "NOT FOUND")

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
C = w32.constants

print("\n=== make a DWG from the fixture drawing ===")
drw = w32.CastTo(app.Documents.Open(IDW, False), "DrawingDocument")
try:
    drw.SaveAs(DWG, True)
    print("  SaveAs dwg OK:", os.path.exists(DWG), os.path.getsize(DWG) if os.path.exists(DWG) else "")
except Exception as e:
    print("  SaveAs dwg FAIL:", str(e)[:200])
drw.Close(True)

print("\n=== can Inventor OPEN a .dwg? ===")
if os.path.exists(DWG):
    try:
        d = app.Documents.Open(DWG, False)
        print("  opened. DocumentType =", d.DocumentType,
              "(12292 == kDrawingDocumentObject)")
        print("  DisplayName:", d.DisplayName)
        try:
            dd = w32.CastTo(d, "DrawingDocument")
            print("  CastTo DrawingDocument OK, sheets =", dd.Sheets.Count)
            sh = dd.Sheets.Item(1)
            print("  sheet:", sh.Name, "views:", sh.DrawingViews.Count,
                  "dims:", sh.DrawingDimensions.Count)
            v = sh.DrawingViews.Item(1) if sh.DrawingViews.Count else None
            if v:
                print("  view curves:", v.DrawingCurves.Count)
        except Exception as e:
            print("  CastTo/inspect FAIL:", str(e)[:200])
        d.Close(True)
    except Exception as e:
        print("  Open dwg FAIL:", type(e).__name__, str(e)[:250])

print("\n=== does ezdxf read an Inventor-exported DXF? ===")
dxf = os.path.join(FIX, "probe_drawing.dxf")
if os.path.exists(dxf):
    import ezdxf
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    kinds = {}
    for e in msp:
        kinds[e.dxftype()] = kinds.get(e.dxftype(), 0) + 1
    print("  dxf version:", doc.dxfversion, "| modelspace entity types:", kinds)
    print("  layers:", [l.dxf.name for l in doc.layers][:15])
    dims = [e for e in msp if e.dxftype() == "DIMENSION"]
    print("  DIMENSION count:", len(dims))
    for d in dims[:3]:
        print("     dimstyle=", d.dxf.get("dimstyle"), "text=", d.dxf.get("text"),
              "measurement=", d.get_measurement())
    circles = [e for e in msp if e.dxftype() == "CIRCLE"]
    print("  CIRCLE count:", len(circles))
    for cc in circles[:3]:
        print(f"     center=({cc.dxf.center.x:.2f},{cc.dxf.center.y:.2f}) r={cc.dxf.radius:.3f}")
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    print("  INSERT (blocks, i.e. title block) count:", len(inserts))
    for ins in inserts[:5]:
        attrs = {a.dxf.tag: a.dxf.text for a in ins.attribs} if ins.attribs else {}
        print(f"     block={ins.dxf.name!r} attribs={attrs}")
print("\nDONE")

