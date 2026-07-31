import re

MIN_HOLE_DIA_MM = 3.0
MIN_WALL_MM = 2.0
MAX_WALL_GAP_MM = 15.0
GENERIC_MATERIALS = {"일반", "generic", "기본값", "default", ""}
REQUIRED_PROPS = {
    "part_number": "품번 (Part Number)",
    "material": "재질 (Material)",
    "designer": "설계자 (Designer)",
}
TOL_REQUIRED_ABOVE_MM = 0.0
ISO2768_M = [
    (3, 0.10), (6, 0.10), (30, 0.20), (120, 0.30),
    (400, 0.50), (1000, 0.80), (2000, 1.20), (4000, 2.00),
]

SEV_ERROR, SEV_WARN, SEV_INFO = "error", "warn", "info"

_ISO_FIT = re.compile(r"\d\s*[A-Za-z]{1,2}\d{1,2}(?![\d.])")
_EXPLICIT_TOL = re.compile(r"±|\^|[+\-]\s*\d*\.\d+|\bmin\b|\bmax\b", re.I)
_NO_TOL_NEEDED = re.compile(r"^\s*[(\[]|^\s*R[\d.]|^\s*M\s*\d|×|\bTYP\b|\bREF\b", re.I)


def text_tolerance_state(text):
    t = (text or "").strip()
    if not t:
        return "plain"
    if _NO_TOL_NEEDED.search(t):
        return "not_applicable"
    if _EXPLICIT_TOL.search(t):
        return "explicit"
    if _ISO_FIT.search(t):
        return "fit"
    return "plain"


def iso2768_m(value_mm):
    v = abs(value_mm)
    for upper, dev in ISO2768_M:
        if v <= upper:
            return dev
    return None


def _f(code, severity, title, detail, fix, where=None):
    return {"code": code, "severity": severity, "title": title,
            "detail": detail, "fix": fix, "where": where or {}}


def check_sketches(facts):
    out = []
    for sk in facts.get("sketches", []):
        if sk["status"] == "under":
            out.append(_f(
                "SKETCH_UNDER_CONSTRAINED", SEV_ERROR,
                f"미구속 스케치: {sk['name']}",
                f"엔티티 {sk['entities']}개 중 {sk['under_count']}개가 미구속 상태입니다. "
                f"치수나 구속조건이 부족해서 형상이 의도치 않게 움직일 수 있습니다.",
                "스케치를 편집하고 F8(모든 구속조건 표시)로 확인하세요. "
                "Inventor 하단 상태바에 필요한 구속조건 수가 표시됩니다. "
                "치수 구속(D) 또는 기하 구속을 추가해 '완전 구속'으로 만드세요.",
                {"sketch": sk["name"]}))
        elif sk["status"] == "over":
            out.append(_f(
                "SKETCH_OVER_CONSTRAINED", SEV_WARN,
                f"과구속 스케치: {sk['name']}",
                "구속조건이 중복되어 충돌합니다. 형상 수정 시 오류가 발생합니다.",
                "중복된 치수/구속조건을 삭제하세요. 보통 같은 거리를 두 번 정의한 경우입니다.",
                {"sketch": sk["name"]}))
    return out


def check_holes(facts):
    out = []
    for h in facts.get("holes", []):
        d = h["diameter_mm"]
        if d < MIN_HOLE_DIA_MM:
            out.append(_f(
                "HOLE_TOO_SMALL", SEV_WARN,
                f"작은 홀: {h['name']} (Ø{d:.2f} mm)",
                f"직경 {d:.2f} mm는 기준 {MIN_HOLE_DIA_MM} mm보다 작습니다. "
                "드릴 파손 위험이 있고 가공비가 올라갑니다.",
                f"Ø{MIN_HOLE_DIA_MM} mm 이상으로 키우거나, 꼭 필요하면 "
                "도면에 가공 방법(방전/레이저)을 명시하세요.",
                {"feature": h["name"]}))
        if h.get("depth_mm") and d and h["depth_mm"] / d > 10:
            out.append(_f(
                "HOLE_TOO_DEEP", SEV_WARN,
                f"깊은 홀: {h['name']} (깊이/직경 = {h['depth_mm'] / d:.1f})",
                f"깊이 {h['depth_mm']:.1f} mm / 직경 {d:.2f} mm 비율이 10:1을 넘습니다. "
                "일반 드릴로는 가공이 어렵습니다.",
                "관통 홀로 바꾸거나, 양쪽에서 가공하도록 분할하세요.",
                {"feature": h["name"]}))
    return out


