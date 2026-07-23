# Brand Guidelines v1.0 — CADSCAN

> Last updated: 2026-07-23
> Status: Draft

## Quick Reference

| Element | Value |
|---------|-------|
| Primary Color | #00F0FF |
| Secondary Color | #A855F7 |
| Primary Font | Segoe UI (system stack) |
| Voice | 기술적, 간결, 신뢰감 (Korean-first, engineer audience) |

---

## 1. Color Palette

### Primary Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Neon Cyan | #00F0FF | rgb(0,240,255) | Logo, glow accents, primary gradient stop, links |
| Cyan Dark | #00A8B8 | rgb(0,168,184) | Hover/pressed states |

### Secondary Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Electric Purple | #A855F7 | rgb(168,85,247) | Logo gradient, AI-section marker, secondary glow |
| Purple Dark | #7C3AED | rgb(124,58,237) | Hover/pressed states |

### Accent Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Signal Green | #3DDC97 | rgb(61,220,151) | Success / low-severity / "ok" state |

### Neutral Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Background | #06070D | rgb(6,7,13) | Page background (deep space black) |
| Panel | rgba(20,24,38,0.6) | — | Glassmorphic card/section background |
| Text Primary | #EEF1F8 | rgb(238,241,248) | Headings, body text |
| Text Secondary | #8B93A7 | rgb(139,147,167) | Captions, muted text, subtitles |
| Border/Glow | rgba(0,240,255,0.18) | — | Panel borders, dividers |

### Semantic Colors

| State | Hex | Usage |
|-------|-----|-------|
| Success (low) | #3DDC97 | Low-severity findings, "완료" status |
| Warning (medium) | #FFB454 | Medium-severity findings |
| Error (high) | #FF5470 | High-severity findings, error text |
| Info | #00F0FF | Informational tags, active-step indicator |

### Accessibility

