# 발표 도우미 (슬라이드 + 대본) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. 사용자가 "실행해"로 실행 방식을 이미 정했다 — 이 세션에서 직접(네이티브) 구현한다.

**Goal:** 데모데이 ② 5분 발표용 슬라이드와 대본을 한 사이트(탭)에 두고, 여러 컴퓨터가 같은 장을 자동으로 따라가게 한다.

**Architecture:** 빌드 없는 정적 페이지(`presenter/`)를 Vercel 에 올린다. 장 넘기기 · 순번 판정 · 타이머 보정은 `state.js`
(순수 함수)에 두고 node 로 시험한다. 기기 사이는 Supabase Realtime 채널(broadcast + presence)로 상태 전체를 주고받는다.

**Tech Stack:** HTML · CSS · ES modules(브라우저) · `@supabase/supabase-js@2`(CDN ESM) · `node --test` · Vercel CLI 62 · Supabase(무료, 서울)

**Spec:** `docs/superpowers/specs/2026-10-04-presenter-design.md`

## Global Constraints

- 빌드 도구 · npm 의존성 없음. 브라우저는 CDN 에서 supabase-js 만 받는다.
- 방 코드: 소문자·숫자 4~16자 (`/^[a-z0-9]{4,16}$/`), 없으면 6자 생성. 채널 이름 `presenter:<코드>`.
- 상태 `{ slide, startedAt, seq, by }` — `seq` 큰 쪽이 이김, 같으면 `by` 큰 쪽.
- 타이머는 "시작한 지 몇 ms" 로 주고받는다. 전체 기준 300초, 장 목표는 대사 글자 수 ÷ 4.5.
- 키: `→` `Space` `PageDown` 다음 · `←` `PageUp` 이전 · `F` 전체화면 · `T` 탭 전환. 입력칸(select 등)에 초점이 있으면 무시.
- 슬라이드 1920×1080 기준, 핵심 숫자 160px 이상, 어두운 배경.
- 페이지에는 Supabase 공개용(publishable) 키만. 테이블 없음.
- 숫자 · 대사는 `plan/w8/W8_준비.md` 5분 원고와 같다.

## Review Focus

1. **시계가 서로 다른 노트북** — 순번으로 판정하므로 넘기기가 꼬이지 않아야 한다 → Task 1 시험 `clock skew does not matter`.
2. **둘이 거의 동시에 누름** — 모든 기기가 같은 장으로 모여야 한다 → Task 1 시험 `same seq picks larger device id everywhere`.
3. **끝 장에서 → 를 또 누름 / 첫 장에서 ←** — 범위를 넘지 않고, 순번도 오르지 않아 다른 기기를 흔들지 않는다 → Task 1 시험 `edges do not move or bump seq`.
4. **Supabase 를 못 불러옴(CDN 차단 · 프로젝트 멈춤)** — 이 기기만으로 끝까지 발표할 수 있어야 한다 → Task 3 수동 확인(키 이름이 틀린 설정으로 열어 `○ 끊김` 과 넘기기 확인).
5. **대본 내용 오타(읽는 사람 이름이 people 에 없음 · 빈 장)** — 화면이 깨지지 않게 시험에서 미리 잡는다 → Task 2 시험 `talk is well formed`.

---

### Task 1: 상태 계산 (`state.js`)

**Files:** Create `presenter/state.js`, `presenter/state.test.mjs`

**Interfaces — Produces:**
- `initial(by: string) → State` (`{slide:0, startedAt:null, seq:0, by}`)
- `step(state, delta: number, count: number, by: string) → State` — 범위 밖이면 같은 객체를 돌려준다(순번 안 오름)
- `setTimer(state, startedAt: number|null, by) → State`
- `newer(a: State, b: State) → boolean`
- `toWire(state, now) → {slide, seq, by, elapsed: number|null}`
- `receive(state, wire, now) → State` — 더 새로우면 받은 상태(`startedAt = now - elapsed`), 아니면 그대로

- [x] 시험 먼저: 경계 · 순번 · 동률 · 옛 상태 무시 · 타이머 보정 · 시계 차이 (`node --test presenter/*.test.mjs` → 실패 확인)
- [x] 구현 → `node --test presenter/*.test.mjs` 통과

### Task 2: 내용 (`talk.js`)

**Files:** Create `presenter/talk.js`, `presenter/talk.test.mjs`

**Interfaces — Produces:** `TALK = { title, limit, people: string[], slides: [{ title, view, lines: [{who, say}] }] }`,
`view.kind ∈ {"cover","big","flow","ask"}`, `targetSeconds(slide) → number`

- [x] 시험 먼저: 모든 줄의 `who` 가 `people` 에 있음 · 장마다 대사 1줄 이상 · `view.kind` 가 넷 중 하나 · 목표 초 합이 300 이하
- [x] W8_준비.md 5분 원고를 7장으로 옮김 → 통과

### Task 3: 화면 (`index.html`) — 이 기기만으로 완성

**Files:** Create `presenter/index.html`

- [x] 탭 · 슬라이드 4종 렌더 · 1920×1080 맞춤 · 대본(내 줄 강조 · 다음 장 미리보기) · 타이머 · 글자 크기 · 키 · 전체화면 · 잠금 · 이름 고르기(localStorage, try/catch)
- [x] 헤드리스 크롬으로 두 탭 화면을 찍어 눈으로 확인(슬라이드 7장 · 대본 · 좁은 화면)

### Task 4: 동기화 (Supabase)

**Files:** Modify `presenter/index.html`

- [x] Supabase 무료 프로젝트 생성(서울) → URL · publishable 키
- [x] 방 코드 · 채널 구독 · `state`/`hello` broadcast · presence 연결 수 · 끊김 표시 · CDN 실패 시 이 기기만
- [x] node 로 두 기기를 흉내 내 같은 방에서 상태가 오가는지 확인

### Task 5: 배포 · 기록

**Files:** Create `presenter/.gitignore`(`.vercel` · `.env*` — Vercel CLI 가 만듦), `presenter/.vercelignore`(`.env*` · 시험 파일);
Modify `.github/workflows/tests.yml`(node 24 + 시험), `plan/w8/W8_준비.md`(쓰는 법 · 리허설 점검)

- [x] Vercel 프로젝트 `cadlens-presenter` 로 `presenter/` 배포 → 주소가 열리는지 확인
- [x] 배포된 주소를 브라우저 두 탭(같은 방)으로 열어 넘기기 · 잠금 확인
- [x] 커밋 · main 푸시
