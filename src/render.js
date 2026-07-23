// Renders the parsed DXF geometry as an SVG string with findings highlighted
// directly on the drawing — so a viewer can see at a glance where/what is
// wrong instead of just reading a text list.

const SEVERITY_COLOR = { high: "#ff5470", medium: "#ffb454", low: "#3ddc97" };
const SEVERITY_RANK = { high: 3, medium: 2, low: 1 };

function escapeXml(s) {
  return String(s).replace(/[<>&"']/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" }[c]));
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
  const padX = Math.max((maxX - minX) * 0.08, 2);
  const padY = Math.max((maxY - minY) * 0.08, 2);
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

// Which findings apply to which layer, keeping the worst severity per layer.
function worstSeverityByLayer(findings) {
  const byLayer = new Map();
  const unplaced = [];
  for (const f of findings) {
    if (!f.location_hint) { unplaced.push(f); continue; }
    const cur = byLayer.get(f.location_hint);
    if (!cur || SEVERITY_RANK[f.severity] > SEVERITY_RANK[cur]) byLayer.set(f.location_hint, f.severity);
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
  const markers = [];
  for (const dim of data.dimensions) {
    if (dim.x == null || dim.y == null || !dim.layer) continue;
    const sev = byLayer.get(dim.layer);
    if (!sev) continue;
    const cx = dim.x;
    const cy = y(dim.y);
    const color = SEVERITY_COLOR[sev] || SEVERITY_COLOR.low;
    markers.push(
      `<circle cx="${cx}" cy="${cy}" r="${markerR * 2.2}" fill="${color}" opacity="0.18" />` +
      `<circle cx="${cx}" cy="${cy}" r="${markerR}" fill="${color}" stroke="#06070d" stroke-width="${markerR * 0.25}" />`
    );
  }

  const badge = unplaced.length
    ? `<g transform="translate(${minX + width * 0.02}, ${minY + height * 0.06})">
         <rect x="0" y="-14" width="${16 + unplaced.length.toString().length * 9 + 40}" height="22" rx="11" fill="#ff5470" opacity="0.85" />
         <text x="10" y="2" font-size="${Math.max(width, height) * 0.028}" fill="#06070d" font-weight="700">⚠ 도면 전체 ${unplaced.length}건</text>
       </g>`
    : "";

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX} ${minY} ${width} ${height}" font-family="monospace">
    <style>
      .geom { stroke: #4a5468; stroke-width: ${Math.max(width, height) * 0.0025}; vector-effect: non-scaling-stroke; }
    </style>
    <rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="#0b0e18" />
    ${geomLines.join("\n")}
    ${markers.join("\n")}
    ${badge}
  </svg>`;
}
