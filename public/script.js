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

function dotClass(sev) {
  return ["high", "medium", "low"].includes(sev) ? `dot-${sev}` : "dot-low";
}

// 레이어/객체명(location_hint)별로 가장 심각한 findings만 남겨서, 뷰어 안의
// 실제 요소(dbId)를 찾아 그 위에 점을 찍는다 — DXF SVG 마커와 같은 방식.
function worstSeverityByLocation(findings) {
  const byLocation = new Map();
  for (const f of findings || []) {
    if (!f.location_hint) continue;
    const cur = byLocation.get(f.location_hint);
    if (!cur || SEVERITY_RANK[f.severity] > SEVERITY_RANK[cur]) byLocation.set(f.location_hint, f.severity);
  }
  return byLocation;
}

function placeApsMarkers(viewer, markerLayer, findings) {
  const byLocation = worstSeverityByLocation(findings);
  if (!byLocation.size) return;

  const hits = []; // { dbId, severity }
  let pending = byLocation.size;

  const layout = () => {
    markerLayer.innerHTML = "";
    const box = new Float32Array(6);
    for (const { dbId, severity } of hits) {
      try {
        viewer.model.getInstanceTree().getNodeBox(dbId, box);
      } catch {
        continue;
      }
      if (!Number.isFinite(box[0])) continue;
      const center = { x: (box[0] + box[3]) / 2, y: (box[1] + box[4]) / 2, z: (box[2] + box[5]) / 2 };
      const p = viewer.worldToClient(center);
      const dot = document.createElement("div");
      dot.className = `aps-marker ${dotClass(severity)}`;
      dot.style.left = `${p.x}px`;
      dot.style.top = `${p.y}px`;
      markerLayer.appendChild(dot);
    }
  };

  const onDone = () => {
    pending -= 1;
    if (pending > 0) return;
    if (!hits.length) return;
    layout();
    viewer.addEventListener(Autodesk.Viewing.CAMERA_CHANGE_EVENT, layout);
  };

  for (const [location, severity] of byLocation) {
    viewer.search(
      location,
      (dbIds) => {
        for (const dbId of dbIds) hits.push({ dbId, severity });
        onDone();
      },
      onDone,
      undefined
    );
  }
}

let apsViewerReady = false;
async function renderApsViewer(urn, findings) {
  await loadApsViewerLibs();
  const wrap = document.createElement("div");
  wrap.className = "aps-viewer";
  const markerLayer = document.createElement("div");
  markerLayer.className = "aps-marker-layer";
  wrap.appendChild(markerLayer);
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

  const start = () => {
    const viewer = new Autodesk.Viewing.GuiViewer3D(wrap);
    viewer.start();
    viewer.addEventListener(Autodesk.Viewing.GEOMETRY_LOADED_EVENT, function onLoaded() {
      viewer.removeEventListener(Autodesk.Viewing.GEOMETRY_LOADED_EVENT, onLoaded);
      placeApsMarkers(viewer, markerLayer, findings);
    });
    Autodesk.Viewing.Document.load(
      `urn:${urn}`,
      (doc) => {
        const viewables = doc.getRoot().getDefaultGeometry();
        viewer.loadDocumentNode(doc, viewables);
      },
      (code, msg) => setStatus(`도면 뷰어 로드 실패: ${msg || code}`, true)
    );
  };

  if (apsViewerReady) {
    start();
  } else {
    Autodesk.Viewing.Initializer(initOptions, () => {
      apsViewerReady = true;
      start();
    });
  }
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