def check_walls(facts):
    out = []
    for w in facts.get("walls", []):
        gap = w["gap_mm"]
        if gap < MIN_WALL_MM:
            out.append(_f(
                "WALL_TOO_THIN", SEV_WARN,
                f"얇은 벽: {gap:.2f} mm",
                f"마주보는 두 평면 사이가 {gap:.2f} mm로 기준 {MIN_WALL_MM} mm보다 얇습니다. "
                "가공 중 변형되거나 파손될 수 있습니다.",
                f"두께를 {MIN_WALL_MM} mm 이상으로 키우거나 리브(보강대)를 추가하세요.",
                {"faces": w["faces"]}))
    return out


def check_material(facts):
    if facts.get("kind") != "part":
        return []
    props = facts.get("props", {})
    mat = (props.get("material") or "").strip()
    if mat.lower() in GENERIC_MATERIALS or mat in GENERIC_MATERIALS:
        return [_f(
            "MATERIAL_NOT_SET", SEV_ERROR,
            f"재질 미지정 ({mat or '비어있음'})",
            "재질이 기본값('일반')입니다. 질량·무게중심·강도 계산이 모두 무의미해지고, "
            "도면 표제란과 BOM에도 잘못된 재질이 올라갑니다.",
            "부품 문서에서 도구 > 재질 을 열고 실제 재질(예: SS400, AL6061, SUS304)을 "
            "지정하세요.",
            {})]
    return []


def check_props(facts):
    out = []
    props = facts.get("props", {})
    for key, label in REQUIRED_PROPS.items():
        if key == "material":
            continue
        if not (props.get(key) or "").strip():
            out.append(_f(
                "PROP_MISSING", SEV_WARN,
                f"속성 누락: {label}",
                f"iProperty '{label}'가 비어 있습니다. 도면 표제란과 BOM이 빈칸으로 출력됩니다.",
                "파일 > iProperty > 프로젝트 탭에서 값을 입력하세요.",
                {"prop": key}))
    return out


def check_dimension_tolerances(facts):
    out = []
    for sheet in facts.get("sheets", []):
        for d in sheet.get("dims", []):
            val, where = d["value_mm"], {"sheet": sheet["name"], **_xy(d)}
            if d["tol_type"] == "none":
                state = text_tolerance_state(d.get("text"))
                if state in ("explicit", "fit", "not_applicable"):
                    continue
                if abs(val) >= TOL_REQUIRED_ABOVE_MM:
                    dev = iso2768_m(val)
                    out.append(_f(
                        "TOL_MISSING", SEV_WARN,
                        f"공차 없음: {d['text'] or f'{val:.2f} mm'}",
                        f"치수 {val:.2f} mm에 공차가 지정되지 않아 일반공차가 적용됩니다."
                        + (f" ISO 2768-m 기준 ±{dev} mm로 가공됩니다." if dev else ""),
                        "끼워맞춤이나 조립에 관여하는 치수라면 공차를 명시하세요. "
                        "치수를 더블클릭 > 공차 탭에서 편차/한계/끼워맞춤을 지정합니다. "
                        "일반공차로 충분하면 표제란에 'ISO 2768-m' 표기를 확인하세요.",
                        where))
                continue
            up, lo = d.get("upper_mm"), d.get("lower_mm")
            if up is not None and lo is not None:
                if up < lo:
                    out.append(_f(
                        "TOL_INVERTED", SEV_ERROR,
                        f"공차 상/하한 뒤바뀜: {val:.2f} mm ({up:+.3f}/{lo:+.3f})",
                        "상한이 하한보다 작습니다. 가공 불가능한 치수입니다.",
                        "치수 공차 탭에서 상한과 하한 값을 서로 바꾸세요.",
                        where))
                elif up == lo == 0:
                    out.append(_f(
                        "TOL_ZERO", SEV_ERROR,
                        f"공차 폭 0: {val:.2f} mm",
                        "상한과 하한이 모두 0이라 공차 폭이 없습니다. 물리적으로 가공 불가입니다.",
                        "실제 허용 편차를 입력하거나 공차 방식을 '기본'으로 되돌리세요.",
                        where))
                else:
                    dev = iso2768_m(val)
                    span = up - lo
                    if dev and span > 2 * dev * 4:
                        out.append(_f(
                            "TOL_TOO_LOOSE", SEV_INFO,
                            f"공차가 매우 느슨함: {val:.2f} mm (폭 {span:.3f} mm)",
                            f"공차 폭 {span:.3f} mm는 ISO 2768-m 일반공차(±{dev} mm)보다 "
                            "4배 이상 넓습니다. 공차를 지정한 의미가 없습니다.",
                            "공차를 제거해 일반공차에 맡기거나, 실제 기능에 맞게 좁히세요.",
                            where))
    return out


