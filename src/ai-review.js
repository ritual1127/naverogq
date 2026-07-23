// AI review via Cloudflare Workers AI (not Gemini) — calling Google's
// Generative Language API from a Cloudflare Worker hits Google's regional
// block on Cloudflare's egress IPs, so this stays entirely on Cloudflare's
// own infrastructure instead.

const MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

// 사람이 도면 검도할 때 보는 항목을 12개 버킷으로 묶었다 — 실제 화면 라벨은
// public/script.js·src/render.js의 CATEGORY_LABEL과 반드시 맞춰야 한다.
const CATEGORIES = [
  "missing_dimension", // 치수 누락
  "extra_dimension", // 중복/과잉 치수
  "missing_tolerance", // 공차 누락
  "dimension_placement", // 치수 위치/치수선·보조선 오류
  "centerline_error", // 중심선 오류/누락
  "hidden_line_error", // 숨은선 오류
  "projection_error", // 투상도 오류/정렬 불량/실형상 불일치
  "line_type_error", // 선종류/선굵기 오류
  "symmetry_error", // 대칭 오류
  "geometry_mismatch", // 형상 불일치/접선 오류/원호 정렬/간섭선/끊어진 선/불필요한 선
  "titleblock_error", // 표제란 오류
  "standard_violation", // 그 외 KS/ISO 위반
];

const FINDING_SCHEMA = {
  type: "object",
  properties: {
    findings: {
      type: "array",
      items: {
        type: "object",
        properties: {
          category: { type: "string", enum: CATEGORIES },
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

const CHECKLIST = `- 투상도 오류 / 정렬 불량 / 실제 형상과 투상도 불일치 → projection_error
- 중심선 오류(누락·위치 오류) → centerline_error
- 숨은선 오류(누락·잘못된 표현) → hidden_line_error
- 치수 누락 → missing_dimension
- 중복 치수 / 과잉 치수 → extra_dimension
- 치수 위치 오류 / 치수선·보조선 오류 → dimension_placement
- 공차 누락 → missing_tolerance
- 선종류 오류 / 선굵기 오류 → line_type_error
- 대칭 오류 → symmetry_error
- 원·호·축 정렬 오류 / 접선 오류 / 간섭되는 선 / 끊어진 선 / 불필요한 선 / 형상 불일치 → geometry_mismatch
- 표제란 오류 → titleblock_error
- 그 외 KS/ISO 제도 규격 위반 → standard_violation`;

function buildPrompt(summaryText, ksReference) {
  return (
    "당신은 기계제도(CAD) 도면 검도 전문가입니다. 다음은 CAD 도면에서 추출한 데이터입니다 " +
    "(이미지는 없고, 아래 텍스트/구조화 데이터가 도면에 대해 아는 전부입니다):\n" +
    `${summaryText}\n\n` +
    "참고할 KS 표준 규칙 요약:\n" +
    `${ksReference}\n\n` +
    "아래 체크리스트의 각 항목을 하나씩 확인하고, 데이터에서 근거를 찾을 수 있는 문제를 모두 " +
    "findings 배열로 답하세요. 한 번 훑고 끝내지 말고, 놓친 게 없는지 스스로 다시 한번 " +
    "점검하는 태도로 신중하게 판단하세요:\n" +
    `${CHECKLIST}\n\n` +
    "규칙:\n" +
    "- category는 반드시 위 체크리스트에서 매핑된 영문 값 중 하나를 쓰세요.\n" +
    "- 확실한 근거가 있으면 severity를 medium/high로, 데이터만으로 단정하기 어려운 " +
    "'의심되는 오류'는 severity를 low로 하고 description 맨 앞에 '(의심되는 오류) '를 붙이세요.\n" +
    "- location_hint는 위 데이터의 layers 배열에 있는 값 중 정확히 하나만 그대로 복사해서 쓰세요 " +
    "('레이어 0'처럼 접두어를 붙이거나 '0, 2, MOT'처럼 여러 개를 나열하지 마세요 — " +
    "여러 레이어에 해당하면 finding을 레이어別로 각각 따로 만드세요). " +
    "'오른쪽 상단' 같은 화면상 위치는 이미지 없이는 알 수 없으니 지어내지 마세요. " +
    "해당하는 레이어를 특정할 수 없으면 location_hint를 빈 문자열로 두세요.\n" +
    "- 데이터에 근거가 전혀 없는 항목은 억지로 만들어내지 말고 findings에서 제외하세요."
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
