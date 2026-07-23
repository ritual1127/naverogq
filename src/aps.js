// Autodesk Platform Services (APS) integration for DWG/IPT/IAM/IDW.
// Native Inventor files can't be parsed without Inventor itself, so we
// upload -> translate -> pull a thumbnail, then let Gemini judge the image.
// Precise dimension extraction needs an Inventor Design Automation
// AppBundle, which is out of scope here (same limitation as the Python version).

import { checkMissingDimensionFromCounts } from "./dxf.js";

const APS_BASE = "https://developer.api.autodesk.com";

export class APSError extends Error {}

async function bodySnippet(resp) {
  const text = await resp.text().catch(() => "");
  return text.slice(0, 300);
}

async function bucketKeyFor(clientId) {
  const data = new TextEncoder().encode(clientId);
  const hash = await crypto.subtle.digest("SHA-1", data);
  const hex = [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return "cad-err-" + hex.slice(0, 16);
}

async function getToken(env, scope = "data:read data:write data:create bucket:create bucket:read") {
  if (!env.APS_CLIENT_ID || !env.APS_CLIENT_SECRET) {
    throw new APSError(
      "APS_CLIENT_ID / APS_CLIENT_SECRET 환경변수가 없습니다. DWG/IPT/IAM/IDW 분석에는 Autodesk Platform Services 앱 자격증명이 필요합니다."
    );
  }
  const resp = await fetch(`${APS_BASE}/authentication/v2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: env.APS_CLIENT_ID,
      client_secret: env.APS_CLIENT_SECRET,
      scope,
    }),
  });
  if (!resp.ok) throw new APSError(`APS 토큰 발급 실패: ${resp.status} ${await bodySnippet(resp)}`);
  const data = await resp.json();
  return data.access_token;
}

async function ensureBucket(token, bucketKey) {
  const headers = { Authorization: `Bearer ${token}` };
  const detail = await fetch(`${APS_BASE}/oss/v2/buckets/${bucketKey}/details`, { headers });
  if (detail.status === 200) return;
  if (detail.status === 403) {
    throw new APSError(`버킷 이름 '${bucketKey}'을(를) 다른 APS 계정이 이미 사용 중입니다.`);
  }
  const create = await fetch(`${APS_BASE}/oss/v2/buckets`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ bucketKey, policyKey: "transient" }),
  });
  if (create.status === 409) return; // already ours
  if (!create.ok) throw new APSError(`버킷 생성 실패: ${create.status} ${await bodySnippet(create)}`);
}

async function uploadFile(token, bucketKey, objectKey, bytes) {
  const headers = { Authorization: `Bearer ${token}` };
  const signResp = await fetch(
    `${APS_BASE}/oss/v2/buckets/${bucketKey}/objects/${objectKey}/signeds3upload`,
    { headers }
  );
  if (!signResp.ok) throw new APSError(`업로드 URL 발급 실패: ${signResp.status} ${await bodySnippet(signResp)}`);
  const { uploadKey, urls } = await signResp.json();

  const putResp = await fetch(urls[0], { method: "PUT", body: bytes });
  if (!putResp.ok) throw new APSError(`파일 업로드 실패: ${putResp.status} ${await bodySnippet(putResp)}`);

  const finalizeResp = await fetch(
    `${APS_BASE}/oss/v2/buckets/${bucketKey}/objects/${objectKey}/signeds3upload`,
    {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ uploadKey }),
    }
  );
  if (!finalizeResp.ok) throw new APSError(`업로드 완료 처리 실패: ${finalizeResp.status} ${await bodySnippet(finalizeResp)}`);
  const { objectId } = await finalizeResp.json();
  return objectId;
}

function base64UrlEncode(str) {
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function translate(token, urn, formats = ["svf2"]) {
  const base64Urn = base64UrlEncode(urn);
  const resp = await fetch(`${APS_BASE}/modelderivative/v2/designdata/job`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      input: { urn: base64Urn },
      output: { formats: formats.map((type) => ({ type, views: ["2d", "3d"] })) },
    }),
  });
  if (!resp.ok) throw new APSError(`변환 작업 시작 실패: ${resp.status} ${await bodySnippet(resp)}`);
  return base64Urn;
}

async function waitForTranslation(token, base64Urn, timeoutS = 180, intervalS = 5) {
  const headers = { Authorization: `Bearer ${token}` };
  let waited = 0;
  while (waited < timeoutS) {
    const resp = await fetch(`${APS_BASE}/modelderivative/v2/designdata/${base64Urn}/manifest`, { headers });
    if (!resp.ok) throw new APSError(`변환 상태 조회 실패: ${resp.status} ${await bodySnippet(resp)}`);
    const manifest = await resp.json();
    if (["success", "failed", "timeout"].includes(manifest.status)) return manifest;
    await new Promise((r) => setTimeout(r, intervalS * 1000));
    waited += intervalS;
  }
  throw new APSError("APS 변환이 제한 시간 안에 끝나지 않았습니다.");
}

async function getThumbnail(token, base64Urn) {
  const headers = { Authorization: `Bearer ${token}` };
  const resp = await fetch(
    `${APS_BASE}/modelderivative/v2/designdata/${base64Urn}/thumbnail?width=400&height=400`,
    { headers }
  );
  return resp.status === 200 ? new Uint8Array(await resp.arrayBuffer()) : null;
}

// Pulls the actual extracted object/layer data out of the translated model
// so the AI has something real to look at instead of just a status string,
// and so we can run the same kind of rule checks DXF gets (see
// checkApsMissingDimension below).
async function getMetadataSummary(token, base64Urn) {
  const headers = { Authorization: `Bearer ${token}` };
  const metaResp = await fetch(`${APS_BASE}/modelderivative/v2/designdata/${base64Urn}/metadata`, { headers });
  if (!metaResp.ok) return null;
  const meta = await metaResp.json();
  const guid = meta?.data?.metadata?.[0]?.guid;
  if (!guid) return null;

  const propsResp = await fetch(
    `${APS_BASE}/modelderivative/v2/designdata/${base64Urn}/metadata/${guid}/properties`,
    { headers }
  );
  if (!propsResp.ok) return null;
  const props = await propsResp.json();
  const objects = props?.data?.collection ?? [];

  const layers = new Set();
  const entityTypeCounts = {};
  for (const obj of objects) {
    const name = obj.name || "";
    const bracketIdx = name.indexOf(" [");
    if (bracketIdx === -1) continue; // skip rollup/group nodes, keep only leaf entities
    const type = name.slice(0, bracketIdx);
    entityTypeCounts[type] = (entityTypeCounts[type] || 0) + 1;
    const layerVal = obj.properties?.General?.Layer;
    if (layerVal) layers.add(layerVal);
  }

  return {
    view_name: meta.data.metadata[0].name,
    object_count: objects.length,
    entity_type_counts: entityTypeCounts,
    layers: [...layers].slice(0, 30),
  };
}

// DXF gets this same check from real coordinate/entity data (see
// checkMissingDimensionFromCounts in dxf.js) — APS only gives us type
// counts, but "geometry exists, zero Dimension entities" is still a real,
// defensible signal rather than an AI guess.
export function checkApsMissingDimension(metadataSummary) {
  if (!metadataSummary) return [];
  const counts = metadataSummary.entity_type_counts;
  const geometryTotal = (counts.Line || 0) + (counts.Circle || 0) + (counts.Arc || 0) + (counts.Polyline || 0);
  return checkMissingDimensionFromCounts(geometryTotal, counts.Dimension || 0);
}

export async function extractViaAps(env, filename, bytes) {
  if (!env.APS_CLIENT_ID) throw new APSError("APS_CLIENT_ID / APS_CLIENT_SECRET 환경변수가 없습니다.");
  const bucketKey = await bucketKeyFor(env.APS_CLIENT_ID);
  const token = await getToken(env);
  await ensureBucket(token, bucketKey);
  const objectKey = filename.replace(/\s/g, "_");
  const urn = await uploadFile(token, bucketKey, objectKey, bytes);
  const base64Urn = await translate(token, urn);
  const manifest = await waitForTranslation(token, base64Urn);
  const thumbnail = await getThumbnail(token, base64Urn);
  const metadataSummary = await getMetadataSummary(token, base64Urn);
  return { manifestStatus: manifest.status, imageBytes: thumbnail, urn: base64Urn, metadataSummary };
}

// Short-lived, read-only token for the APS Viewer running in the browser —
// separate from the upload/translate token above, which stays server-side.
export async function getViewerToken(env) {
  const resp = await fetch(`${APS_BASE}/authentication/v2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: env.APS_CLIENT_ID,
      client_secret: env.APS_CLIENT_SECRET,
      scope: "viewables:read",
    }),
  });
  if (!resp.ok) throw new APSError(`뷰어 토큰 발급 실패: ${resp.status} ${await bodySnippet(resp)}`);
  return resp.json(); // { access_token, expires_in, token_type }
}