def check_missing_dimensions(facts):
    out = []
    for sheet in facts.get("sheets", []):
        for c in sheet.get("undimensioned", []):
            n = c.get("count", 1)
            places = f" ({n}곳)" if n > 1 else ""
            out.append(_f(
                "DIM_MISSING", SEV_ERROR,
                f"치수 없는 원형 형상: Ø{c['diameter_mm']:.2f} mm{places}",
                f"도면의 원/호(Ø{c['diameter_mm']:.2f} mm)에 치수가 붙어 있지 않습니다. "
                + (f"같은 직경이 {n}곳 있습니다. " if n > 1 else "")
                + "가공자가 크기를 알 수 없습니다.",
                "해당 원을 클릭하고 치수(D)를 추가하세요. 홀이라면 "
                "주석 > 홀/스레드 노트를 쓰면 규격까지 함께 표기됩니다."
                + (f" 동일한 홀 {n}개는 '{n}×Ø{c['diameter_mm']:.1f}'로 한 번만 "
                   "기입하면 됩니다." if n > 1 else ""),
                {"sheet": sheet["name"], "x_cm": c["x_cm"], "y_cm": c["y_cm"],
                 "diameter_mm": c["diameter_mm"], "count": n}))
    return out


def check_drawing_meta(facts):
    out = []
    if facts.get("first_angle") is None and facts.get("kind") == "drawing":
        pass
    for sheet in facts.get("sheets", []):
        if not sheet.get("title_block") and not sheet.get("border"):
            out.append(_f(
                "TITLEBLOCK_MISSING", SEV_ERROR,
                f"표제란 없음: {sheet['name']}",
                "시트에 표제란(Title Block)도 도면 양식(Border)도 없습니다. "
                "품번·재질·척도·투상법이 표기되지 않은 도면은 출도할 수 없습니다.",
                "브라우저에서 시트 우클릭 > 표제란 삽입 을 실행하세요.",
                {"sheet": sheet["name"]}))
        for v in sheet.get("views", []):
            if v["scale"] and v["scale"] not in (
                    1.0, 0.5, 0.25, 0.2, 0.1, 2.0, 4.0, 5.0, 10.0, 0.05, 0.02, 0.01):
                out.append(_f(
                    "SCALE_NONSTANDARD", SEV_WARN,
                    f"비표준 척도: {v['name']} = {v.get('scale_string') or v['scale']}",
                    f"척도 {v['scale']}는 표준 척도(1:1, 1:2, 1:5, 2:1 ...)가 아닙니다. "
                    "실측 오류를 유발합니다.",
                    "뷰 속성에서 표준 척도로 변경하세요.",
                    {"sheet": sheet["name"], "view": v["name"]}))
    if facts.get("kind") == "drawing" and not any(
            s.get("dims") for s in facts.get("sheets", [])):
        out.append(_f(
            "NO_DIMENSIONS_AT_ALL", SEV_ERROR,
            "도면에 치수가 전혀 없음",
            "시트 전체에 치수가 하나도 없습니다. 제작 도면으로 사용할 수 없습니다.",
            "주석 > 치수 로 주요 치수를 넣거나, 관리 > 주석 검색 으로 "
            "모델 치수를 일괄 가져오세요.",
            {}))
    return out


