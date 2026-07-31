import re

import rules as R


def codes(findings):
    return {f["code"] for f in findings}


def test_iso2768():
    assert R.iso2768_m(2) == 0.10
    assert R.iso2768_m(3) == 0.10, "boundary is inclusive"
    assert R.iso2768_m(3.1) == 0.10
    assert R.iso2768_m(30) == 0.20
    assert R.iso2768_m(30.1) == 0.30
    assert R.iso2768_m(-120) == 0.30, "sign must not matter"
    assert R.iso2768_m(99999) is None, "off the end of the table"


def test_sketches():
    f = R.check_sketches({"sketches": [
        {"name": "s1", "status": "under", "entities": 87, "under_count": 28},
        {"name": "s2", "status": "full", "entities": 4, "under_count": 0},
        {"name": "s3", "status": "over", "entities": 9, "under_count": 0},
    ]})
    assert codes(f) == {"SKETCH_UNDER_CONSTRAINED", "SKETCH_OVER_CONSTRAINED"}
    assert "28" in [x for x in f if x["code"] == "SKETCH_UNDER_CONSTRAINED"][0]["detail"]


def test_holes():
    f = R.check_holes({"holes": [
        {"name": "h1", "diameter_mm": 1.5, "depth_mm": 5},
        {"name": "h2", "diameter_mm": 10.0, "depth_mm": 200},
        {"name": "h3", "diameter_mm": 8.0, "depth_mm": 16},
    ]})
    assert codes(f) == {"HOLE_TOO_SMALL", "HOLE_TOO_DEEP"}
    assert len(f) == 2
    assert R.check_holes({"holes": [{"name": "x", "diameter_mm": R.MIN_HOLE_DIA_MM,
                                     "depth_mm": None}]}) == []


def test_walls():
    f = R.check_walls({"walls": [{"faces": [6, 26], "gap_mm": 2.0},
                                 {"faces": [1, 2], "gap_mm": 0.8}]})
    assert len(f) == 1 and f[0]["where"]["faces"] == [1, 2]


def test_material():
    def part(mat):
        return {"kind": "part", "props": {"material": mat}}
    assert codes(R.check_material(part("일반"))) == {"MATERIAL_NOT_SET"}
    assert codes(R.check_material(part("Generic"))) == {"MATERIAL_NOT_SET"}
    assert codes(R.check_material(part(""))) == {"MATERIAL_NOT_SET"}
    assert R.check_material(part("SS400")) == []
    assert R.check_material({"kind": "drawing", "props": {"material": ""}}) == []
    assert R.check_material({"kind": "assembly", "props": {"material": ""}}) == []


def test_props():
    f = R.check_props({"props": {"part_number": "", "designer": "smile", "material": "일반"}})
    assert codes(f) == {"PROP_MISSING"}
    assert f[0]["where"]["prop"] == "part_number"


def test_tolerances():
    sheets = [{"name": "s1", "dims": [
        {"value_mm": 30.0, "tol_type": "none", "text": "30", "x_cm": 1, "y_cm": 2},
        {"value_mm": 20.0, "tol_type": "deviation", "upper_mm": -0.1, "lower_mm": 0.1,
         "text": "20"},
        {"value_mm": 10.0, "tol_type": "deviation", "upper_mm": 0.0, "lower_mm": 0.0,
         "text": "10"},
        {"value_mm": 25.0, "tol_type": "deviation", "upper_mm": 5.0, "lower_mm": -5.0,
         "text": "25"},
        {"value_mm": 25.0, "tol_type": "deviation", "upper_mm": 0.05, "lower_mm": -0.05,
         "text": "25"},
    ]}]
    f = R.check_dimension_tolerances({"sheets": sheets})
    assert codes(f) == {"TOL_MISSING", "TOL_INVERTED", "TOL_ZERO", "TOL_TOO_LOOSE"}
    missing = [x for x in f if x["code"] == "TOL_MISSING"][0]
    assert "0.2" in missing["detail"], "should quote the ISO 2768-m deviation for 30mm"
    assert missing["where"]["x_cm"] == 1


