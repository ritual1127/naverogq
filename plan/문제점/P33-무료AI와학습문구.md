# P33 · 정책은 "도면이 AI 학습에 쓰이지 않는다"고 하는데, 공개 서버가 쓰는 Gemini 무료 등급은 "제품 개선에 쓴다"고 적혀 있다

| | |
|---|---|
| 상태 | 🔴 **열림** — 원인은 확인했다(10-16, 공개 서버 키는 무료 등급). 문구는 아직 그대로 |
| 처음 본 날 | 2026-10-12 |
| 무엇에 영향을 주나 | 보호자 · 선생님께 한 약속([`docs/policy.md`](../../docs/policy.md)) · 윤리 · 안전 심사(통과/탈락) · 미성년 사용자가 올린 도면 그림 |
| 맡은 사람 | 박지완 |
| 목록 | [문제점 전체](README.md) |

## 증상

10-12 에 W8 KPI 리포트의 유료 단가를 채우려고 [Gemini API 가격표](https://ai.google.dev/gemini-api/docs/pricing) 원문을 읽었다.
공개 서버의 1순위 채점기 `gemini-3.1-flash-lite` 칸에 **"Used to improve our products — Free Tier: Yes · Paid Tier: No"** 가 있다.

우리 문서는 이렇게 적고 있다.

| 문서 | 적은 것 |
|---|---|
| [`docs/policy.md`](../../docs/policy.md) 「올린 도면」 표 | AI 학습에 쓰나 — **안 씁니다.** 사용자 도면으로 어떤 AI도 학습시키지 않습니다 |
| [`docs/policy.md`](../../docs/policy.md) 「보호자와 선생님께」 | 학생이 올린 도면은 서버에 최대 1시간 있다가 지워지고, **AI 학습에 쓰이지 않습니다** |
| [`docs/ai_checklist.md`](../../docs/ai_checklist.md) 5번 | 사용자 도면을 AI 학습에 쓰나 — ✅ 안 씀 |

같은 정책 문서의 「밖으로 나가는 것」 문단은 도면 그림을 Gemini 에 보낸다는 것과 "보낸 뒤로는 Google 의 개인정보처리방침과 Gemini 약관을
따른다"는 것을 적고 있다. 그런데 보호자 · 선생님께 하는 문장은 "쓰이지 않는다"로 끝난다.

공개 서버의 AI 채점은 "전부 무료 한도"라고 적어 왔다(README "AI 채점기를 두 곳으로 붙여 둔 이유" · [W8 KPI 리포트](../w8/W8_KPI리포트.md) ⑤).

## 원인

**공개 서버(Render)에 넣은 Gemini 키는 결제가 붙지 않은 무료 등급이다** — 10-16 저녁에 박지완이 그렇다고 말했다.
그래서 우리 문서의 "쓰이지 않는다"는 **우리가** 학습시키지 않는다는 데서 그친 문장이었다. Google 쪽이 보낸 그림을 어떻게 쓰는지는 따지지 않고 썼다.

10-16 19:11 에 [Gemini API 추가 약관](https://ai.google.dev/gemini-api/terms) 원문을 읽었다(페이지 "Last updated 2026-04-28 UTC"). 무료 등급(Unpaid Services)에 대해 —

> When you use Unpaid Services, including, for example, Google AI Studio and the unpaid quota on Gemini API, Google uses the content you submit
> to the Services and any generated responses to provide, improve, and develop Google products and services and machine learning technologies […]
> To help with quality and improve our products, human reviewers may read, annotate, and process your API input and output. […]
> Do not submit sensitive, confidential, or personal information to the Unpaid Services.

| 무료 등급에서 일어나는 일 | 우리 서버에서는 |
|---|---|
| 보낸 내용과 답으로 Google 이 제품과 기계학습 기술을 만들고 고친다 | 투상도 30점을 채점할 때 보내는 **도면 그림 1장**과 요약 글이 여기에 든다 |
| 사람 검토자가 입력과 출력을 읽고 표시를 단다(계정 · API 키와 떼어 낸 뒤) | 표제란에 이름이 적힌 도면이면 그 이름이 그림에 찍혀 간다([정책](../../docs/policy.md) 「도면 안에 들어 있는 개인정보」) |
| 민감 · 기밀 · 개인 정보를 보내지 말라 | 이름을 지우고 올리라고 안내만 하고, 서버가 지우지는 않는다 |

결제가 붙은 등급(Paid Services)은 같은 약관에서 "Google doesn't use your prompts […] or responses to improve our products" 라고 한다 —
그쪽이었다면 우리 문장이 맞았다. **원인은 무료 등급을 쓰면서 결제 등급을 전제로 한 문장을 쓴 것**이다.

같은 약관을 읽다 나이 조항을 따로 찾았다 — 그건 무료 · 유료와 상관없는 다른 문제라 [P35](P35-제미나이18세조항.md)로 적었다.

## 조치

아직 없다. 공개 서버 키의 등급은 무료 등급이다(10-16 · 박지완이 말함). 셋 중 하나를 고른다 —
문구를 사실대로 고친다 / 결제가 붙은 키로 바꾼다 / 1순위 채점기를 바꾼다.

**10-16 — 박지완이 "문구를 사실대로 고친다"로 정했다.** 채점기는 바꾸지 않는다. 코드 동결 날이라 투상도 30점을 재 보지 않은 채점기로
바꾸는 것보다, 지금 쓰는 채점기가 하는 일을 그대로 적는 쪽을 골랐다. 앱 화면 12곳은 오늘 마지막 배포에 싣는다.

## 확인

아직 없다.

## 기록

| 날짜 | 무엇 |
|---|---|
| 2026-10-12 | KPI 리포트 유료 단가를 채우다 가격표 원문에서 찾음. 기록만 하고 문구 · 설정은 안 건드림 |
| 2026-10-15 | 앱 화면에도 "도면을 AI 학습에 쓰지 않는다"는 문장이 있다 — [`static/common.js`](../../static/common.js) 의 저작권 · 미성년자 안전 · 자주 묻는 질문 세 곳, 네 언어 모두(한국어 · 영어 · 일본어 · 중국어 3곳씩, 12곳). 위 증상 표에는 문서만 있었다. 이 파일은 이미지에 들어가서 **10-16 저녁 코드 동결 뒤에는 못 고친다** — 문구를 고치는 쪽으로 정하면 10-16 마지막 배포가 마지막이다. `docs/` 쪽은 동결 뒤에도 고칠 수 있다. 공개 서버 키 등급은 아직 확인 전이라 문구 · 설정은 안 건드렸다 |
| 2026-10-16 | **원인 확인** — 박지완이 공개 서버 키가 무료 등급이라고 말했다. 19:11 Gemini API 추가 약관 원문(2026-04-28 갱신)을 읽어 무료 등급의 데이터 쓰임 세 줄(제품 · 기계학습 개선, 사람 검토자, 개인정보를 보내지 말 것)을 원인 칸에 옮겼다. 박지완이 "문구를 사실대로"로 정함. 같은 약관에서 나이 조항을 찾아 [P35](P35-제미나이18세조항.md)로 따로 적음 |
