// AI review via Cloudflare Workers AI (not Gemini) — calling Google's
// Generative Language API from a Cloudflare Worker hits Google's regional
// block on Cloudflare's egress IPs, so this stays entirely on Cloudflare's
// own infrastructure instead.

const MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

const FINDING_SCHEMA = {
  type: "object",
  properties: {
    findings: {
      type: "array",
      items: {
        type: "object",
        properties: {
          category: {
            type: "string",
            enum: ["missing_dimension", "missing_tolerance", "standard_violation"],
          },
          description: { type: "string" },
          severity: { type: "string", enum: ["low", "medium", "high"] },
          location_hint: { type: "string" },
        },
        required: ["category", "description", "severity"],
      },
    },
  },
  required: ["findings"],
};

function buildPrompt(summaryText, ksReference) {
  return (
    "다음은 CAD 도면에서 추출한 데이터입니다:\n" +
    `${summaryText}\n\n` +
    "참고할 KS 표준 규칙 요약:\n" +
    `${ksReference}\n\n` +
    "이 도면에서 누락된 치수(missing_dimension), 누락된 공차 표기(missing_tolerance), " +
    "KS 표준 위반(standard_violation)을 찾아 findings 배열로 답하세요. " +
    "확실하지 않으면 severity를 low로 표시하세요."
  );
}

export class AIConfigError extends Error {}

export async function reviewDrawing(env, summaryText, _imageBytes, ksReference) {
  // ponytail: image (APS thumbnail) not sent — Workers AI JSON-schema mode
  // isn't reliably supported on the vision models yet, so DWG/IPT/IAM/IDW
  // review runs text-only (manifest status). Upgrade to a vision model once
  // structured output on it is solid.
  if (!env.AI) {
    throw new AIConfigError("AI 바인딩이 설정되지 않았습니다 (wrangler.toml의 [ai] 확인 필요).");
  }

  const result = await env.AI.run(MODEL, {
    messages: [{ role: "user", content: buildPrompt(summaryText, ksReference) }],
    response_format: { type: "json_schema", json_schema: FINDING_SCHEMA },
  });

  let parsed = result?.response;
  if (typeof parsed === "string") parsed = JSON.parse(parsed);
  const findings = parsed?.findings ?? [];
  for (const f of findings) f.source = "ai";
  return findings;
}