def test_text_tolerance_state():
    explicit = ["52-0.03^-0.05", "n10+0.1^  0", "3+0.1^  0", "14+0.2^  0", "3±0.007"]
    fit = ["Ø17js5", "n17js5", "5N9", "n14h6", "20H7", "30g6"]
    na = ["R0.3", "R0.5", "R2", "M10", "(R)", "(25)"]
    plain = ["12", "24", "13.5", "n20", "n26", "Ø14.9", "9", "3", "15"]
    for t in explicit:
        assert R.text_tolerance_state(t) == "explicit", t
    for t in fit:
        assert R.text_tolerance_state(t) == "fit", t
    for t in na:
        assert R.text_tolerance_state(t) == "not_applicable", t
    for t in plain:
        assert R.text_tolerance_state(t) == "plain", t
    assert R.text_tolerance_state("") == "plain"
    assert R.text_tolerance_state(None) == "plain"


def test_tolerance_check_respects_text():
    sheets = [{"name": "s1", "dims": [
        {"value_mm": 52.0, "tol_type": "none", "text": "52-0.03^-0.05"},
        {"value_mm": 17.0, "tol_type": "none", "text": "Ø17js5"},
        {"value_mm": 0.3, "tol_type": "none", "text": "R0.3"},
        {"value_mm": 24.0, "tol_type": "none", "text": "24"},
    ]}]
    f = R.check_dimension_tolerances({"sheets": sheets})
    assert len(f) == 1, [x["title"] for x in f]
    assert "24" in f[0]["title"]


def test_missing_dimensions():
    f = R.check_missing_dimensions({"sheets": [{"name": "s1", "undimensioned": [
        {"id": 76, "diameter_mm": 15.0, "x_cm": 25.3, "y_cm": 20.0}]}]})
    assert codes(f) == {"DIM_MISSING"}
    assert f[0]["where"]["x_cm"] == 25.3, "UI needs coordinates to place the marker"
    g = R.check_missing_dimensions({"sheets": [{"name": "s1", "undimensioned": [
        {"id": 5, "diameter_mm": 6.0, "x_cm": 1, "y_cm": 2, "count": 4}]}]})
    assert len(g) == 1 and "4곳" in g[0]["title"]
    assert "4×Ø6.0" in g[0]["fix"]


def test_drawing_meta():
    f = R.check_drawing_meta({"kind": "drawing", "sheets": [
        {"name": "s1", "title_block": None, "border": None, "dims": [], "views": [
            {"name": "v1", "scale": 0.333, "scale_string": "1:3"}]}]})
    assert codes(f) == {"TITLEBLOCK_MISSING", "SCALE_NONSTANDARD", "NO_DIMENSIONS_AT_ALL"}
    bordered = R.check_drawing_meta({"kind": "drawing", "sheets": [
        {"name": "s1", "title_block": None, "border": "1111",
         "dims": [{"value_mm": 1, "tol_type": "none"}],
         "views": [{"name": "v1", "scale": 1.0}]}]})
    assert bordered == [], bordered
    assert R.check_drawing_meta({"kind": "drawing", "sheets": [
        {"name": "s1", "title_block": "ISO", "dims": [{"value_mm": 1, "tol_type": "none"}],
         "views": [{"name": "v1", "scale": 1.0, "scale_string": "1:1"}]}]}) == []


def test_interference():
    f = R.check_interference({"interferences": [
        {"a": "부품1:1", "b": "부품1:2", "volume_mm3": 65039.7}]})
    assert codes(f) == {"INTERFERENCE"}
    assert "65039.7" in f[0]["title"]


def test_run_sorts_and_survives_bad_rules():
    facts = {
        "kind": "part",
        "props": {"material": "일반", "part_number": "", "designer": "smile"},
        "sketches": [{"name": "s1", "status": "under", "entities": 87, "under_count": 28}],
        "holes": [{"name": "h1", "diameter_mm": 1.0, "depth_mm": None}],
        "walls": [], "sheets": [], "interferences": [], "sick_features": [],
    }
    findings, summary = R.run(facts)
    assert summary["total"] == len(findings) > 0
    sev = [f["severity"] for f in findings]
    assert sev == sorted(sev, key=lambda s: R._SEV_ORDER[s]), "errors must come first"
    assert summary["error"] >= 2
    boom = lambda _: (_ for _ in ()).throw(ValueError("boom"))
    boom.__name__ = "check_boom"
    orig = R.ALL_CHECKS
    try:
        R.ALL_CHECKS = orig + (boom,)
        findings, _ = R.run(facts)
        assert "RULE_ERROR" in codes(findings)
    finally:
        R.ALL_CHECKS = orig


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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} checks passed")
