// 프론트엔드와 API가 같은 Cloudflare Worker에서 서빙되므로 상대 경로만 있으면 됨.
const BACKEND_URL = "";

const fileInput = document.getElementById("fileInput");
const fileNameDisplay = document.getElementById("fileNameDisplay");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusEl = document.getElementById("status");
const progressPanel = document.getElementById("progressPanel");
const stepEls = progressPanel.querySelectorAll(".steps li");
const ruleSection = document.getElementById("ruleResults");
const aiSection = document.getElementById("aiResults");
const ruleCards = document.getElementById("ruleCards");
const aiCards = document.getElementById("aiCards");
const diagramSection = document.getElementById("diagramResult");
const diagramContainer = document.getElementById("diagramContainer");
const diagramNote = document.getElementById("diagramNote");
const downloadBtn = document.getElementById("downloadBtn");

let lastReport = null;

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileNameDisplay.textContent = file ? `> ${file.name}_` : "> 파일을 선택하세요_";
  analyzeBtn.disabled = !file;
});

// APS Viewer는 처음 필요할 때만 CDN에서 로드 (DXF만 쓰는 사람은 안 받아도 됨).
let apsViewerLoading = null;
function loadApsViewerLibs() {
  if (window.Autodesk?.Viewing) return Promise.resolve();
  if (apsViewerLoading) return apsViewerLoading;
  apsViewerLoading = new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "https://developer.api.autodesk.com/modelderivative/v2/viewers/7.*/style.min.css";
    document.head.appendChild(css);

    const script = document.createElement("script");
    script.src = "https://developer.api.autodesk.com/modelderivative/v2/viewers/7.*/viewer3D.min.js";
    script.onload = resolve;
    script.onerror = () => reject(new Error("APS Viewer 라이브러리 로드 실패"));
    document.head.appendChild(script);
  });
  return apsViewerLoading;
}

const SEVERITY_RANK = { high: 3, medium: 2, low: 1 };
const SEVERITY_COLOR = { high: "#ff5470", medium: "#ffb454", low: "#3ddc97" };
const CATEGORY_LABEL = {
  missing_dimension: "치수 누락",
  missing_tolerance: "공차 누락",
  standard_violation: "표준 위반",
};

// AI가 location_hint에 "레이어 0, 2, MOT"처럼 접두어/나열을 붙여도 검색은 되게
// 쉼표 기준으로만 쪼갠다 — "중심 표식(ISO)"처럼 실제 레이어명 안에 공백이 있을 수
// 있어서 공백으로는 쪼개면 안 된다. 접두어(레이어/layer)만 골라서 제거한다.
const LOCATION_STOPWORDS = new Set(["layer", "layers", "레이어", "location", "unknown", "n/a", ""]);
const LOCATION_PREFIX = /^(레이어|layer)\s*[:：]?\s*/i;

function extractLocationTokens(hint) {
  return hint
    .split(",")
    .map((t) => t.trim().replace(LOCATION_PREFIX, "").trim())
    .filter((t) => t && !LOCATION_STOPWORDS.has(t.toLowerCase()));
}

// 레이어/객체명(location_hint)별로 가장 심각한 finding만 남겨서(카테고리/설명 포함),
// 뷰어 안의 실제 요소(dbId)를 찾아 그 위에 화살표+라벨을 그린다 — DXF SVG와 같은 방식.
function worstFindingByLocation(findings) {
  const byLocation = new Map();
  for (const f of findings || []) {
    if (!f.location_hint) continue;
    for (const token of extractLocationTokens(f.location_hint)) {
      const cur = byLocation.get(token);
      if (!cur || SEVERITY_RANK[f.severity] > SEVERITY_RANK[cur.severity]) {
        byLocation.set(token, { severity: f.severity, category: f.category, description: f.description });
      }
    }
  }
  return byLocation;
}

// 라이브 3D 뷰어를 계속 띄워놓고 카메라를 움직일 때마다 마커를 다시 그리면
// 어긋나기 쉽고 무겁다 — 모델 로드가 끝난 시점의 뷰를 스냅샷(이미지)으로
// 한 번 캡처해서, 그 위에 화살표를 고정으로 그린 정적 결과물을 보여준다.
function resolveApsMarkers(viewer, findings) {
  const byLocation = worstFindingByLocation(findings);
  if (!byLocation.size) return Promise.resolve([]);

  const searches = [...byLocation].map(
    ([location, finding]) =>
      new Promise((resolve) => {
        viewer.search(
          location,
          (dbIds) => resolve(dbIds.map((dbId) => ({ dbId, ...finding }))),
          () => resolve([]),
          ["Layer", "name"]
        );
      })
  );

  return Promise.all(searches).then((groups) => {
    const box = new Float32Array(6);
    const markers = [];
    for (const { dbId, severity, category, description } of groups.flat()) {
      try {
        viewer.model.getInstanceTree().getNodeBox(dbId, box);
      } catch {
        continue;
      }
      if (!Number.isFinite(box[0])) continue;
      const center = { x: (box[0] + box[3]) / 2, y: (box[1] + box[4]) / 2, z: (box[2] + box[5]) / 2 };
      const p = viewer.worldToClient(center);
      markers.push({ x: p.x, y: p.y, severity, category, description });
    }
    return markers;
  });
}

