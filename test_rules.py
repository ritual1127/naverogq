import re
import os
import tempfile

import exam


def codes(findings):
    return {f["code"] for f in findings}


def test_text_tolerance_state():
    explicit = ["52-0.03^-0.05", "n10+0.1^  0", "3+0.1^  0", "14+0.2^  0", "3±0.007"]
    fit = ["Ø17js5", "n17js5", "5N9", "n14h6", "20H7", "30g6"]
    na = ["R0.3", "R0.5", "R2", "M10", "(R)", "(25)"]
    plain = ["12", "24", "13.5", "n20", "n26", "Ø14.9", "9", "3", "15"]
    for t in explicit:
        assert exam.text_tolerance_state(t) == "explicit", t
    for t in fit:
        assert exam.text_tolerance_state(t) == "fit", t
    for t in na:
        assert exam.text_tolerance_state(t) == "not_applicable", t
    for t in plain:
        assert exam.text_tolerance_state(t) == "plain", t
    assert exam.text_tolerance_state("") == "plain"
    assert exam.text_tolerance_state(None) == "plain"


def test_unit_detection():
    import ezdxf
    import dwg

    def doc_with(insunits, size):
        d = ezdxf.new("R2010")
        d.header["$INSUNITS"] = insunits
        d.modelspace().add_lwpolyline(
            [(0, 0), (size, 0), (size, size * 0.6), (0, size * 0.6)], close=True)
        return d

    d = doc_with(4, 210)
    assert dwg.detect_mm_per_unit(d, d.modelspace())[0] == 1.0
    d = doc_with(0, 0.12)
    assert dwg.detect_mm_per_unit(d, d.modelspace())[0] == 1000.0
    d = doc_with(6, 210)
    k, why = dwg.detect_mm_per_unit(d, d.modelspace())
    assert k == 1.0, f"should reject the implausible declaration, got {k} ({why})"
    d = doc_with(6, 0.12)
    assert dwg.detect_mm_per_unit(d, d.modelspace())[0] == 1000.0
    d = doc_with(1, 12)
    assert dwg.detect_mm_per_unit(d, d.modelspace())[0] == 25.4


def test_render_margin_scales_for_meter_drawings():
    import ezdxf
    import dwg
    from ezdxf import bbox

    def margin_for(size):
        doc = ezdxf.new("R2010")
        doc.modelspace().add_line((0, 0), (size, size * 0.6))
        return dwg._drawing_margin(bbox.extents(doc.modelspace()))

    assert abs(margin_for(0.12) - 0.006) < 1e-9
    assert margin_for(210) == dwg.MARGIN_MM

    doc = ezdxf.new("R2010")
    doc.layers.add("SOURCE_RED", color=1)
    doc.layers.add(dwg.ERR_LAYER, color=1)
    source = doc.modelspace().add_line((0, 0), (1, 1),
                                       dxfattribs={"layer": "SOURCE_RED",
                                                   "color": 1})
    marker = doc.modelspace().add_circle((0, 0), 1,
                                         dxfattribs={"layer": dwg.ERR_LAYER,
                                                     "color": 1})
    dwg._prepare_preview_colors(doc)
    assert source.dxf.color == 7
    assert doc.layers.get("SOURCE_RED").color == 7
    assert marker.dxf.color == 1
    assert doc.layers.get(dwg.ERR_LAYER).color == 1

    svg, _ = dwg._finish(doc, doc.modelspace())
    widths = [int(value) for value in re.findall(r"stroke-width: (\d+)", svg)]
    assert widths and max(widths) < 5000, widths


def test_badges_sit_next_to_their_target():
    import math

    import dwg

    span = 1000.0
    badge_r = span * 0.016
    targets = [(100, 100), (500, 400), (900, 150)]
    rings = [span * 0.01] * 3
    spots = dwg._badge_positions(span, targets, rings)

    for (tx, ty), ring, (bx, by) in zip(targets, rings, spots):
        d = math.hypot(bx - tx, by - ty)
        assert d >= ring + badge_r, "badge clears the ring it points at"
        assert d <= ring + badge_r * 4, f"badge stays beside its target, not {d:.0f} away"


def test_badges_never_cover_each_other():
    import math

    import dwg

    span = 1000.0
    # eight findings on the same circle: they cannot all take the first spot
    targets = [(500, 500)] * 8
    rings = [span * 0.008] * 8
    spots = dwg._badge_positions(span, targets, rings)

    clear = span * 0.016 * 2.15
    for i, (ax, ay) in enumerate(spots):
        for bx, by in spots[i + 1:]:
            assert math.hypot(ax - bx, ay - by) >= clear - 1e-9, "badges overlap"


def test_badges_do_not_grow_the_drawing():
    import ezdxf
    from ezdxf import bbox

    import dwg

    doc = ezdxf.new("R2010")
    space = doc.modelspace()
    space.add_lwpolyline([(0, 0), (400, 0), (400, 300), (0, 300)], close=True)
    space.add_circle((200, 150), 6)
    before = bbox.extents(space)

    doc.layers.add(dwg.ERR_LAYER, color=1)
    span = max(before.size.x, before.size.y)
    ring = span * 0.01
    (bx, by), = dwg._badge_positions(span, [(200, 150)], [ring])
    dwg._arrow(space, 200, 150, ring, span, "1", bx, by)

    after = bbox.extents(space)
    assert after.size.x <= before.size.x + 1e-6
    assert after.size.y <= before.size.y + 1e-6,         "markers must not inflate the preview canvas"


