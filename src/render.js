// Renders the parsed DXF geometry as an SVG string with findings highlighted
// directly on the drawing — so a viewer can see at a glance where/what is
// wrong instead of just reading a text list.

const SEVERITY_COLOR = { high: "#ff5470", medium: "#ffb454", low: "#3ddc97" };
const SEVERITY_RANK = { high: 3, medium: 2, low: 1 };
const CATEGORY_LABEL = {
  missing_dimension: "치수 누락",
  extra_dimension: "치수 중복/과잉",
  missing_tolerance: "공차 누락",
  dimension_placement: "치수 위치 오류",
  centerline_error: "중심선 오류",
  hidden_line_error: "숨은선 오류",
  projection_error: "투상도/정렬 오류",
  line_type_error: "선종류/선굵기 오류",
  symmetry_error: "대칭 오류",
  geometry_mismatch: "형상 불일치",
  titleblock_error: "표제란 오류",
  standard_violation: "표준 위반",
};

function escapeXml(s) {
  return String(s).replace(/[<>&"']/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" }[c]));
}

// ①②③... 유니코드 원문자 (1~20), 그 이상은 "(21)" 식으로 폴백.
function circledNumber(n) {
  return n >= 1 && n <= 20 ? String.fromCodePoint(0x2460 + n - 1) : `(${n})`;
}

function computeBounds(data) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const consider = (x, y) => {
    if (x == null || y == null || Number.isNaN(x) || Number.isNaN(y)) return;
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  };
  for (const s of data.shapes) {
    if (s.type === "LINE") { consider(s.x1, s.y1); consider(s.x2, s.y2); }
    else if (s.type === "CIRCLE" || s.type === "ARC") {
      consider(s.x - s.r, s.y - s.r); consider(s.x + s.r, s.y + s.r);
    }
  }
  for (const d of data.dimensions) consider(d.x, d.y);

  if (!Number.isFinite(minX)) return { minX: 0, minY: 0, maxX: 100, maxY: 100 };
  // 넉넉하게 여백을 둬서 화살표+설명 박스(여러 줄)가 도면 밖으로 잘리지 않게 한다.
  const padX = Math.max((maxX - minX) * 0.3, 6);
  const padY = Math.max((maxY - minY) * 0.35, 6);
  return { minX: minX - padX, minY: minY - padY, maxX: maxX + padX, maxY: maxY + padY };
}

