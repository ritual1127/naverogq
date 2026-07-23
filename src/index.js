import { parseDxf, runAllChecks } from "./dxf.js";
import { extractViaAps, getViewerToken, checkApsMissingDimension, APSError } from "./aps.js";
import { reviewDrawing, AIConfigError } from "./ai-review.js";
import { renderDxfSvg } from "./render.js";
import ksReference from "../Knowledge/ks_reference.md";

function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

const APS_EXTENSIONS = new Set([".dwg", ".ipt", ".iam", ".idw"]);

function extOf(filename) {
  const i = filename.lastIndexOf(".");
  return i === -1 ? "" : filename.slice(i).toLowerCase();
}

async function extractPdf(bytes) {
  // ponytail: text only, no page thumbnail (needs canvas, not available in
  // Workers) — upgrade to page-image extraction if visual PDF review matters.
  const { extractText, getDocumentProxy } = await import("unpdf");
  const pdf = await getDocumentProxy(bytes);
  const { text } = await extractText(pdf, { mergePages: true });
  return text;
}

async function handleAnalyze(request, env) {
  let form;
  try {
    form = await request.formData();
  } catch {
    return json({ detail: "multipart/form-data 요청이 아닙니다." }, 400);
  }
  const file = form.get("file");
  if (!file || typeof file === "string") {
    return json({ detail: "file 필드가 없습니다." }, 400);
  }

  const suffix = extOf(file.name);
  const bytes = new Uint8Array(await file.arrayBuffer());

  let ruleFindings = [];
  let imageBytes = null;
  let apsUrn = null;
  let dxfData = null;
  let summaryText = `파일명: ${file.name}\n`;

  try {
    if (suffix === ".dxf") {
      dxfData = parseDxf(new TextDecoder().decode(bytes));
      ruleFindings = runAllChecks(dxfData);
      summaryText += JSON.stringify(dxfData).slice(0, 4000);
    } else if (suffix === ".pdf") {
      const text = await extractPdf(bytes);
      summaryText += text.slice(0, 4000);
    } else if (APS_EXTENSIONS.has(suffix)) {
      const data = await extractViaAps(env, file.name, bytes);
      imageBytes = data.imageBytes;
      apsUrn = data.urn;
      ruleFindings = checkApsMissingDimension(data.metadataSummary);
      summaryText += data.metadataSummary
        ? JSON.stringify({ status: data.manifestStatus, ...data.metadataSummary }).slice(0, 4000)
        : JSON.stringify({ status: data.manifestStatus, note: "객체/레이어 메타데이터를 가져오지 못했습니다." });
    } else {
      return json({ detail: "지원하지 않는 파일 형식입니다." }, 400);
    }
  } catch (e) {
    if (e instanceof APSError) return json({ detail: e.message }, 400);
    return json({ detail: `파일 분석 중 오류가 발생했습니다: ${e.message}` }, 400);
  }

  let aiFindings = [];
  let aiError = null;
  try {
    aiFindings = await reviewDrawing(env, summaryText, imageBytes, ksReference);
  } catch (e) {
    aiError = e instanceof AIConfigError ? e.message : `AI 검토 중 오류가 발생했습니다: ${e.message}`;
  }

  // 도면 위에 문제 위치를 표시한 이미지 — DXF는 직접 렌더링(SVG). APS 계열은
  // findings를 프론트엔드로 넘겨서, 뷰어가 로드된 후 location_hint와 일치하는
  // 레이어/객체를 찾아(viewer.search) 그 위에 점을 찍는다 (public/script.js).
  let diagram = null;
  if (dxfData) {
    diagram = { type: "svg", svg: renderDxfSvg(dxfData, [...ruleFindings, ...aiFindings]) };
  } else if (apsUrn) {
    diagram = {
      type: "viewer",
      urn: apsUrn,
      findings: [...ruleFindings, ...aiFindings],
      note: "레이어/객체명이 일치하는 위치에 마커를 표시합니다 — 일치하는 요소가 없으면 표시되지 않을 수 있습니다.",
    };
  } else if (imageBytes) {
    diagram = { type: "raster", base64: bytesToBase64(imageBytes) };
  }

  return json({ rule_findings: ruleFindings, ai_findings: aiFindings, ai_error: aiError, diagram });
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/analyze" && request.method === "POST") {
      return handleAnalyze(request, env);
    }
    if (url.pathname === "/aps-token" && request.method === "GET") {
      try {
        return json(await getViewerToken(env));
      } catch (e) {
        return json({ detail: e.message }, 400);
      }
    }
    return new Response("Not found", { status: 404 });
  },
};
