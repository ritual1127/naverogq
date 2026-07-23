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

function renderDiagram(diagram) {
  if (!diagram) {
    diagramSection.classList.add("hidden");
    return;
  }
  diagramContainer.innerHTML = "";
  if (diagram.type === "svg") {
    diagramContainer.innerHTML = diagram.svg;
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
