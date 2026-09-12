import json
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


class _BB:
    """Minimal stand-in for ezdxf's BoundingBox."""

    def __init__(self, x0, y0, x1, y1):
        self.has_data = True
        self.extmin = type("P", (), {"x": x0, "y": y0})()
        self.extmax = type("P", (), {"x": x1, "y": y1})()


def test_badges_sit_next_to_their_target():
    import math

    import dwg

    span = 1000.0
    badge_r = span * dwg.BADGE_R
    targets = [(100, 100), (500, 400), (900, 150)]
    rings = [span * 0.01] * 3
    spots = dwg._badge_positions(_BB(0, 0, 1000, 1000), span, targets, rings)

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
    spots = dwg._badge_positions(_BB(0, 0, 1000, 1000), span, targets, rings)

    clear = span * dwg.BADGE_R * 2.15
    for i, (ax, ay) in enumerate(spots):
        for bx, by in spots[i + 1:]:
            assert math.hypot(ax - bx, ay - by) >= clear - 1e-9, "badges overlap"


def test_badges_stay_inside_even_when_targets_hug_the_border():
    """A badge that hangs off the edge enlarges the preview canvas, which is the
    empty margin this placement exists to avoid."""
    import dwg

    span = 400.0
    badge_r = span * dwg.BADGE_R
    bb = _BB(0, 0, 400, 300)
    corners = [(0, 0), (400, 0), (0, 300), (400, 300), (200, 300), (400, 150)]
    for targets in (corners, [(400, 300)] * 8):
        spots = dwg._badge_positions(bb, span, targets, [span * 0.01] * len(targets))
        for bx, by in spots:
            assert badge_r <= bx <= 400 - badge_r, f"badge escaped sideways at {bx:.1f}"
            assert badge_r <= by <= 300 - badge_r, f"badge escaped vertically at {by:.1f}"


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
    (bx, by), = dwg._badge_positions(before, span, [(200, 150)], [ring])
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
    assert max(label.dxf.height for label in labels) == span * dwg.BADGE_R * 1.35, \
        "the number is sized from the badge, not the sheet"
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


def test_cloudconvert_posts_to_the_real_v2_endpoint():
    """The job URL is built from a module constant. This path only runs where an
    API key is set, so a missing or misspelled constant stays invisible in
    development and dies on the one server that depends on it."""
    import sys
    import types

    import dwg

    sent = []

    class _Resp:
        ok = True
        status_code = 200

        def json(self):
            # No upload form -- the call bails out right after creating the job,
            # which is all this test needs to see.
            return {"data": {"id": "job1",
                             "tasks": [{"name": "up", "result": {"form": None}}]}}

    fake = types.ModuleType("requests")
    fake.RequestException = Exception
    fake.get = lambda url, **kw: _Resp()

    def post(url, **kw):
        sent.append(url)
        return _Resp()

    fake.post = post

    had_module = "requests" in sys.modules
    old_module = sys.modules.get("requests")
    old_key = os.environ.get("CLOUDCONVERT_API_KEY")
    sys.modules["requests"] = fake
    os.environ["CLOUDCONVERT_API_KEY"] = "test-key"
    try:
        try:
            dwg.dwg_via_cloudconvert("no-such-file.dwg", "out.dxf")
        except RuntimeError:
            pass
    finally:
        if had_module:
            sys.modules["requests"] = old_module
        else:
            del sys.modules["requests"]
        if old_key is None:
            os.environ.pop("CLOUDCONVERT_API_KEY", None)
        else:
            os.environ["CLOUDCONVERT_API_KEY"] = old_key

    assert sent == ["https://api.cloudconvert.com/v2/jobs"], sent


def test_variance_spread():
    import variance

    assert variance.spread([]) is None
    one = variance.spread([27])
    assert one["spread"] == 0 and one["stdev"] == 0.0
    s = variance.spread([30, 22, 26, 26])
    assert s["n"] == 4
    assert s["min"] == 22 and s["max"] == 30
    assert s["spread"] == 8
    assert s["median"] == 26
    assert 3.2 < s["stdev"] < 3.3, s["stdev"]


def test_drop_clause_numbers():
    import ai_review

    drop = ai_review._drop_clause_numbers
    assert drop("KS B 0001 제3장에 따라 감점입니다") == "KS B 0001에 따라 감점입니다"
    assert drop("KS B ISO 128 Section 4 requires it") == "KS B ISO 128 requires it"
    assert drop("KS B 0001 第3章による") == "KS B 0001による"
    # 규격 이름만 있으면 그대로 둔다
    assert drop("KS B 0001 에 따라") == "KS B 0001 에 따라"
    # 조문 번호가 아닌 숫자는 건드리지 않는다
    assert drop("Ø17js5 를 3곳에서 확인") == "Ø17js5 를 3곳에서 확인"