def test_arrow_draws_a_ring_leader_and_badge():
    import ezdxf
    import dwg

    doc = ezdxf.new("R2010")
    space = doc.modelspace()
    space.add_line((0, 0), (100, 100))
    span = 100.0
    for i, radius in enumerate((2, 4, 8, 16), 1):
        ring = min(max(radius * 1.12, span * 0.006), span * 0.018)
        dwg._arrow(space, 50, 50, ring, span, str(i), 120.0, 90.0 - i * 5)

    labels = list(space.query(f'TEXT[layer=="{dwg.ERR_LAYER}"]'))
    assert len(labels) == 4
    assert len({round(label.dxf.insert.y, 6) for label in labels}) == 4
    assert max(label.dxf.height for label in labels) == span * 0.022
    leaders = list(space.query(f'LINE[layer=="{dwg.ERR_LAYER}"]'))
    assert leaders and all(line.dxf.lineweight == 100 for line in leaders)
    badges = list(space.query(f'CIRCLE[layer=="{dwg.ERR_LAYER}"]'))
    assert len(badges) == 8, "one ring on the target plus one badge per marker"
    discs = list(space.query(f'HATCH[layer=="{dwg.ERR_LAYER}"]'))
    assert len(discs) == 4, "each badge is backed by a filled disc"


def test_recovers_orphaned_inventor_paper_views():
    import ezdxf
    import dwg

    doc = ezdxf.new("R2013")
    layout = doc.layouts.new("시트")
    layout.add_viewport(center=(100, 80), size=(60, 40),
                        view_center_point=(0, 0), view_height=20,
                        dxfattribs={"id": 2})
    block = doc.blocks.new("부품_시트_뷰1")
    block.add_circle((0, 0), 8)
    block.add_line((-10, 0), (10, 0))

    path = os.path.join(tempfile.mkdtemp(), "orphaned.dxf")
    doc.saveas(path)
    assert not dwg.dxf_has_content(path)
    assert dwg.recover_orphaned_paper_views(path)
    restored = ezdxf.readfile(path)
    inserts = list(restored.modelspace().query("INSERT"))
    assert len(inserts) == 1
    assert inserts[0].dxf.name == "부품_시트_뷰1"


def test_marker_index_targets_the_actual_dimension_finding():
    import ezdxf
    import main

    doc = ezdxf.new("R2013")
    doc.modelspace().add_circle((10, 10), 2)
    path = os.path.join(tempfile.mkdtemp(), "markers.dxf")
    doc.saveas(path)
    circle = {"diameter_mm": 4.0, "count": 1,
              "dxf_x": 10.0, "dxf_y": 10.0, "dxf_r": 2.0}

    facts = {"dxf": path, "sheets": [
        {"name": "Model", "dims": [], "undimensioned": [circle]}]}
    _, _, index, _, _ = main._render(facts)
    assert index[0]["finding_code"] == "EX_NO_DIMS"

    facts["sheets"][0]["dims"] = [{"value_mm": 10.0}]
    _, _, index, _, _ = main._render(facts)
    assert index[0]["finding_code"] == "EX_DIM_MISSING"


def test_surface_and_geometric_text_detection():
    import dwg

    assert dwg._surface_symbol("√y")["max"] == "y"
    assert dwg._surface_symbol("Ra 1.6")["max"] == "1.6"
    assert dwg._surface_symbol("√")["max"] is None, "빈 기호는 값 없음으로 잡혀야 한다"
    assert dwg._surface_symbol("주조 흑피 √")["no_machining"] is True
    assert dwg._surface_symbol("160") is None
    assert dwg._surface_symbol("1. 일반공차 KS B ISO 2768-m") is None
    for axis in ("X", "Y", "Z"):
        assert dwg._surface_symbol(axis) is None, "축·뷰 문자는 거칠기 기호가 아니다"
    assert dwg._surface_symbol("√Y")["max"] == "y", "기호가 붙으면 대문자도 인정"
    assert dwg._surface_symbol("표면거칠기 √") is None, "주서 문구는 면의 기호가 아니다"

    g = dwg._geometric_tol("⊥%%v0.011%%vA")
    assert g["tolerance"] == "0.011" and g["datums"] == ["A"]
    assert dwg._geometric_tol("◎%%v0.02")["datums"] == []
    assert dwg._geometric_tol("{\\Fgdt;j}%%v0.011%%vA")["tolerance"] == "0.011"
    assert dwg._geometric_tol("Ø17js5") is None


def test_note_text_is_not_every_string_on_the_sheet():
    import dwg

    assert dwg._is_note("1. 일반공차 - 가) 가공부: KS B ISO 2768-m")
    assert dwg._is_note("열처리 HRC50")
    assert not dwg._is_note("√y")
    assert not dwg._is_note("160")


def test_bench_fixtures_are_graded_exactly():
    import tempfile

    import bench

    with tempfile.TemporaryDirectory() as tmp:
        rows, m = bench.run(bench.fixtures(tmp))
    bad = [r for r in rows if r["miss"] or r["extra"] or r["error"]]
    assert not bad, bad
    assert m["recall"] == 1.0 and m["precision"] == 1.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} checks passed")