def check_references(facts):
    if facts.get("refs_ok", True):
        return []
    return [_f(
        "REFS_BROKEN", SEV_WARN,
        "모델 참조가 끊어져 형상 검사를 못 했습니다",
        "도면(.idw)은 부품/조립 파일(.ipt/.iam)을 경로로 참조합니다. "
        "도면 파일만 따로 올리면 참조가 끊겨서 원·홀 형상을 읽을 수 없고, "
        "치수 누락 검사가 '문제 없음'으로 잘못 나옵니다. "
        "치수·공차·표제란 검사 결과는 정상입니다.",
        "도면과 모델 파일을 함께 압축(.zip)해서 올리거나, "
        "'로컬 경로로 분석'에 원본 폴더의 도면 경로를 그대로 입력하세요. "
        "그러면 참조가 유지된 상태로 검사합니다.",
        {})]


def check_interference(facts):
    out = []
    for it in facts.get("interferences", []):
        out.append(_f(
            "INTERFERENCE", SEV_ERROR,
            f"부품 간섭: {it['a']} ↔ {it['b']} ({it['volume_mm3']:.1f} mm³)",
            f"두 부품이 {it['volume_mm3']:.1f} mm³ 겹칩니다. 물리적으로 조립 불가능합니다.",
            "구속조건(Constraint)을 확인하고 위치를 수정하거나, "
            "간섭 부위 형상을 절삭하세요. 검사 > 간섭 분석 으로 위치를 시각적으로 확인할 수 있습니다.",
            {"a": it["a"], "b": it["b"]}))
    return out


def check_sick_features(facts):
    out = []
    for f in facts.get("sick_features", []):
        out.append(_f(
            "FEATURE_SICK", SEV_ERROR,
            f"오류 피처: {f['name']}",
            f"피처가 정상 상태가 아닙니다 (상태 코드 {f['status']}). "
            "모델이 의도한 형상과 다를 수 있습니다.",
            "브라우저에서 해당 피처를 우클릭 > 편집 하여 참조가 끊긴 스케치나 "
            "면을 다시 지정하세요.",
            {"feature": f["name"]}))
    return out


def _xy(d):
    return {k: d[k] for k in ("x_cm", "y_cm") if d.get(k) is not None}


ALL_CHECKS = (
    check_sketches, check_holes, check_walls, check_material, check_props,
    check_dimension_tolerances, check_missing_dimensions, check_drawing_meta,
    check_interference, check_sick_features, check_references,
)

_SEV_ORDER = {SEV_ERROR: 0, SEV_WARN: 1, SEV_INFO: 2}


def run(facts):
    findings = []
    for chk in ALL_CHECKS:
        try:
            findings += chk(facts)
        except Exception as e:
            findings.append(_f("RULE_ERROR", SEV_INFO, f"검사 규칙 오류: {chk.__name__}",
                               f"{type(e).__name__}: {e}", "개발자에게 알려주세요."))
    findings.sort(key=lambda f: _SEV_ORDER.get(f["severity"], 9))
    summary = {
        "total": len(findings),
        "error": sum(1 for f in findings if f["severity"] == SEV_ERROR),
        "warn": sum(1 for f in findings if f["severity"] == SEV_WARN),
        "info": sum(1 for f in findings if f["severity"] == SEV_INFO),
    }
    return findings, summary