def test_ai_title_is_fixed_by_kind():
    """같은 kind 면 AI 가 뭐라고 썼든 제목이 같아야 한다 (P03)."""
    import ai_review

    def titles(text):
        data = {"verdict": "총평", "i18n": {"en": {"deductions": [{"detail": "d",
                                                                  "fix": "f"}]}},
                "deductions": [{"severity": "error", "kind": "VIEW_MISSING",
                                "detail": text, "fix": text, "deduct": 10}]}
        out = ai_review._to_findings(data, "test-model")
        return out["findings"][0]["title"], out["findings"][0]["i18n"]["en"]["title"]

    first = titles("투상도 전체 누락 및 형상 표현 불가")
    second = titles("기계 부품 투상도 미작성 및 투상 뷰 부재")
    assert first == second == ("투상도 누락", "Missing views")

    # kind 는 여섯 개 중 하나만 나올 수 있다
    kinds = ai_review.SCHEMA["properties"]["deductions"]["items"]["properties"]["kind"]
    assert kinds["enum"] == list(ai_review.PROJECTION_KINDS)
    assert "title" not in ai_review.SCHEMA["properties"]["deductions"]["items"]["properties"]

    # 옛 캐시에는 kind 가 없다. 그때 화면에 뜬 제목을 그대로 둔다
    old = {"deductions": [{"severity": "warn", "title": "투상도 완전 누락",
                           "detail": "d", "fix": "f", "deduct": 5}]}
    assert ai_review._to_findings(old, "m")["findings"][0]["title"] == "투상도 완전 누락"


def test_malformed_dxf_recovers():
    """다른 CAD 가 쓴 DXF 는 살짝 깨져 있는 일이 잦다.

    ezdxf.readfile 은 거기서 ValueError 를 던지지만 AutoCAD 는 연다.
    우리 합성 도면은 늘 깨끗해서 실제 파일을 넣어 보기 전까지 안 드러났다 (P11)."""
    import ezdxf
    import dwg

    fd, path = tempfile.mkstemp(suffix=".dxf")
    os.close(fd)
    try:
        doc = ezdxf.new("R2013", setup=True)
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True)
        msp.add_circle((120, 120), 10.0)
        doc.saveas(path)

        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        # 실수 값 하나를 QCAD 가 뱉었던 것과 같은 모양으로 망가뜨린다
        broken = text.replace("\n120.0\n", "\n120.0l\n", 1)
        assert broken != text, "망가뜨릴 실수 값을 못 찾았다"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(broken)

        try:
            ezdxf.readfile(path)
        except Exception:
            pass
        else:
            raise AssertionError("ezdxf.readfile 이 그냥 열렸다 — 시험이 무의미하다")

        doc2 = dwg.readfile(path)          # 복구해서 열려야 한다
        assert doc2.modelspace() is not None
        assert dwg.dxf_has_content(path)   # 빈 도면으로 오해하지 않아야 한다
    finally:
        os.unlink(path)


def test_stats_counts_by_ip():
    """접속은 IP 하나에 하나로 세고, 검사는 올린 횟수만큼 센다.
    IP 원본이 남으면 안 되고, 주가 다르면 같은 IP 라도 이어 보이면 안 된다."""
    import datetime
    import importlib
    import stats as _stats

    class Req:
        def __init__(self, ip):
            self.headers = {"cf-connecting-ip": ip}
            self.client = None

    with tempfile.TemporaryDirectory() as tmp:
        # conftest 가 깔아 둔 임시 DB 를 지우지 말고 되돌려 놓는다. 지우면 뒤에
        # 오는 시험이 진짜 통계 DB 를 쓰게 돼서 방문자 수가 쌓인다.
        kept = {k: os.environ.get(k)
                for k in ("CADLENS_STAT_DB", "CADLENS_STAT_SALT")}
        os.environ["CADLENS_STAT_DB"] = os.path.join(tmp, "stats.db")
        os.environ["CADLENS_STAT_SALT"] = "test-salt"
        stats = importlib.reload(_stats)
        try:
            day = datetime.date(2026, 8, 30)          # 일요일 = 그 주의 마지막 날
            for kind in ("visit", "check", "check"):  # 한 사람이 두 번 검사
                stats.bump(Req("203.0.113.9"), kind, day)
            stats.bump(Req("203.0.113.10"), "visit", day)
            stats.bump(Req("203.0.113.10"), "sample", day)

            s = stats.summary(day)
            assert s["today"]["visitors"] == 2, s          # IP 둘
            assert s["today"]["checks"] == 3, s            # 검사 2 + 예제 1
            assert s["week"]["recheckers"] == 1, s         # 두 번 이상은 한 명
            assert s["total"]["checks"] == 2, s
            assert s["total"]["samples"] == 1, s
            assert s["daily"][-1] == {"day": "2026-08-30", "visitors": 2,
                                      "checks": 3}, s["daily"]

            with open(os.environ["CADLENS_STAT_DB"], "rb") as fh:
                raw = fh.read()
            assert b"203.0.113.9" not in raw, "IP 원본이 그대로 남았다"

            # 주가 바뀌면 같은 IP 도 다른 사람이 된다
            assert stats.visitor_id("203.0.113.9", day) !=                    stats.visitor_id("203.0.113.9", day + datetime.timedelta(days=1))
        finally:
            for k, v in kept.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            importlib.reload(_stats)


def test_synthetic_sheet_is_clean_and_defects_are_caught():
    """합성 기준 도면은 지적 0건이어야 하고, 결함을 하나 넣으면 그것만 잡혀야 한다.

    여기서 잡는 것 셋은 실제로 오탐·미탐이었다 —
    제3각법 기호의 원을 미치수 구멍으로, 뷰 이름표를 주서로,
    뷰 사각형을 도면 윤곽선으로 봤다."""
    import check
    import make_drawings

    with tempfile.TemporaryDirectory() as tmp:
        clean = make_drawings.build(0, out_dir=tmp)
        _, findings, _ = check.analyze(clean, use_ai=False)
        assert [f["code"] for f in findings] == [], [f["code"] for f in findings]

        for defect in ("no_notes", "no_title", "no_center", "undimensioned"):
            path = make_drawings.build(0, defect=defect, out_dir=tmp)
            _, findings, _ = check.analyze(path, use_ai=False)
            got = {f["code"] for f in findings}
            assert make_drawings.DEFECTS[defect] <= got, (defect, sorted(got))


