"""Probe 17: does unit detection give sane millimetres for all three sources?"""
import os
import dwg

TESTS = [
    (r"C:\Users\smile\AppData\Local\cad-checker\uploads\b5e902f77758\075em07z.dwg",
     "AutoCAD DWG (declares unitless, really metres)"),
    (r"C:\Users\smile\AppData\Local\cad-checker\uploads\fd6abc35d106\부품2.dwg",
     "Inventor-authored DWG (declares mm)"),
    (os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures",
                  "sample_plate.dxf"),
     "synthetic fixture (declares metres, really mm; plate is 120x80, holes 12/12/2.4/25)"),
]

for path, label in TESTS:
    if not os.path.exists(path):
        print(f"\n{label}\n   missing: {path}")
        continue
    f = dwg.analyze(path)
    sh = f["sheets"][0]
    print(f"\n{label}")
    print(f"   scale : {f['unit_mm_per_drawing_unit']:g} mm/unit   [{f['unit_source']}]")
    print(f"   dims  : {[round(d['value_mm'], 2) for d in sh['dims'][:6]]}")
    print(f"   holes : {[(round(c['diameter_mm'], 2), c['count']) for c in sh['undimensioned'][:6]]}")
