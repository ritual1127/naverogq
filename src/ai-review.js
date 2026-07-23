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
    "다음은 CAD 도면에서 추출한 데이터입니다 (이미지는 없고, 아래 텍스트/구조화 데이터가 전부입니다):\n" +
    `${summaryText}\n\n` +
    "참고할 KS 표준 규칙 요약:\n" +
    `${ksReference}\n\n` +
    "이 도면에서 누락된 치수(missing_dimension), 누락된 공차 표기(missing_tolerance), " +
    "KS 표준 위반(standard_violation)을 찾아 findings 배열로 답하세요. " +
    "확실하지 않으면 severity를 low로 표시하세요. " +
    "location_hint는 위 데이터의 layers 배열에 있는 값 중 정확히 하나만 그대로 복사해서 쓰세요 " +
    "('레이어 0'처럼 접두어를 붙이거나 '0, 2, MOT'처럼 여러 개를 나열하지 마세요 — " +
    "여러 레이어에 해당하면 finding을 레이어別로 각각 따로 만드세요). " +
    "'오른쪽 상단' 같은 화면상 위치는 이미지 없이는 알 수 없으니 지어내지 마세요. " +
    "해당하는 레이어를 특정할 수 없으면 location_hint를 빈 문자열로 두세요."
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