def test_view_coordinates_reach_the_ai_context():
    """뷰 좌표를 뽑아서 AI 참고 정보까지 실어 보낸다.

    제3각법 배치와 공간 활용은 좌표 비교로 답이 나오는데, 예전에는 뷰 이름만
    넘기고 좌표를 버려서 AI 가 150 DPI 그림을 보고 위치를 짐작해야 했다."""
    import ezdxf
    import ai_review
    import dwg

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    # 제3각법: 평면도가 정면도 위(y 가 큼), 우측면도가 정면도 오른쪽(x 가 큼).
    for name, (x, y) in (("부품_시트_뷰1", (100, 100)),
                         ("부품_시트_뷰2", (100, 200)),
                         ("부품_시트_뷰3", (200, 100))):
        block = doc.blocks.new(name)
        block.add_circle((0, 0), 20)
        msp.add_blockref(name, (x, y))

    path = os.path.join(tempfile.mkdtemp(), "views.dxf")
    doc.saveas(path)
    views = (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]["views"]

    assert len(views) == 3, views
    spot = {v["name"]: (v["x_mm"], v["y_mm"]) for v in views}
    assert spot["부품_시트_뷰1"] == (100.0, 100.0), spot
    assert spot["부품_시트_뷰2"][1] > spot["부품_시트_뷰1"][1], "평면도가 위"
    assert spot["부품_시트_뷰3"][0] > spot["부품_시트_뷰1"][0], "우측면도가 오른쪽"
    # 블록 안까지 펼쳐 재야 크기가 나온다. 삽입점만 읽으면 40mm 가 안 나온다.
    assert all(v["w_mm"] == 40.0 and v["h_mm"] == 40.0 for v in views), views

    context = ai_review._context(dwg.facts_from_dxf(path))
    assert "뷰 위치·크기" in context, context
    assert "(100.0, 200.0)" in context, context


def test_views_are_clustered_when_the_cad_file_has_no_view_blocks():
    """뷰 블록이 없는 도면에서도 형상 뭉치로 뷰 경계를 찾는다.

    실제 도면 6장 중 뷰 블록을 가진 것은 1장뿐이었다. 나머지는 모델 공간에
    형상이 평평하게 깔려 있어 투상도 검사가 통째로 꺼져 있었다."""
    import ezdxf
    import dwg

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    # 도면 윤곽선. 시트를 가로지르므로 뷰 세 개를 한 덩어리로 이어선 안 된다.
    msp.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True)
    for cx, cy in ((100, 100), (100, 200), (250, 100)):
        for dx, dy in ((-15, -15), (15, -15), (-15, 15), (15, 15), (0, 0)):
            msp.add_circle((cx + dx, cy + dy), 5)

    path = os.path.join(tempfile.mkdtemp(), "noblocks.dxf")
    doc.saveas(path)
    views = (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]["views"]

    assert len(views) == 3, [(v["x_mm"], v["y_mm"], v["w_mm"]) for v in views]
    assert all(v["detected"] == "cluster" for v in views), views
    spot = sorted((v["x_mm"], v["y_mm"]) for v in views)
    assert spot == [(100.0, 100.0), (100.0, 200.0), (250.0, 100.0)], spot
    assert all(v["w_mm"] == 40.0 and v["h_mm"] == 40.0 for v in views), views

    import ai_review
    context = ai_review._context(dwg.facts_from_dxf(path))
    assert "형상 뭉치로 추정" in context, context


def test_front_view_is_the_one_the_dimensions_cluster_on():
    """치수가 몰린 뷰를 정면도로 고른다.

    형상 개수로 고르면 안 된다. 실제 도면에서 형상이 가장 많은 덩어리는
    등각투상도였고 치수는 0개였다. 여기서도 형상이 가장 많은 뷰와 치수가
    몰린 뷰를 일부러 다르게 뒀다."""
    import ezdxf
    import ai_review
    import dwg

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True)
    corners = ((-15, -15), (15, -15), (-15, 15), (15, 15), (0, 0))
    for cx, cy in ((100, 100), (100, 200), (250, 100)):
        # 오른쪽 뷰에 형상을 몰아 준다. 치수는 왼쪽 아래 뷰에 붙일 것이다.
        spots = corners + ((-8, 0), (8, 0), (0, -8), (0, 8), (-8, 8), (8, -8))             if (cx, cy) == (250, 100) else corners
        for dx, dy in spots:
            msp.add_circle((cx + dx, cy + dy), 5)
    for i in range(6):
        msp.add_linear_dim(base=(100, 60 - i * 6), p1=(85, 70), p2=(115, 70)).render()

    path = os.path.join(tempfile.mkdtemp(), "front.dxf")
    doc.saveas(path)
    views = (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]["views"]

    front = [v for v in views if v.get("is_front")]
    assert len(front) == 1, [(v["x_mm"], v["y_mm"], v.get("dim_count")) for v in views]
    assert (front[0]["x_mm"], front[0]["y_mm"]) == (100.0, 100.0), front
    busiest = max(views, key=lambda v: v.get("shapes") or 0)
    assert not busiest.get("is_front"), "형상이 가장 많은 뷰가 정면도는 아니다"

    # 뷰 셋이 정면도 · 그 위 · 그 오른쪽에 놓였으니 제3각법 배치다. 좌표로
    # 가려 낸 것이라 AI 에게 짐작시키지 않고 이름과 판정을 같이 넘긴다.
    assert front[0].get("role") == "정면도", front
    assert {v.get("role") for v in views} == {"정면도", "평면도", "우측면도"}, views

    context = ai_review._context(dwg.facts_from_dxf(path))
    assert "← 정면도" in context, context
    assert "제3각법 배치 확인됨" in context, context


