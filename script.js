// 백엔드(Render 등)에 배포한 뒤 이 주소를 실제 API URL로 바꾸세요.
const BACKEND_URL = "http://localhost:8000";

const fileInput = document.getElementById("fileInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusEl = document.getElementById("status");
const ruleSection = document.getElementById("ruleResults");
const aiSection = document.getElementById("aiResults");
const ruleTable = document.getElementById("ruleTable");
const aiTable = document.getElementById("aiTable");
const downloadBtn = document.getElementById("downloadBtn");

let lastReport = null;

function renderTable(table, findings) {
  table.innerHTML = "";
  if (!findings || findings.length === 0) {
    table.innerHTML = "<tr><td>발견된 문제가 없습니다.</td></tr>";
    return;
  }
  const headers = ["category", "description", "severity", "location_hint"];
  const headRow = document.createElement("tr");
  headers.forEach((h) => {
    const th = document.createElement("th");
    th.textContent = h;
    headRow.appendChild(th);
  });
  table.appendChild(headRow);

  findings.forEach((f) => {
    const row = document.createElement("tr");
    headers.forEach((h) => {
      const td = document.createElement("td");
      td.textContent = f[h] ?? "";
      row.appendChild(td);
    });
    table.appendChild(row);
  });
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

analyzeBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    setStatus("파일을 먼저 선택하세요.", true);
    return;
  }

  analyzeBtn.disabled = true;
  setStatus("분석 중... (DWG/IPT/IAM/IDW는 시간이 좀 걸릴 수 있습니다)");
  ruleSection.classList.add("hidden");
  aiSection.classList.add("hidden");
  downloadBtn.classList.add("hidden");

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
    renderTable(ruleTable, result.rule_findings);
    ruleSection.classList.remove("hidden");

    if (result.ai_error) {
      setStatus(result.ai_error);
    } else {
      setStatus("분석 완료");
    }
    renderTable(aiTable, result.ai_findings);
    aiSection.classList.remove("hidden");

    lastReport = [...(result.rule_findings || []), ...(result.ai_findings || [])];
    downloadBtn.classList.remove("hidden");
  } catch (e) {
    setStatus(`분석 중 오류가 발생했습니다: ${e.message}`, true);
  } finally {
    analyzeBtn.disabled = false;
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
