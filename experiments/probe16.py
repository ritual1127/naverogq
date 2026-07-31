import os
import ezdxf

U = {0: "unitless", 1: "inch", 2: "feet", 3: "mile", 4: "mm", 5: "cm",
     6: "m", 7: "km", 8: "microinch", 9: "mil", 10: "yard"}

FILES = [
    os.path.join(os.environ["TEMP"], "v2.dxf"),
    os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures",
                 "sample_plate.dxf"),
    os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures",
                 "conv_부품2.dxf"),
]

for p in FILES:
    if not os.path.exists(p):
        print(f"{os.path.basename(p)}: missing")
        continue
    d = ezdxf.readfile(p)
    h = d.header
    ins = h.get("$INSUNITS", None)
    print(f"\n{os.path.basename(p)}")
    print(f"   $INSUNITS = {ins} ({U.get(ins, '?')})   "
          f"$MEASUREMENT = {h.get('$MEASUREMENT', None)}")
    print(f"   $EXTMIN = {h.get('$EXTMIN', None)}")
    print(f"   $EXTMAX = {h.get('$EXTMAX', None)}")
    rs = sorted({round(e.dxf.radius, 5)
                 for e in d.modelspace() if e.dxftype() in ("CIRCLE", "ARC")})
    print(f"   distinct radii: {rs[:14]}")
    if rs:
        print(f"   radius range: {rs[0]} .. {rs[-1]}")
    try:
        from ezdxf import bbox
        bb = bbox.extents(d.modelspace())
        print(f"   drawing size: {bb.size.x:.4f} x {bb.size.y:.4f} (drawing units)")
    except Exception as e:
        print("   bbox failed:", e)