def test_third_angle_layout_is_read_from_coordinates():
    """제3각법 배치를 좌표로 가린다. 뒤집어 그리면 제1각법으로 본다.

    투상도 30점의 한 축인데 지금까지 AI 에게 통째로 맡겨 왔다. 정면도를 못
    고르면 AI 에게 '판단하지 마세요' 라고 보내서, 실제 도면 30장 중 22장에서
    이 배점이 비어 있었다."""
    import ezdxf

    import dwg

    def sheet(spots, name):
        doc = ezdxf.new("R2013", setup=True)
        doc.header["$INSUNITS"] = 4
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True)
        for cx, cy in spots:
            for dx, dy in ((-15, -15), (15, -15), (-15, 15), (15, 15), (0, 0)):
                msp.add_circle((cx + dx, cy + dy), 5)
        # 치수는 정면도(첫 자리)에 몰아 준다 — KS 가 그렇게 기입하라고 한다.
        for i in range(6):
            msp.add_linear_dim(base=(spots[0][0], spots[0][1] - 40 - i * 6),
                               p1=(spots[0][0] - 15, spots[0][1] - 30),
                               p2=(spots[0][0] + 15, spots[0][1] - 30)).render()
        path = os.path.join(tempfile.mkdtemp(), name + ".dxf")
        doc.saveas(path)
        return (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]

    # 정면도 (150,120) · 평면도 위 · 우측면도 오른쪽
    third = sheet([(150, 120), (150, 230), (280, 120)], "third")
    assert third["layout"]["verdict"] == "third", third["layout"]

    # 같은 도면을 뒤집어 그린 것 — 평면도 아래, 우측면도 왼쪽
    first = sheet([(280, 230), (280, 120), (150, 230)], "first")
    assert first["layout"]["verdict"] == "first", first["layout"]

    # 제3각법 도면에는 이 지적이 붙지 않고, 뒤집힌 도면에만 붙는다.
    import exam
    codes = lambda s: {f["code"] for f in exam.grade({"sheets": [s]})[0]}
    assert "EX_LAYOUT_FIRST_ANGLE" not in codes(third)
    assert "EX_LAYOUT_FIRST_ANGLE" in codes(first)


def test_front_view_is_left_unset_when_the_drawing_has_no_dimensions():
    """치수가 없으면 정면도를 고르지 않는다.

    DWG 를 변환한 도면은 치수가 선과 문자로 흩어져 DIMENSION 이 하나도 안
    남는다. 그때 아무 뷰나 정면도로 찍으면 제3각법 판정이 통째로 뒤집힌다."""
    import ezdxf
    import ai_review
    import dwg

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (420, 0), (420, 297), (0, 297)], close=True)
    for cx, cy in ((100, 100), (100, 200)):
        for dx, dy in ((-15, -15), (15, -15), (-15, 15), (15, 15), (0, 0)):
            msp.add_circle((cx + dx, cy + dy), 5)

    path = os.path.join(tempfile.mkdtemp(), "nodims.dxf")
    doc.saveas(path)
    views = (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]["views"]

    assert len(views) == 2, views
    assert not any(v.get("is_front") for v in views), views
    context = ai_review._context(dwg.facts_from_dxf(path))
    assert "정면도를 특정하지 못했습니다" in context, context


def test_projection_is_not_claimed_when_the_file_does_not_say():
    """투상법을 모르면 모른다고 적는다.

    DXF 헤더에 투상법이 없어서 first_angle 은 늘 None 인데, None 이 거짓으로
    취급돼 모든 도면에 '제3각법' 이라고 AI 에게 단언하고 있었다. 제1각법으로
    그려서 오작인 도면까지 제3각법이라고 알려준 셈이다."""
    import ai_review

    unknown = ai_review._projection_line(None)
    assert "알 수 없음" in unknown, unknown
    assert "제3각법" not in unknown.split("—")[0], unknown
    assert ai_review._projection_line(True) == "투상법(파일 속성): 제1각법"
    assert ai_review._projection_line(False) == "투상법(파일 속성): 제3각법"


def test_gdt_font_letters_are_read_as_geometric_tolerance():
    """GDT 글꼴로 찍은 기하공차를 읽는다.

    실기 도면은 기하공차를 유니코드(⏥ ⌭)가 아니라 GDT 전용 글꼴(AIGDT___.TTF)로
    알파벳 한 글자를 찍어 만든다. 글자만 보면 그냥 'b' 라서, 실제 도면을 넣으면
    기하공차가 하나도 없다고 보고 도면마다 오작(DQ_NO_GEOMETRIC_TOL)이 떴다.
    같은 글꼴로 찍히는 지름 기호(⌀)만 있고 공차값도 데이텀도 없으면 공차칸이 아니다."""
    import ezdxf

    import dwg

    doc = ezdxf.new(setup=True)
    doc.styles.add("GDT", font="AIGDT___.TTF")
    msp = doc.modelspace()
    msp.add_text("b", height=3, dxfattribs={"style": "GDT"}).set_placement((10, 50))
    msp.add_text("0.013", height=3).set_placement((16, 50))
    msp.add_text("A", height=3).set_placement((26, 50))
    msp.add_text("o", height=3, dxfattribs={"style": "GDT"}).set_placement((10, 20))

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "gdt.dxf")
        doc.saveas(path)
        sheet = dwg.facts_from_dxf(path)["sheets"][0]

    tols = sheet["geometric_tols"]
    assert len(tols) == 1, tols          # 지름 기호 하나는 공차칸이 아니다
    assert tols[0]["tolerance"] == "0.013", tols
    assert tols[0]["datums"] == ["A"], tols


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} checks passed")


