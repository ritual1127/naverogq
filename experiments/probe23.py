"""Probe 23: are the "empty roughness" symbols real omissions, or legitimate
'제거가공 불가' symbols that correctly carry no Ra value?
"""
import os
import win32com.client as w32

PATH = r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\5커버(2개).idw"

app = w32.Dispatch("Inventor.Application")
app.Visible = False
app.SilentOperation = True
D = w32.constants.__dict__.get("__dicts__", [{}])[0]


def nm(v):
    return ([k for k, x in D.items() if x == v] or [str(v)])[0]


print("SurfaceTextureType constants:")
for k, v in sorted(D.items()):
    if "surfacetexture" in k.lower() or "SurfaceType" in k:
        print(f"   {k} = {v}")

d = w32.CastTo(app.Documents.Open(PATH, False), "DrawingDocument")
sh = d.Sheets.Item(1)
coll = sh.SurfaceTextureSymbols
print(f"\n{coll.Count} symbols on {os.path.basename(PATH)}\n")
print(f"{'#':>3}  {'type':34} {'max':>10} {'min':>8} {'method':>10}")
for i in range(1, coll.Count + 1):
    s = coll.Item(i)
    vals = {}
    for a in ("MaximumRoughness", "MinimumRoughness", "ProductionMethod",
              "SurfaceTextureType", "MachiningAllowance", "SurfaceWaviness"):
        try:
            vals[a] = getattr(s, a)
        except Exception:
            vals[a] = "ERR"
    t = vals["SurfaceTextureType"]
    print(f"{i:>3}  {nm(t)[:34]:34} {str(vals['MaximumRoughness'])[:10]:>10} "
          f"{str(vals['MinimumRoughness'])[:8]:>8} {str(vals['ProductionMethod'])[:10]:>10}")
d.Close(True)
print("\nIf the blank ones are kBasicSurfaceTexture / material-removal-prohibited,"
      "\nthen a missing Ra value is CORRECT and must not be flagged.")