function apsArrowheadDefs() {
  return Object.entries(SEVERITY_COLOR)
    .map(
      ([sev, color]) =>
        `<marker id="aps-arrowhead-${sev}" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
           <path d="M0,0 L6,3 L0,6 Z" fill="${color}" />
         </marker>`
    )
    .join("");
}

function renderApsMarkerSvg(markers, width, height) {
  let toggle = 0;
  const shapes = markers
    .map(({ x, y, severity, category, description }) => {
      toggle += 1;
      const dir = toggle % 2 === 0 ? 1 : -1;
      const lx = x + 46 * dir;
      const ly = y - 40;
      const s = SEVERITY_COLOR[severity] ? severity : "low";
      const color = SEVERITY_COLOR[s];
      const label = CATEGORY_LABEL[category] || "문제 발견";
      const safeDesc = (description || label).replace(/[<>&]/g, "");
      return (
        `<circle cx="${x}" cy="${y}" r="10" fill="${color}" opacity="0.22" />` +
        `<circle cx="${x}" cy="${y}" r="5" fill="${color}" stroke="#06070d" stroke-width="1.5"><title>${safeDesc}</title></circle>` +
        `<line x1="${lx}" y1="${ly}" x2="${x}" y2="${y}" stroke="${color}" stroke-width="2" marker-end="url(#aps-arrowhead-${s})" />` +
        `<rect x="${dir > 0 ? lx : lx - label.length * 13 - 12}" y="${ly - 16}" width="${label.length * 13 + 12}" height="22" rx="4" fill="#06070d" stroke="${color}" stroke-width="1.2" />` +
        `<text x="${dir > 0 ? lx + 6 : lx - label.length * 13 - 6}" y="${ly - 1}" font-size="13" font-family="Consolas, monospace" font-weight="700" fill="${color}">${label}</text>`
      );
    })
    .join("");
  return `<svg class="aps-marker-layer" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}"><defs>${apsArrowheadDefs()}</defs>${shapes}</svg>`;
}

let apsViewerReady = false;
async function renderApsViewer(urn, findings) {
  await loadApsViewerLibs();
  const wrap = document.createElement("div");
  wrap.className = "aps-viewer";
  diagramContainer.appendChild(wrap);

  const initOptions = {
    env: "AutodeskProduction2",
    api: "streamingV2",
    getAccessToken: async (onTokenReady) => {
      const res = await fetch(`${BACKEND_URL}/aps-token`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "APS 토큰 발급 실패");
      onTokenReady(data.access_token, data.expires_in);
    },
  };

  const loadAndCapture = () =>
    new Promise((resolve, reject) => {
      const viewer = new Autodesk.Viewing.GuiViewer3D(wrap);
      viewer.start();
      viewer.addEventListener(Autodesk.Viewing.GEOMETRY_LOADED_EVENT, async function onLoaded() {
        viewer.removeEventListener(Autodesk.Viewing.GEOMETRY_LOADED_EVENT, onLoaded);
        try {
          viewer.fitToView();
          const markers = await resolveApsMarkers(viewer, findings);
          const rect = wrap.getBoundingClientRect();
          viewer.getScreenShot(undefined, undefined, (blobUrl) => {
            viewer.finish();
            wrap.innerHTML =
              `<img class="aps-snapshot" src="${blobUrl}" alt="도면 스냅샷" />` +
              renderApsMarkerSvg(markers, rect.width, rect.height);
            resolve();
          });
        } catch (e) {
          reject(e);
        }
      });
      Autodesk.Viewing.Document.load(
        `urn:${urn}`,
        (doc) => {
          const viewables = doc.getRoot().getDefaultGeometry();
          viewer.loadDocumentNode(doc, viewables);
        },
        (code, msg) => reject(new Error(msg || String(code)))
      );
    });

  if (!apsViewerReady) {
    await new Promise((resolve) => {
      Autodesk.Viewing.Initializer(initOptions, () => {
        apsViewerReady = true;
        resolve();
      });
    });
  }
  await loadAndCapture();
}