def _sheet_facts(fields=None, **sheet):
    base = {"name": "Model", "title_block": "TITLE", "border": "윤곽선",
            "fields": dict(fields or {}), "sheet_name": "A2",
            "views": [], "dims": [], "undimensioned": [],
            "surface_symbols": [], "geometric_tols": [],
            "counts": {"SurfaceTextureSymbols": 3, "FeatureControlFrames": 1,
                       "Centerlines": 2, "Centermarks": 0}}
    base.update(sheet)
    return {"kind": "dwg", "file": "t.dxf", "props": {}, "sheets": [base],
            "first_angle": False, "notes_text": [], "title_attributes": {}}


def test_title_block_fields_are_read_label_by_value():
    import dwg

    # 실기 도면은 라벨과 값이 다른 칸에 따로 놓인다 (Inventor 도면틀).
    plain = [(370, 21, "척도"), (395, 21, "1:1"), (370, 14, "각법"),
             (395, 14, "3각법"), (350, 56, "재질"), (350, 50, "SCM415")]
    got = dwg._title_fields(plain, 1.0)
    assert got["scale"] == "1:1"
    assert got["projection"] == "3각법"
    assert got["material"] == "SCM415"

    # 한 문자에 붙어 있는 도면도 있다 (합성 도면·AutoCAD 양식).
    inline = dwg._title_fields([(300, 24, "척도 1:1"), (250, 24, "제3각법")], 1.0)
    assert inline["scale"] == "1:1"

    # 값처럼 안 생긴 것은 버린다. 옆 칸 글자를 값으로 읽느니 모르는 게 낫다.
    assert "scale" not in dwg._title_fields([(370, 21, "척도"), (395, 21, "본체")], 1.0)


def test_first_angle_from_drawing_text():
    import dwg

    assert dwg._first_angle(["제3각법"], {}) is False
    assert dwg._first_angle(["제1각법"], {}) is True
    assert dwg._first_angle(["3각법"], {}) is False
    assert dwg._first_angle([], {"projection": "3"}) is False
    assert dwg._first_angle([], {"projection": "1"}) is True
    assert dwg._first_angle(["본체", "1:1"], {}) is None

    # 표제란은 칸마다 문자가 따로다. 이어 붙이면 `1:1` 과 `각법` 이 붙어 `1 각법`
    # 이 되고, 제3각법 도면이 제1각법 오작으로 찍힌다. 실제로 그렇게 났었다.
    title = ["척도", "1:1", "각법", "제3각법", "재질", "SM45C"]
    assert dwg._first_angle(title, {"scale": "1:1", "projection": "제3각법"}) is False
    assert dwg._first_angle(["척도 1:1", "각법"], {}) is None
    assert dwg._first_angle(["척도 1:1 각법 제3각법"], {}) is False


def test_sheet_size_matches_standard_paper():
    import ezdxf
    import dwg

    def size_of(w, h):
        doc = ezdxf.new("R2013")
        doc.header["$INSUNITS"] = 4
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True)
        rects = [e for e in msp if dwg._is_border(e)]
        return dwg._sheet_size(doc, rects, 1.0)[0]

    assert size_of(594, 420) == "A2"
    assert size_of(420, 297) == "A3"
    assert size_of(297, 420) == "A3", "세로 도면도 같은 크기다"
    assert size_of(500, 300) is None, "표준에 없는 크기는 이름을 붙이지 않는다"


FORM_CODES = {"EX_NO_SHEET_SCALE", "EX_NO_MATERIAL", "EX_SCALE_NOT_ONE",
              "EX_NO_PROJECTION_MARK", "EX_NO_MASS", "EX_SHEET_SIZE",
              "EX_VIEW_SCALE_MIXED", "DQ_SHEET_SIZE", "DQ_PROJECTION"}


def form_codes(facts):
    return codes(exam.grade(facts)[0]) & FORM_CODES


def test_sheet_form_checks_fire_only_on_what_is_missing():
    facts = _sheet_facts({"scale": "1:1", "material": "SM45C"})
    assert form_codes(facts) == set(), "다 갖춘 표제란은 조용해야 한다"

    assert form_codes(_sheet_facts({"material": "SM45C"})) == {"EX_NO_SHEET_SCALE"}
    assert form_codes(_sheet_facts({"scale": "1:1"})) == {"EX_NO_MATERIAL"}
    assert form_codes(_sheet_facts({"scale": "2:1", "material": "SM45C"})) ==         {"EX_SCALE_NOT_ONE"}

    no_mark = _sheet_facts({"scale": "1:1", "material": "SM45C"})
    no_mark["first_angle"] = None
    assert form_codes(no_mark) == {"EX_NO_PROJECTION_MARK"}

    first = _sheet_facts({"scale": "1:1", "material": "SM45C"})
    first["first_angle"] = True
    assert "DQ_PROJECTION" in form_codes(first), "제1각법은 오작이다"

    # 표제란이 통째로 없으면 EX_NO_TITLEBLOCK 만 말한다. 같은 말을 여러 번 하지 않는다.
    bare = _sheet_facts({}, title_block=None, border=None, sheet_name=None)
    assert form_codes(bare) == set(), "표제란이 없으면 표제란 항목을 따로 세지 않는다"


