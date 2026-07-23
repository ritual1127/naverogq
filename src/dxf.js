// Minimal DXF ASCII tag parser — extracts just what the rule checks and the
// SVG renderer need (dimensions w/ position, text, layers, raw geometry).
// Not a full DXF implementation; ezdxf's get_measurement() does real
// geometry math, we only read the "actual measurement" group code (42) when
// AutoCAD already wrote it.

function tokenize(content) {
  const lines = content.split(/\r\n|\r|\n/);
  const tokens = [];
  for (let i = 0; i + 1 < lines.length; i += 2) {
    const code = parseInt(lines[i].trim(), 10);
    const value = lines[i + 1].trim();
    if (Number.isNaN(code)) continue;
    tokens.push([code, value]);
  }
  return tokens;
}

export function parseDxf(content) {
  const tokens = tokenize(content);

  const dimensions = [];
  const texts = [];
  const layerNames = [];
  const geometryCounts = { lines: 0, circles_arcs: 0 };
  const shapes = []; // for SVG rendering: {type, layer, ...geometry}

  let table = null; // LAYER, LTYPE, ... (inside TABLES)
  let sawSectionCode2 = false;
  let entityType = null;
  let entity = null;

  const flushEntity = () => {
    if (!entity) return;
    if (entityType === "DIMENSION") {
      const point = entity.textX != null ? { x: entity.textX, y: entity.textY } : { x: entity.x, y: entity.y };
      dimensions.push({
        text: entity.text && entity.text !== "<>" ? entity.text : null,
        measurement: entity.measurement ?? null,
        layer: entity.layer ?? null,
        style: entity.style ?? null,
        x: point.x ?? null,
        y: point.y ?? null,
      });
    } else if (entityType === "TEXT" || entityType === "MTEXT") {
      if (entity.text) texts.push(entity.text);
    } else if (entityType === "LINE") {
      geometryCounts.lines += 1;
      if (entity.x1 != null) {
        shapes.push({ type: "LINE", layer: entity.layer, x1: entity.x1, y1: entity.y1, x2: entity.x2, y2: entity.y2 });
      }
    } else if (entityType === "CIRCLE") {
      geometryCounts.circles_arcs += 1;
      if (entity.x != null) shapes.push({ type: "CIRCLE", layer: entity.layer, x: entity.x, y: entity.y, r: entity.r });
    } else if (entityType === "ARC") {
      geometryCounts.circles_arcs += 1;
      if (entity.x != null) {
        shapes.push({
          type: "ARC",
          layer: entity.layer,
          x: entity.x,
          y: entity.y,
          r: entity.r,
          start: entity.start ?? 0,
          end: entity.end ?? 360,
        });
      }
    } else if (entityType === "LAYER" && table === "LAYER") {
      if (entity.name) layerNames.push(entity.name);
    }
    entity = null;
    entityType = null;
  };

  for (const [code, value] of tokens) {
    if (code === 0) {
      flushEntity();
      if (value === "SECTION" || value === "TABLE") {
        sawSectionCode2 = false;
        if (value === "TABLE") table = null;
      } else if (value === "ENDSEC") {
        table = null;
      } else if (value === "ENDTAB") {
        table = null;
      } else {
        entityType = value;
        entity = {};
      }
      continue;
    }

    if (entity === null) {
      if (code === 2 && !sawSectionCode2) {
        table = value; // names the current TABLE (harmless if it's actually a SECTION name)
        sawSectionCode2 = true;
      }
      continue;
    }

    if (entityType === "DIMENSION") {
      if (code === 8) entity.layer = value;
      else if (code === 1) entity.text = value;
      else if (code === 3) entity.style = value;
      else if (code === 42) entity.measurement = parseFloat(value);
      else if (code === 10) entity.x = parseFloat(value);
      else if (code === 20) entity.y = parseFloat(value);
      else if (code === 11) entity.textX = parseFloat(value);
      else if (code === 21) entity.textY = parseFloat(value);
    } else if (entityType === "TEXT" || entityType === "MTEXT") {
      if (code === 1) entity.text = value;
    } else if (entityType === "LINE") {
      if (code === 8) entity.layer = value;
      else if (code === 10) entity.x1 = parseFloat(value);
      else if (code === 20) entity.y1 = parseFloat(value);
      else if (code === 11) entity.x2 = parseFloat(value);
      else if (code === 21) entity.y2 = parseFloat(value);
    } else if (entityType === "CIRCLE") {
      if (code === 8) entity.layer = value;
      else if (code === 10) entity.x = parseFloat(value);
      else if (code === 20) entity.y = parseFloat(value);
      else if (code === 40) entity.r = parseFloat(value);
    } else if (entityType === "ARC") {
      if (code === 8) entity.layer = value;
      else if (code === 10) entity.x = parseFloat(value);
      else if (code === 20) entity.y = parseFloat(value);
      else if (code === 40) entity.r = parseFloat(value);
      else if (code === 50) entity.start = parseFloat(value);
      else if (code === 51) entity.end = parseFloat(value);
    } else if (entityType === "LAYER") {
      if (code === 2) entity.name = value;
    }
  }
  flushEntity();

  return { dimensions, texts, layers: layerNames, geometry_counts: geometryCounts, shapes };
}