function renderDiagram(diagram) {
  if (!diagram) {
    diagramSection.classList.add("hidden");
    return;
  }
  diagramContainer.innerHTML = "";
  if (diagram.type === "svg") {
    diagramContainer.innerHTML = diagram.svg;
  } else if (diagram.type === "viewer") {
    renderApsViewer(diagram.urn, diagram.findings).catch((e) => setStatus(`도면 뷰어 로드 실패: ${e.message}`, true));
  } else if (diagram.type === "raster") {
    const img = document.createElement("img");
    img.src = `data:image/png;base64,${diagram.base64}`;
    img.alt = "분석된 도면 썸네일";
    diagramContainer.appendChild(img);
  }
  diagramNote.textContent = diagram.note || "";
  diagramSection.classList.remove("hidden");
}

function severityClass(sev) {
  return ["high", "medium", "low"].includes(sev) ? `sev-${sev}` : "sev-low";
}

function renderCards(container, findings) {
  container.innerHTML = "";
  if (!findings || findings.length === 0) {
    container.innerHTML = '<div class="empty-card">발견된 문제가 없습니다.</div>';
    return;
  }
  findings.forEach((f) => {
    const card = document.createElement("div");
    card.className = `card ${severityClass(f.severity)}`;
    card.innerHTML = `
      <div class="card-top">
        <span class="card-category">${f.category ?? ""}</span>
        <span class="badge ${severityClass(f.severity)}">${(f.severity ?? "").toUpperCase()}</span>
      </div>
      <div class="card-desc"></div>
      ${f.location_hint ? `<div class="card-loc">위치: ${f.location_hint}</div>` : ""}
    `;
    card.querySelector(".card-desc").textContent = f.description ?? "";
    container.appendChild(card);
  });
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

// 실제 서버 진행률 이벤트가 없어서, 파일 형식에 맞는 단계들을 순서대로
// "진행 중"으로 표시만 해주는 연출용 타이머. 실패해도 안전하게 stopProgress로 정리됨.
function startProgress(steps) {
  stepEls.forEach((li) => li.classList.remove("active", "done"));
  progressPanel.classList.remove("hidden");
  let i = 0;
  const activate = () => {
    if (i > 0) {
      const prev = progressPanel.querySelector(`[data-step="${steps[i - 1]}"]`);
      prev?.classList.replace("active", "done");
    }
    if (i < steps.length) {
      progressPanel.querySelector(`[data-step="${steps[i]}"]`)?.classList.add("active");
      i += 1;
    }
  };
  activate();
  const timer = setInterval(() => {
    if (i >= steps.length) return;
    activate();
  }, 1100);
  return () => clearInterval(timer);
}

function stopProgress(stopTimer) {
  stopTimer();
  stepEls.forEach((li) => li.classList.remove("active"));
  progressPanel.querySelectorAll("[data-step]").forEach((li) => li.classList.add("done"));
  setTimeout(() => progressPanel.classList.add("hidden"), 500);
}

analyzeBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    setStatus("파일을 먼저 선택하세요.", true);
    return;
  }

  const isAps = /\.(dwg|ipt|iam|idw)$/i.test(file.name);

  analyzeBtn.disabled = true;
  setStatus(isAps ? "분석 중... (DWG/IPT/IAM/IDW는 시간이 좀 걸릴 수 있습니다)" : "분석 중...");
  ruleSection.classList.add("hidden");
  aiSection.classList.add("hidden");
  diagramSection.classList.add("hidden");
  downloadBtn.classList.add("hidden");
  const stopTimer = startProgress(["upload", "rule", "ai", "done"]);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${BACKEND_URL}/analyze`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `서버 오류 (${res.status})`);
    }

    const result = await res.json();
    renderDiagram(result.diagram);
    renderCards(ruleCards, result.rule_findings);
    ruleSection.classList.remove("hidden");

    if (result.ai_error) {
      setStatus(result.ai_error);
    } else {
      setStatus("분석 완료");
    }
    renderCards(aiCards, result.ai_findings);
    aiSection.classList.remove("hidden");

    lastReport = [...(result.rule_findings || []), ...(result.ai_findings || [])];
    downloadBtn.classList.remove("hidden");
  } catch (e) {
    setStatus(`분석 중 오류가 발생했습니다: ${e.message}`, true);
  } finally {
    analyzeBtn.disabled = false;
    stopProgress(stopTimer);
  }
});

downloadBtn.addEventListener("click", () => {
  if (!lastReport) return;
  const blob = new Blob([JSON.stringify(lastReport, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "report.json";
  a.click();
  URL.revokeObjectURL(url);
});