def test_isometric_sheet_needs_mass_and_allows_ns_scale():
    iso = _sheet_facts({"scale": "NS", "material": "SM45C"}, is_isometric=True)
    assert form_codes(iso) == {"EX_NO_MASS"}, "3D는 NS 척도가 맞고 질량만 빠졌다"

    with_mass = _sheet_facts({"scale": "NS", "material": "SM45C", "mass": "128.4"},
                             is_isometric=True)
    assert form_codes(with_mass) == set()


def test_sheet_size_verdicts():
    full = {"scale": "1:1", "material": "SM45C"}
    assert form_codes(_sheet_facts(full, sheet_name="A3")) == {"EX_SHEET_SIZE"},         "A3는 출력 크기라 경고까지만 한다"
    assert "DQ_SHEET_SIZE" in form_codes(_sheet_facts(full, sheet_name="A4")),         "A4로 제도한 것은 오작이다"
    assert form_codes(_sheet_facts(full, sheet_name=None)) == set(),         "크기를 모르면 아무 말도 하지 않는다"


def test_inventor_files_get_export_instructions():
    import check

    for ext in (".idw", ".ipt", ".iam"):
        try:
            check.analyze("도면" + ext)
        except ValueError as e:
            assert "DWG/DXF" in str(e) and ext in str(e)
            if ext != ".idw":
                assert "도면(.idw)" in str(e), "3D 파일은 먼저 도면을 만들어야 한다"
        else:
            raise AssertionError(f"{ext} 는 막혀야 한다")


def test_view_scale_mixed_ignores_detail_views():
    import dwg

    got = dwg._view_scales(["단면도 A-A (1:1)", "C ( 5 : 1 )", "커버 (2:1)",
                            "주서 1. 일반공차 KS B ISO 2768-m (1:1)"])
    assert {v["scale"] for v in got} == {"1:1", "5:1", "2:1"}

    mixed = _sheet_facts({"scale": "1:1", "material": "SM45C"},
                         view_scales=[{"label": "커버 (2:1)", "scale": "2:1"}])
    assert "EX_VIEW_SCALE_MIXED" in form_codes(mixed), \
        "전체 1:1인데 뷰 하나만 2:1인 것은 인터뷰에서 나온 실제 실수다"

    detail = _sheet_facts({"scale": "1:1", "material": "SM45C"},
                          view_scales=[{"label": "C ( 5 : 1 )", "scale": "5:1"},
                                       {"label": "상세도 B (2:1)", "scale": "2:1"}])
    assert form_codes(detail) == set(), "상세도·확대도는 척도가 달라도 맞다"


def test_ai_moves_to_the_next_grader_when_the_first_one_fails(monkeypatch):
    """Gemini 가 503 을 주면 투상도 30점이 통째로 비었다. 키가 있는 다음
    채점기로 넘어가야 한다 — 폴백을 넷이나 붙인 이유가 이것이다."""
    import ai_review

    called = []

    def boom(*a, **k):
        called.append("gemini")
        raise RuntimeError("503 UNAVAILABLE")

    def ok(*a, **k):
        called.append("mistral")
        return json.dumps({"deductions": [{"title": "투상도 누락", "detail": "d",
                                           "fix": "f", "deduct": 8,
                                           "severity": "error"}]})

    monkeypatch.setattr(ai_review, "providers", lambda: ["gemini", "mistral"])
    monkeypatch.setattr(ai_review, "render_png", lambda path: b"png")
    monkeypatch.setattr(ai_review, "_cache_get", lambda path: None)
    monkeypatch.setattr(ai_review, "_cache_put", lambda path, data: None)
    monkeypatch.setattr(ai_review, "_enrich", lambda data, ask, timeout: None)
    monkeypatch.setattr(ai_review, "_ask_gemini", boom)
    monkeypatch.setattr(ai_review, "_ask_mistral", ok)

    out = ai_review.judge({"dxf": __file__}, timeout=1)
    assert called == ["gemini", "mistral"], called
    assert out and out["findings"][0]["code"] == "AI_PROJECTION"
    assert out["findings"][0]["deduct"] == 8
    assert ai_review.MISTRAL_MODEL in json.dumps(out, ensure_ascii=False)


def test_ai_gives_up_only_after_every_grader_failed(monkeypatch):
    import ai_review

    tried = []

    def boom(name):
        def f(*a, **k):
            tried.append(name)
            raise RuntimeError("429")
        return f

    monkeypatch.setattr(ai_review, "providers",
                        lambda: ["gemini", "cloudflare", "mistral", "groq"])
    monkeypatch.setattr(ai_review, "render_png", lambda path: b"png")
    monkeypatch.setattr(ai_review, "_cache_get", lambda path: None)
    for name in ("gemini", "cloudflare", "mistral", "groq"):
        monkeypatch.setattr(ai_review, f"_ask_{name}", boom(name))

    assert ai_review.judge({"dxf": __file__}, timeout=1) is None
    assert tried == ["gemini", "cloudflare", "mistral", "groq"], tried