- Text Primary (#EEF1F8) on Background (#06070D): >13:1 contrast (AAA)
- Neon Cyan (#00F0FF) on Background: >12:1 contrast (AAA) — safe for small text and icons
- Never place body text directly on the raw gradient (cyan→purple); gradient is for accents/headlines only

---

## 2. Typography

### Font Stack

```css
--font-heading: 'Segoe UI', system-ui, -apple-system, sans-serif;
--font-body: 'Segoe UI', system-ui, -apple-system, sans-serif;
--font-mono: 'Consolas', 'SFMono-Regular', monospace;
```

No external web fonts — system stack only, so the site has zero font-loading dependency.

### Type Scale

| Element | Size (Desktop) | Size (Mobile) | Weight | Line Height |
|---------|----------------|----------------|--------|-------------|
| H1 | clamp(1.6rem, 4vw, 2.4rem) | 1.6rem | 700 | 1.3 |
| H2 (section) | 1.05rem | 1rem | 700 | 1.4 |
| Body | 1rem | 0.95rem | 400 | 1.6 |
| Subtitle | 1rem | 0.9rem | 400 | 1.6 |
| Caption/tag | 0.7–0.78rem | 0.7rem | 400–700 | 1.4 |

---

## 3. Logo Usage

### Variants

| Variant | File | Use Case |
|---------|------|----------|
| Icon (hexagon + caliper mark) | `public/favicon.svg` | Favicon, header lockup, small spaces |
| Wordmark | inline `CAD<em>SCAN</em>` span (CSS gradient text) | Header, alongside icon |

The mark is a hexagon outline (cyan→purple gradient stroke) framing a caliper/measurement glyph with a single glowing node at center — reads as "CAD file being measured/scanned."

### Clear Space

Minimum clear space = width of the hexagon icon on all sides.

### Minimum Size

| Context | Minimum Width |
|---------|----------------|
| Digital — icon | 24px |
| Favicon | 16px (SVG scales cleanly) |

### Don'ts

- Don't recolor the mark outside the cyan→purple gradient
- Don't drop the gradient in favor of a flat fill
- Don't stretch — keep the hexagon's aspect ratio 1:1
- Don't place on light backgrounds without inverting the panel behind it

---

## 4. Voice & Tone

### Brand Personality

| Trait | Description |
|-------|-------------|
| **Precise** | Speaks in exact engineering terms (치수, 공차, KS 표준) — no vague marketing language |
| **Direct** | Short sentences, states findings and severity plainly |
| **Technical-confident** | Assumes a CAD/설계 audience; doesn't over-explain basics |
| **Transparent** | Always shows what stage of analysis is running, never a silent black box |

### Tone by Context

| Context | Tone | Example |
|---------|------|---------|
| UI copy | 간결한 지시형 | "파일을 선택하세요", "분석하기" |
| Progress/status | 현재 진행 중인 작업을 있는 그대로 | "AI 모델 분석 중...", "분석 완료" |
| Errors | 원인을 정확히, 과장 없이 | "GOOGLE_API_KEY 환경변수가 없어 AI 검토를 건너뜁니다." |
| Findings | 표준 근거를 함께 제시 | "KS B 0412 공차 표기 기준 확인 필요" |

### Prohibited Terms

| Avoid | Reason |
|-------|--------|
| 혁신적인 | 과장된 마케팅 표현, 이 툴은 실무 도구 |
| 완벽하게 | AI 검토는 후보 제시일 뿐, 확정 판정처럼 말하지 않음 |
| 강력한 AI | 모호한 과장, 실제 모델명을 밝히는 게 신뢰감 있음 |

---

## 5. Design Components

### Buttons

| Type | Background | Text | Border Radius |
|------|------------|------|----------------|
| Primary | linear-gradient(90deg, #00F0FF, #A855F7) | #06070D | 8px |
| Secondary | transparent | #00F0FF | 8px |

### Spacing Scale

| Token | Value |
|-------|-------|
| xs | 4px |
| sm | 8px |
| md | 16px |
| lg | 24px |
| xl | 32px |

### Border Radius

| Element | Radius |
|---------|--------|
| Buttons | 8px |
| Panels/cards | 8–12px |
| Pills/tags | 999px |

---

## AI Image Generation

### Base Prompt Template

```
Dark futuristic HUD interface for a CAD/engineering drawing-analysis tool, deep space-black background (#06070D), glowing neon cyan (#00F0FF) to electric purple (#A855F7) gradient accents, glassmorphic translucent panels, faint animated circuit/grid lines, precise technical-blueprint mood, no clutter, no human figures.
```

### Style Keywords

| Category | Keywords |
|----------|----------|
| **Lighting** | neon glow, backlit edges, soft bloom |
| **Mood** | precise, technical, futuristic, quiet-confident |
| **Composition** | centered, minimal, generous negative space |
| **Treatment** | glassmorphism, subtle grid, high contrast on dark |
| **Aesthetic** | HUD / sci-fi CAD interface, blueprint-inspired |

### Visual Mood Descriptors

- Feels like a scanning/measurement instrument, not a marketing landing page
- Calm dark background so neon accents read as signal, not noise
- Every glow has a purpose (active state, severity, brand mark) — never decorative-only

### Visual Don'ts

| Avoid | Reason |
|-------|--------|
| Bright white backgrounds | Breaks the dark futuristic identity |
| Stock-photo people/office imagery | Wrong audience register, this is a technical tool |
| Rainbow/multi-hue gradients | Dilutes the two-color cyan/purple identity |

### Example Prompts

**Hero Banner:**
```
Dark futuristic HUD interface for a CAD drawing-error scanner, deep black background, cyan-to-purple neon gradient hexagon logo with a caliper glyph glowing at center, thin animated grid lines receding into the background, glassmorphic card in the foreground showing a scan-line progress bar, precise and technical mood, no text, no people.
```

**Status/Progress Illustration:**
```
Minimal dark UI illustration of a scanning progress bar mid-animation, cyan-to-purple gradient scan line moving across a thin track, four step indicators with glowing dots (one pulsing cyan, others dim), glassmorphic panel background, precise technical aesthetic.
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-23 | Initial guidelines, extracted from the deployed CADSCAN site (public/style.css, public/index.html) |