const TOLERANCE_MARKERS = ["±", "+/-", "h6", "h7", "h8", "H6", "H7", "H8", "js", "JS"];

function checkMissingTolerance(data) {
  const findings = [];
  for (const dim of data.dimensions) {
    const text = dim.text || "";
    if (!TOLERANCE_MARKERS.some((m) => text.includes(m))) {
      findings.push({
        category: "missing_tolerance",
        description: `치수(레이어: ${dim.layer})에 공차 표기가 없습니다 (KS B 0412 공차 표기 기준 확인 필요).`,
        severity: "medium",
        location_hint: dim.layer,
        source: "rule",
      });
    }
  }
  return findings;
}

// AI/OCR 최적화 표준: "4-Ø10" 같은 하이픈 표기 대신 "4XØ10"(ISO/ASME 국제 표준
// 구분자)을 권장한다. %%c는 옛 AutoCAD DXF에서 지름 기호(Ø)를 나타내는 표기.
const HOLE_CALLOUT_HYPHEN = /(\d+)\s*-\s*(%%[Cc]|[ØøΦφ⌀])/;

function checkHoleCalloutNotation(data) {
  const findings = [];
  const allTexts = [...data.texts, ...data.dimensions.map((d) => d.text).filter(Boolean)];
  for (const text of allTexts) {
    const match = text.match(HOLE_CALLOUT_HYPHEN);
    if (match) {
      findings.push({
        category: "standard_violation",
        description: `"${match[0]}" — 하이픈 표기(N-Ø) 대신 국제 표준 구분자 "${match[1]}XØ" 표기를 권장합니다 (AI/OCR 파싱 정확도 향상).`,
        severity: "low",
        location_hint: null,
        source: "rule",
      });
    }
  }
  return findings;
}

// 형상 요소 수 대비 치수 개수만으로 판단하는 부분이라 DXF/APS 양쪽에서 재사용.
export function checkMissingDimensionFromCounts(geometryTotal, dimCount) {
  const findings = [];
  if (geometryTotal > 0 && dimCount === 0) {
    findings.push({
      category: "missing_dimension",
      description: "도면에 형상 요소는 있지만 치수 기입이 전혀 없습니다.",
      severity: "high",
      location_hint: null,
      source: "rule",
    });
  } else if (geometryTotal > 20 && dimCount < geometryTotal * 0.1) {
    findings.push({
      category: "missing_dimension",
      description: `형상 요소(${geometryTotal}개)에 비해 치수(${dimCount}개)가 적어 누락 가능성이 있습니다.`,
      severity: "low",
      location_hint: null,
      source: "rule",
    });
  }
  return findings;
}

function checkMissingDimension(data) {
  const geometryTotal = data.geometry_counts.lines + data.geometry_counts.circles_arcs;
  return checkMissingDimensionFromCounts(geometryTotal, data.dimensions.length);
}

// KS 치수 기입 원칙 "중복 기입 금지" — 같은 값이 여러 DIMENSION에 반복 기입되면
// 실제로 중복 표기일 가능성이 높다. measurement가 없으면(그룹코드 42 미기록)
// 판단할 근거가 없으니 건너뛴다.
function checkDuplicateDimensions(data) {
  const findings = [];
  const groups = new Map();
  for (const dim of data.dimensions) {
    if (dim.measurement == null) continue;
    const key = dim.measurement.toFixed(2);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(dim);
  }
  for (const [value, dims] of groups) {
    if (dims.length < 2) continue;
    const layers = [...new Set(dims.map((d) => d.layer).filter(Boolean))];
    findings.push({
      category: "standard_violation",
      description: `동일한 치수 값(${value})이 ${dims.length}곳에 중복 기입되어 있습니다 (KS 치수 기입 원칙 — 중복 기입 금지).`,
      severity: "low",
      location_hint: layers.join(", ") || null,
      source: "rule",
    });
  }
  return findings;
}

function checkDimstyleDefined(data) {
  const findings = [];
  for (const dim of data.dimensions) {
    if (!dim.style) {
      findings.push({
        category: "standard_violation",
        description: "치수에 도면 스타일(DIMSTYLE)이 지정되지 않았습니다.",
        severity: "low",
        location_hint: dim.layer,
        source: "rule",
      });
    }
  }
  return findings;
}

export function runAllChecks(data) {
  return [
    ...checkMissingTolerance(data),
    ...checkMissingDimension(data),
    ...checkDuplicateDimensions(data),
    ...checkHoleCalloutNotation(data),
    ...checkDimstyleDefined(data),
  ];
}