def test_material_field_does_not_borrow_the_cell_below():
    import dwg

    # 재질 칸이 비면 아래 칸 글자를 물어 온다. `1:1`을 재료로 읽으면 재료 누락을
    # 영영 못 잡는다.
    empty = dwg._title_fields([(300, 30, "재질"), (300, 20, "척도"),
                               (320, 20, "1:1")], 1.0)
    assert "material" not in empty

    for code in ("GC250", "SM45C", "SCM415", "SUS304", "주철"):
        got = dwg._title_fields([(300, 30, "재질"), (320, 30, code)], 1.0)
        assert got.get("material") == code, code


def test_web_screen_knows_every_check_and_rubric_item():
    """화면의 검사 이름·묶음·배점표가 exam.py 와 어긋나지 않는다.

    검사를 새로 만들 때 `static/index.html` 을 같이 안 고치면 화면에 코드가
    그대로 뜨거나(`EX_OUTSIDE_FRAME`) 어느 항목에도 안 묶여 사라진다.
    배점표도 손으로 적어 둔 것이라 항목이 늘면 만점이 안 맞는다."""
    import re

    import exam

    def block(text, start):
        depth, i = 0, start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
            i += 1
        raise AssertionError("괄호가 안 닫혔다")

    here = os.path.dirname(os.path.abspath(__file__))
    page = open(os.path.join(here, "static", "index.html"), encoding="utf-8").read()

    checks = {c for c, *_ in exam.CHECKS}
    rubric = [c for c, _, _, _ in exam.RUBRIC]

    codes = re.search(r"const RUBRIC_CODES=\[(.*?)\]", page).group(1)
    assert re.findall(r"'([A-Z_]+)'", codes) == rubric, codes
    maxes = re.search(r"const RUBRIC_MAX=\[(.*?)\]", page).group(1)
    assert [int(v) for v in maxes.split(",")] == [p for _, _, p, _ in exam.RUBRIC]

    groups = block(page, page.index("const GROUP_BY_CHECK=")
                   + len("const GROUP_BY_CHECK="))
    mapped = dict(re.findall(r"([A-Z_]+):'([A-Za-z_]+)'", groups))
    assert not checks - set(mapped), sorted(checks - set(mapped))
    assert not set(mapped) - checks, sorted(set(mapped) - checks)
    assert not set(mapped.values()) - set(rubric) - {"dq"}, sorted(set(mapped.values()))

    labels = block(page, page.index("const CHECK_LABELS=") + len("const CHECK_LABELS="))
    for lang in ("en", "ja", "zh"):
        named = set(re.findall(
            r"([A-Z_]+):", block(labels, labels.index(lang + ":{") + len(lang) + 1)))
        assert not (checks | set(rubric)) - named, (lang, sorted(
            (checks | set(rubric)) - named))

    for key in ("rub:[",):
        for row in re.findall(r"rub:\[(.*?)\]", page):
            assert len(row.split("','")) == len(rubric), (key, row)


def test_every_check_has_a_written_basis():
    """검사마다 어느 규격·채점 기준에서 나왔는지 문서에 적혀 있다.

    근거 없이 지적하면 수험생이 그 지적을 믿을 수가 없다. 검사를 새로 만들고
    `docs/rule_standards.md` 에 한 줄 안 적으면 이 시험이 잡는다."""
    import re

    import exam

    here = os.path.dirname(os.path.abspath(__file__))
    page = open(os.path.join(here, "docs", "rule_standards.md"),
                encoding="utf-8").read()
    written = set(re.findall(r"\| `([A-Z_]+)`", page))
    ids = {c for c, *_ in exam.CHECKS}
    assert not ids - written, sorted(ids - written)
    assert not written - ids, sorted(written - ids)


def test_holes_that_need_no_dimension_are_not_flagged():
    """치수가 없어도 맞는 원이 있다. 제도 기본을 모르면 전부 오탐이 된다.

    실제 수험생 도면 30장 중 22장에서 헛지적이 났고 원인이 넷이었다 —
    나사 골지름 원, 필렛·라운드 원호, 상세도 경계 원, 절단선이 꺾인 원호."""
    import ezdxf

    import dwg
    import exam

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    for name in ("외형선", "상세 경계(ISO)", "절단선(ISO)", "스케치 형상(ISO)"):
        doc.layers.add(name)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (594, 0), (594, 420), (0, 420)], close=True)
    msp.add_lwpolyline([(40, 60), (200, 60), (200, 180), (40, 180)], close=True)

    # 나사 — 호칭만 적고 지름 치수는 안 적는 것이 맞다. 골지름 원 세 개.
    msp.add_text("3-M4", height=3.5).set_placement((60, 200))
    for i in range(3):
        msp.add_circle((60 + i * 20, 120), 3.24 / 2, dxfattribs={"layer": "외형선"})
    # 라운드 — R 로 적고 구멍이 아니다
    for i in range(4):
        msp.add_arc((60 + i * 20, 90), 6.0, 0, 90, dxfattribs={"layer": "외형선"})
    # 상세도 경계 원과 절단선이 꺾인 원호
    msp.add_circle((300, 300), 20.0, dxfattribs={"layer": "상세 경계(ISO)"})
    msp.add_arc((300, 200), 20.0, 0, 36, dxfattribs={"layer": "절단선(ISO)"})
    msp.add_circle((350, 120), 4.0, dxfattribs={"layer": "스케치 형상(ISO)"})
    # 치수가 하나도 없으면 "치수 없음" 으로 끝나 미치수 구멍까지 안 간다
    msp.add_linear_dim(base=(120, 40), p1=(40, 60), p2=(200, 60),
                       text="160").render()

    path = os.path.join(tempfile.mkdtemp(), "holes.dxf")
    doc.saveas(path)
    sheet = (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]
    assert sheet["undimensioned"] == [], [
        (round(u["diameter_mm"], 2), u["count"]) for u in sheet["undimensioned"]]

    # 치수도 나사 호칭도 없는 진짜 구멍은 그대로 잡는다
    msp.add_circle((120, 150), 9.0 / 2, dxfattribs={"layer": "외형선"})
    doc.saveas(path)
    sheet = (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]
    assert [round(u["diameter_mm"], 1) for u in sheet["undimensioned"]] == [9.0], \
        sheet["undimensioned"]
    assert "EX_DIM_MISSING" in {f["code"] for f in exam.grade({"sheets": [sheet]})[0]}


