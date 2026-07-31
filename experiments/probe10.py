import os
import re
import ezdxf
from ezdxf import bbox
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing import svg, layout as dlayout

FIX = os.path.join(os.environ["LOCALAPPDATA"], "cad-checker", "fixtures")
DXF = os.path.join(FIX, "sample_plate.dxf")
MARGIN_MM = 5.0

doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

back = svg.SVGBackend()
Frontend(RenderContext(doc), back).draw_layout(msp)
page = dlayout.Page(0, 0, dlayout.Units.mm, dlayout.Margins.all(MARGIN_MM))
s = back.get_string(page)

vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', s).group(1).split()]
w_mm = float(re.search(r'width="([\d.]+)mm"', s).group(1))
h_mm = float(re.search(r'height="([\d.]+)mm"', s).group(1))
print(f"viewBox={vb}  page={w_mm}x{h_mm} mm")

bb = bbox.extents(msp)
print(f"dxf extents: min=({bb.extmin.x:.4f},{bb.extmin.y:.4f}) "
      f"max=({bb.extmax.x:.4f},{bb.extmax.y:.4f})  "
      f"size=({bb.size.x:.4f},{bb.size.y:.4f})")

upm = vb[2] / w_mm
print(f"units per mm = {upm:.4f}")
print(f"content mm = {w_mm - 2 * MARGIN_MM:.4f} x {h_mm - 2 * MARGIN_MM:.4f}"
      f"   (dxf size {bb.size.x:.4f} x {bb.size.y:.4f})")


def to_svg(x, y):
    return ((x - bb.extmin.x + MARGIN_MM) * upm,
            (bb.extmax.y - y + MARGIN_MM) * upm)


paths = re.findall(r'd="M ([\d.-]+) ([\d.-]+) l 545076 0', s)
print("\nobserved plate origin in svg:", paths[:1])
pred = to_svg(0, 0)
print(f"predicted     plate origin: ({pred[0]:.1f}, {pred[1]:.1f})")
if paths:
    obs = (float(paths[0][0]), float(paths[0][1]))
    err = (abs(obs[0] - pred[0]), abs(obs[1] - pred[1]))
    print(f"error: ({err[0]:.1f}, {err[1]:.1f}) viewBox units "
          f"= ({err[0] / upm:.4f}, {err[1] / upm:.4f}) mm")
    ok = err[0] < 2 and err[1] < 2
    print("TRANSFORM EXACT" if ok else "TRANSFORM WRONG")

print("\ncircle centres: predicted vs observed")
for c in msp.query("CIRCLE"):
    cx, cy, r = c.dxf.center.x, c.dxf.center.y, c.dxf.radius
    px, py = to_svg(cx, cy)
    sx, sy = to_svg(cx + r, cy)
    hit = re.search(rf'd="M {sx:.0f}', s) or re.search(rf'd="M {sx - 1:.0f}', s) \
        or re.search(rf'd="M {sx + 1:.0f}', s)
    print(f"  dxf({cx:g},{cy:g}) r={r:g} -> svg({px:.0f},{py:.0f}) "
          f"arc-start({sx:.0f},{sy:.0f}) found_in_svg={bool(hit)}")

print(f"\nradius scale check: 1 dxf unit = {upm:.4f} svg units "
      f"(so r={6.0:g} -> {6.0 * upm:.0f})")

