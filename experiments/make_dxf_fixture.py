"""Build a DXF fixture with known-wrong content, and verify SVG rendering.

Inventor's own DXF export turns circles into splines, so it can't stand in for a
human-authored AutoCAD file. This writes a real DXF containing genuine CIRCLE
and DIMENSION entities with deliberate defects, so dwg.py has something honest
to be tested against.
"""
import os
import ezdxf
from ezdxf.enums import TextEntityAlignment

FIX = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
os.makedirs(FIX, exist_ok=True)
OUT = os.path.join(FIX, "sample_plate.dxf")

doc = ezdxf.new("R2010", setup=True)
msp = doc.modelspace()
doc.layers.add("OUTLINE", color=7)
doc.layers.add("DIMS", color=1)

# 120 x 80 plate
msp.add_lwpolyline([(0, 0), (120, 0), (120, 80), (0, 80)], close=True,
                   dxfattribs={"layer": "OUTLINE"})

# four holes: two will get dimensions, two will not
holes = [(20, 20, 6.0), (100, 20, 6.0), (20, 60, 1.2), (100, 60, 12.5)]
for x, y, r in holes:
    msp.add_circle((x, y), r, dxfattribs={"layer": "OUTLINE"})

# dimension WITH a sane tolerance
d1 = msp.add_linear_dim(base=(0, -15), p1=(0, 0), p2=(120, 0),
                        dxfattribs={"layer": "DIMS"},
                        override={"dimtol": 1, "dimtp": 0.05, "dimtm": 0.05})
d1.render()
# dimension with NO tolerance
d2 = msp.add_linear_dim(base=(-20, 0), p1=(0, 0), p2=(0, 80),
                        dxfattribs={"layer": "DIMS"})
d2.render()
# dimension with an INVERTED tolerance (upper < lower)
d3 = msp.add_linear_dim(base=(0, 95), p1=(20, 80), p2=(100, 80),
                        dxfattribs={"layer": "DIMS"},
                        override={"dimtol": 1, "dimtp": -0.2, "dimtm": 0.3})
d3.render()
# diameter dim on ONE hole only (20,20)
d4 = msp.add_diameter_dim(center=(20, 20), radius=6.0, angle=45,
                          dxfattribs={"layer": "DIMS"})
d4.render()

# a title block-ish block with attributes, one of them empty
blk = doc.blocks.new(name="TITLEBLOCK")
blk.add_lwpolyline([(0, 0), (80, 0), (80, 25), (0, 25)], close=True)
for tag, default, y in (("PART_NUMBER", "PLATE-001", 18),
                        ("MATERIAL", "", 12),
                        ("DESIGNER", "smile", 6)):
    blk.add_attdef(tag=tag, insert=(2, y), height=3.0,
                   dxfattribs={"prompt": tag})
ins = msp.add_blockref("TITLEBLOCK", (130, 0))
ins.add_auto_attribs({"PART_NUMBER": "PLATE-001", "MATERIAL": "", "DESIGNER": "smile"})

msp.add_text("SAMPLE PLATE", height=5,
             dxfattribs={"layer": "OUTLINE"}).set_placement((0, 100))
doc.saveas(OUT)
print("wrote", OUT, os.path.getsize(OUT), "bytes")

# --- what does ezdxf's SVG backend actually expose in 1.4.x? ---------------
print("\n=== SVG backend API check ===")
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing import svg, layout as dlayout

back = svg.SVGBackend()
Frontend(RenderContext(doc), back).draw_layout(msp)
page = dlayout.Page(0, 0, dlayout.Units.mm, dlayout.Margins.all(5))
s = back.get_string(page)
svg_path = OUT.replace(".dxf", ".svg")
with open(svg_path, "w", encoding="utf-8") as fh:
    fh.write(s)
print("  svg bytes:", len(s), "->", svg_path)
print("  starts with:", s[:120].replace("\n", " "))
import re
m = re.search(r'viewBox="([^"]+)"', s)
print("  viewBox:", m.group(1) if m else "NONE")
m2 = re.search(r'width="([^"]+)"\s+height="([^"]+)"', s)
print("  width/height:", m2.groups() if m2 else "NONE")

# --- read it back the way dwg.py will ---------------------------------------
print("\n=== read-back check ===")
d = ezdxf.readfile(OUT)
m = d.modelspace()
print("  circles:", len(m.query("CIRCLE")))
for c in m.query("CIRCLE"):
    print(f"     center=({c.dxf.center.x:g},{c.dxf.center.y:g}) d={c.dxf.radius * 2:g}")
print("  dimensions:", len(m.query("DIMENSION")))
for e in m.query("DIMENSION"):
    ovr = e.override()
    print(f"     measurement={e.get_measurement()!r} dimtol={ovr.get('dimtol')!r} "
          f"dimtp={ovr.get('dimtp')!r} dimtm={ovr.get('dimtm')!r} type={e.dimtype}")
print("  inserts:", len(m.query("INSERT")))
for i in m.query("INSERT"):
    print("     ", i.dxf.name, {a.dxf.tag: a.dxf.text for a in i.attribs})