def test_a_view_without_dimensions_is_not_a_defect():
    """KS B 0001 — 하나의 치수는 도면 내 단 한 곳에만 기입한다.

    우측면도에 원의 치수가 없어도 정면도에 있으면 기입한 것이다. 뷰마다
    치수를 요구하면 중복 기입을 시키는 꼴이라 원칙에 어긋난다."""
    import ezdxf

    import dwg
    import exam

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (594, 0), (594, 420), (0, 420)], close=True)
    # 같은 Ø20 구멍을 정면도와 우측면도에 그리고, 치수는 정면도에만 적는다
    for cx in (120, 300):
        msp.add_lwpolyline([(cx - 40, 150), (cx + 40, 150), (cx + 40, 250),
                            (cx - 40, 250)], close=True)
        msp.add_circle((cx, 200), 10.0)
    msp.add_diameter_dim(center=(120, 200), radius=10.0, angle=45,
                         text="%%c20H7").render()

    path = os.path.join(tempfile.mkdtemp(), "oneview.dxf")
    doc.saveas(path)
    sheet = (dwg.facts_from_dxf(path)["sheets"] or [{}])[0]
    assert sheet["undimensioned"] == [], sheet["undimensioned"]
    got = {f["code"] for f in exam.grade({"sheets": [sheet]})[0]}
    assert "EX_DIM_MISSING" not in got, sorted(got)
    assert "EX_VIEW_NO_DIMS" not in got, "뷰마다 치수를 요구하면 안 된다"


def test_official_ks_examples_are_accepted():
    """공단이 낸 `국가기술자격 실기시험용 KS 기계제도 규격` 의 예시를 그대로
    통과시킨다. 이 예시대로 그린 도면에 헛지적이 나면 안 된다."""
    import re

    import dwg
    import exam

    # 50. 기계재료 기호 예시 (KS D) — 소문자가 섞인 것과 빈칸이 있는 것 포함
    for code in ("GC100", "GC250", "GCD 350-22", "SC360", "SC480", "SF390A",
                 "CAC502A", "CAC402", "SM9CK", "SM45C", "AC4C", "STC85",
                 "STS3", "WM3", "SCM415", "SNCM431", "SNC415",
                 "SCr415", "SCr435", "SPS6", "S55C-CSP", "PW-1",
                 "SS235", "ALDC5", "SCW410", "C5102B"):
        assert dwg._MATERIAL_VALUE_RE.match(code), code
    for not_a_code in ("베어링커버", "과제명", "동력전달장치-4", "품명"):
        assert not dwg._MATERIAL_VALUE_RE.match(not_a_code), not_a_code

    # 46. 주서(예) 의 표면거칠기 비교표는 등식으로 쓴다
    for line in ("√w = Ra 12.5", "√x = Ra 3.2", "√y = Ra 0.8", "√z = Ra 0.2",
                 "x = Ra 3.2"):
        assert dwg._ROUGH_PAIR_RE.search(line), line
    for line in ("7. 표면거칠기", "재질", "1. 일반공차"):
        assert not dwg._ROUGH_PAIR_RE.search(line), line

    # 46. 주서(예) 1번은 일반공차 선언이다 — 가공부와 주조부 둘 다 인정한다
    for line in ("1. 일반공차 : 가)가공부 : KS B ISO 2768 - m",
                 "나)주조부 : KS B 0250 - CT11"):
        assert re.search(exam.GENERAL_TOL_RE, line), line
    assert not re.search(exam.GENERAL_TOL_RE, "6. 전체 열처리 HRC 50±3")

    # 10. 미터 보통 나사 골 지름 — 이 원에는 치수를 안 적는 것이 맞다
    for nominal, minor in ((3, 2.459), (4, 3.242), (5, 4.134), (6, 4.917),
                           (8, 6.647), (10, 8.376), (12, 10.106), (16, 13.835)):
        assert dwg._is_thread_circle(minor, {float(nominal)}), (nominal, minor)
        assert dwg._is_thread_circle(float(nominal), {float(nominal)}), nominal
    # 나사와 상관없는 구멍은 그대로 잡는다
    assert not dwg._is_thread_circle(9.0, {4.0, 6.0})
    assert not dwg._is_thread_circle(20.0, {4.0})

    # 49. 요목표(예) 에 실린 종류를 전부 알아본다
    for part in ("스퍼기어", "스퍼어기어", "헬리컬기어", "베벨 기어", "웜휠",
                 "웜", "래크", "피니언", "스프로킷", "체인", "래칫 휠",
                 "압축 스프링"):
        assert dwg._SPEC_PART_RE.match(part), part

    # KS A ISO 5455 권장 척도를 오작으로 부르지 않는다
    for scale in ("1:1", "1:2", "1:5", "1:10", "1:20", "1:50", "1:100",
                  "2:1", "5:1", "10:1", "20:1", "50:1"):
        assert scale in exam.STANDARD_SCALES, scale