function arcPath(cx, cy, r, startDeg, endDeg, flipY) {
  const toRad = (d) => (d * Math.PI) / 180;
  const y = (v) => (flipY ? -v : v);
  const x1 = cx + r * Math.cos(toRad(startDeg));
  const y1 = y(cy + r * Math.sin(toRad(startDeg)));
  const x2 = cx + r * Math.cos(toRad(endDeg));
  const y2 = y(cy + r * Math.sin(toRad(endDeg)));
  let sweep = endDeg - startDeg;
  if (sweep < 0) sweep += 360;
  const largeArc = sweep > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} ${flipY ? 0 : 1} ${x2} ${y2}`;
}

// Which findings apply to which layer, keeping the worst finding per layer
// (severity + its category, so the arrow label matches what's actually wrong).
function worstSeverityByLayer(findings) {
  const byLayer = new Map();
  const unplaced = [];
  for (const f of findings) {
    if (!f.location_hint) { unplaced.push(f); continue; }
    const cur = byLayer.get(f.location_hint);
    if (!cur || SEVERITY_RANK[f.severity] > SEVERITY_RANK[cur.severity]) {
      byLayer.set(f.location_hint, { severity: f.severity, category: f.category, description: f.description });
    }
  }
  return { byLayer, unplaced };
}

export function renderDxfSvg(data, findings) {
  const { minX, minY, maxX, maxY } = computeBounds(data);
  const width = maxX - minX;
  const height = maxY - minY;
  const y = (v) => minY + (maxY - v); // flip Y (DXF is math-up, SVG is screen-down)

  const { byLayer, unplaced } = worstSeverityByLayer(findings);

  const geomLines = [];
  for (const s of data.shapes) {
    if (s.type === "LINE") {
      geomLines.push(`<line x1="${s.x1}" y1="${y(s.y1)}" x2="${s.x2}" y2="${y(s.y2)}" class="geom" />`);
    } else if (s.type === "CIRCLE") {
      geomLines.push(`<circle cx="${s.x}" cy="${y(s.y)}" r="${s.r}" class="geom" fill="none" />`);
    } else if (s.type === "ARC") {
      geomLines.push(`<path d="${arcPath(s.x, s.y, s.r, s.start, s.end, true).replace(/M ([\d.-]+) ([\d.-]+)/, (m, px, py) => `M ${px} ${y(parseFloat(py) * -1)}`)}" class="geom" fill="none" />`);
    }
  }

  const markerR = Math.max(width, height) * 0.018;
  const fontSize = Math.max(width, height) * 0.026;
  const descFontSize = fontSize * 0.82;
  const maxCharsPerLine = 18;
  let labelToggle = 0;

  // 문장을 maxChars 기준으로 단어 단위로 감아서 여러 줄로 만든다 (SVG text는 자동 줄바꿈이 안 됨).
  const wrapText = (text, maxChars) => {
    const lines = [];
    let cur = "";
    for (let word of text.split(/\s+/).filter(Boolean)) {
      while (word.length > maxChars) {
        if (cur) { lines.push(cur); cur = ""; }
        lines.push(word.slice(0, maxChars));
        word = word.slice(maxChars);
      }
      const next = cur ? `${cur} ${word}` : word;
      if (next.length > maxChars) {
        lines.push(cur);
        cur = word;
      } else {
        cur = next;
      }
    }
    if (cur) lines.push(cur);
    return lines;
  };

  // 점만 찍으면 뭐가 문제인지 안 보이니, 문제 지점에서 화살표(리더선)로 당겨서
  // 카테고리 제목 + 설명 전문을 여러 줄 말풍선으로 적어준다 (제목만으론 부족해서 상세 설명까지 노출).
  const arrowMarker = (cx, cy, severity, category, description) => {
    const color = SEVERITY_COLOR[severity] || SEVERITY_COLOR.low;
    labelToggle += 1;
    const dir = labelToggle % 2 === 0 ? 1 : -1;
    const dx = markerR * 7 * dir;
    const dy = -markerR * 7;
    const lx = cx + dx;
    const ly = cy + dy;
    const title = `${circledNumber(labelToggle)} ${CATEGORY_LABEL[category] || "문제 발견"}`;
    const descLines = description ? wrapText(description, maxCharsPerLine) : [];

    const titleWidth = title.length * fontSize * 0.62;
    const descWidth = descLines.reduce((max, l) => Math.max(max, l.length * descFontSize * 0.62), 0);
    const textWidth = Math.max(titleWidth, descWidth) + fontSize;
    const boxX = dir > 0 ? lx : lx - textWidth;
    const lineGap = descFontSize * 1.35;
    const boxTop = ly - fontSize * 0.9;
    const boxHeight = fontSize * 1.4 + descLines.length * lineGap + (descLines.length ? fontSize * 0.3 : 0);
    const textX = dir > 0 ? lx + fontSize * 0.4 : lx - textWidth + fontSize * 0.4;

    const descTspans = descLines
      .map((l, i) => `<tspan x="${textX}" dy="${i === 0 ? fontSize * 1.1 : lineGap}" font-size="${descFontSize}" font-weight="400" fill="#e8e8ec">${escapeXml(l)}</tspan>`)
      .join("");

    return (
      `<circle cx="${cx}" cy="${cy}" r="${markerR * 2.2}" fill="${color}" opacity="0.18" />` +
      `<circle cx="${cx}" cy="${cy}" r="${markerR}" fill="${color}" stroke="#06070d" stroke-width="${markerR * 0.25}">` +
      (description ? `<title>${escapeXml(description)}</title>` : "") +
      `</circle>` +
      `<line x1="${lx}" y1="${ly}" x2="${cx}" y2="${cy}" stroke="${color}" stroke-width="${markerR * 0.35}" marker-end="url(#arrowhead-${severity})" />` +
      `<rect x="${boxX}" y="${boxTop}" width="${textWidth}" height="${boxHeight}" rx="3" fill="#06070d" stroke="${color}" stroke-width="${markerR * 0.15}" />` +
      `<text x="${textX}" y="${ly + fontSize * 0.15}" font-size="${fontSize}" fill="${color}" font-weight="700">${escapeXml(title)}${descTspans}</text>`
    );
  };

  const markers = [];
  for (const dim of data.dimensions) {
    if (dim.x == null || dim.y == null || !dim.layer) continue;
    const found = byLayer.get(dim.layer);
    if (!found) continue;
    markers.push(arrowMarker(dim.x, y(dim.y), found.severity, found.category, found.description));
  }

  // KS 도면은 형상 요소마다 치수가 있어야 하므로, 치수가 하나도 없는 레이어의
  // 형상 위에 직접 화살표를 그어 "어디에" 치수가 빠졌는지 짚어준다 (배지 텍스트 대신).
  const layersWithDims = new Set(data.dimensions.map((d) => d.layer).filter(Boolean));
  const shapeCenter = (s) => {
    if (s.type === "LINE") return { x: (s.x1 + s.x2) / 2, y: y((s.y1 + s.y2) / 2) };
    return { x: s.x, y: y(s.y) };
  };

  const stillUnplaced = [];
  for (const f of unplaced) {
    const bareShapes =
      f.category === "missing_dimension" ? data.shapes.filter((s) => s.layer && !layersWithDims.has(s.layer)) : [];
    if (!bareShapes.length) {
      stillUnplaced.push(f);
      continue;
    }
    // 도형마다 다 그리면 화살표/라벨이 서로 겹치니, 대표로 하나만 짚어준다.
    const { x: cx, y: cy } = shapeCenter(bareShapes[0]);
    markers.push(arrowMarker(cx, cy, f.severity, f.category, f.description));
  }

  const badge = stillUnplaced.length
    ? `<g transform="translate(${minX + width * 0.02}, ${minY + height * 0.06})">
         <rect x="0" y="-14" width="${16 + stillUnplaced.length.toString().length * 9 + 40}" height="22" rx="11" fill="#ff5470" opacity="0.85" />
         <text x="10" y="2" font-size="${Math.max(width, height) * 0.028}" fill="#06070d" font-weight="700">⚠ 도면 전체 ${stillUnplaced.length}건</text>
       </g>`
    : "";

  const arrowheadDefs = Object.entries(SEVERITY_COLOR)
    .map(
      ([sev, color]) =>
        `<marker id="arrowhead-${sev}" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
           <path d="M0,0 L6,3 L0,6 Z" fill="${color}" />
         </marker>`
    )
    .join("\n");

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX} ${minY} ${width} ${height}" font-family="monospace">
    <defs>${arrowheadDefs}</defs>
    <style>
      .geom { stroke: #4a5468; stroke-width: ${Math.max(width, height) * 0.0025}; vector-effect: non-scaling-stroke; }
    </style>
    <rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="#0b0e18" />
    ${geomLines.join("\n")}
    ${markers.join("\n")}
    ${badge}
  </svg>`;
}
