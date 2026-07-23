import { useState, useRef } from "react";
import { ScanLine, ChevronRight, Upload, AlertTriangle, CheckCircle, Info, Layers, ShieldCheck, BarChart2, X, ArrowRight } from "lucide-react";

const FEATURES = [
  { icon: ScanLine, title: "실시간 형상 분석", desc: "STEP, IGES, DXF 등 주요 포맷을 업로드 즉시 분석하여 치수 오류와 면 결함을 자동 검출합니다." },
  { icon: ShieldCheck, title: "KS / ISO 규격 검증", desc: "국내외 표준 규격 라이브러리와 자동 대조하여 볼트·공차·재료 규격 준수 여부를 확인합니다." },
  { icon: Layers, title: "어셈블리 간섭 검사", desc: "다중 부품 어셈블리를 3D 공간에서 교차 분석하여 충돌 및 클리어런스 부족 구간을 표시합니다." },
  { icon: BarChart2, title: "품질 리포트 생성", desc: "검출 결과를 PDF/Excel로 즉시 출력하고 오류 이력을 대시보드에서 추적할 수 있습니다." },
];

type Issue = {
  id: string;
  level: "critical" | "warning" | "info";
  title: string;
  desc: string;
  fix: string;
  image: string;
};

const MOCK_ISSUES: Issue[] = [
  {
    id: "E-4471",
    level: "critical",
    title: "치수 오류 — 홀 직경 허용 오차 초과",
    desc: "bracket_v3.STEP의 228번 요소에서 홀 직경이 설계 기준(12.00mm)보다 0.8mm 초과 가공되었습니다. 이 수준의 오차는 볼트 체결 시 유격이 발생하여 구조적 결함으로 이어질 수 있습니다.",
    fix: "홀 직경을 Ø12.00 ±0.05mm 이내로 재가공하거나, 부시(bush)를 삽입하여 내경을 보정하십시오. 가공 후 게이지 측정을 통해 공차를 재확인하세요.",
    image: "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=600&h=340&fit=crop&auto=format",
  },
  {
    id: "E-4472",
    level: "critical",
    title: "어셈블리 간섭 — 부품 A · C 충돌 감지",
    desc: "assembly_rev2.IGES에서 부품 A와 부품 C가 0.3mm 겹치는 간섭 영역이 발견되었습니다. 조립 시 물리적 충돌이 발생하여 파손 위험이 있습니다.",
    fix: "부품 C의 위치를 Z축 방향으로 0.5mm 이상 이동하거나, 간섭 구간의 형상을 절삭하여 클리어런스를 최소 0.2mm 이상 확보하십시오.",
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&h=340&fit=crop&auto=format",
  },
  {
    id: "W-1193",
    level: "warning",
    title: "벽 두께 경고 — 최소 기준 미달",
    desc: "housing_final.STEP의 측면 쉘 구간 벽 두께가 0.8mm로 측정되었습니다. 사용 재질(ABS) 기준 최소 벽 두께 1.2mm에 미달하여 사출 성형 시 싱크마크·변형이 발생할 수 있습니다.",
    fix: "해당 구간의 벽 두께를 1.2mm 이상으로 수정하십시오. 설계상 어려울 경우 재질을 PC 또는 PA66으로 변경하면 0.9mm까지 허용 가능합니다.",
    image: "https://images.unsplash.com/photo-1565372195458-9de0b320ef04?w=600&h=340&fit=crop&auto=format",
  },
];

function LevelBadge({ level }: { level: Issue["level"] }) {
  if (level === "critical")
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
        <AlertTriangle className="w-3 h-3" /> 오류
      </span>
    );
  if (level === "warning")
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
        <AlertTriangle className="w-3 h-3" /> 경고
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
      <Info className="w-3 h-3" /> 정보
    </span>
  );
}

type Stage = "idle" | "upload" | "analyzing" | "done";

export default function App() {
  const [stage, setStage] = useState<Stage>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFileName(f.name);
    setStage("analyzing");
    setProgress(0);

    let p = 0;
    const interval = setInterval(() => {
      p += Math.random() * 18 + 5;
      if (p >= 100) {
        p = 100;
        clearInterval(interval);
        setTimeout(() => {
          setStage("done");
          setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
        }, 400);
      }
      setProgress(Math.min(p, 100));
    }, 180);
  }

  function reset() {
    setStage("idle");
    setFileName(null);
    setProgress(0);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <div className="min-h-screen bg-background text-foreground" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* NAV */}
      <nav className="border-b border-border sticky top-0 bg-white/90 backdrop-blur-sm z-40">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ScanLine className="w-4 h-4 text-accent" strokeWidth={2} />
            <span className="font-semibold text-sm">CADInspect</span>
          </div>
          <div className="hidden md:flex items-center gap-7">
            {["기능", "사용 방법", "요금제"].map((t) => (
              <a key={t} href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">{t}</a>
            ))}
          </div>
          <button className="text-sm font-medium bg-foreground text-background px-4 py-1.5 rounded-md hover:opacity-80 transition-opacity">
            무료 체험
          </button>
        </div>
      </nav>

      {/* HERO */}
      <section className="max-w-5xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-1.5 text-xs font-medium text-accent border border-blue-200 bg-blue-50 px-3 py-1 rounded-full mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-accent" />
          AI 기반 자동 검출 엔진
        </div>
        <h1 className="text-4xl md:text-5xl font-bold leading-tight tracking-tight mb-4">
          CAD 설계 오류,<br />출하 전에 잡습니다
        </h1>
        <p className="text-base text-muted-foreground leading-relaxed mb-10 max-w-md mx-auto">
          파일을 올리면 2초 안에 치수 오류, 간섭, 규격 위반을 검출합니다.
          제조 전 품질 비용을 평균 <span className="text-foreground font-medium">87% 절감</span>한 도구입니다.
        </p>

        {/* CTA */}
        {stage === "idle" && (
          <button
            onClick={() => setStage("upload")}
            className="inline-flex items-center gap-2 bg-foreground text-background text-sm font-medium px-6 py-3 rounded-md hover:opacity-80 transition-opacity"
          >
            파일 분석 시작 <ChevronRight className="w-4 h-4" />
          </button>
        )}

        {/* UPLOAD ZONE */}
        {stage === "upload" && (
          <div className="mt-2 max-w-lg mx-auto">
            <input ref={fileRef} type="file" className="hidden" accept=".step,.iges,.igs,.dxf,.dwg,.stp" onChange={handleFileChange} />
            <button
              onClick={() => fileRef.current?.click()}
              className="w-full border-2 border-dashed border-border rounded-xl px-8 py-14 flex flex-col items-center gap-3 hover:border-accent/40 hover:bg-blue-50/40 transition-all group"
            >
              <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                <Upload className="w-5 h-5 text-muted-foreground group-hover:text-accent transition-colors" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">파일을 클릭하여 업로드</p>
                <p className="text-xs text-muted-foreground mt-1">STEP · IGES · DXF · DWG 지원 · 최대 500MB</p>
              </div>
            </button>
            <button onClick={reset} className="mt-3 text-xs text-muted-foreground hover:text-foreground transition-colors">
              취소
            </button>
          </div>
        )}

        {/* ANALYZING */}
        {stage === "analyzing" && (
          <div className="mt-2 max-w-lg mx-auto">
            <div className="border border-border rounded-xl px-8 py-10 flex flex-col items-center gap-4">
              <div className="w-10 h-10 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-foreground mb-0.5">분석 중...</p>
                <p className="text-xs text-muted-foreground font-mono">{fileName}</p>
              </div>
              <div className="w-full">
                <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
                  <span>형상 · 치수 · 규격 검사</span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full transition-all duration-200"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* ANALYSIS RESULTS */}
      {stage === "done" && (
        <section ref={resultsRef} className="border-t border-border bg-card">
          <div className="max-w-5xl mx-auto px-6 py-16">

            {/* Summary header */}
            <div className="flex items-start justify-between mb-10 gap-4 flex-wrap">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle className="w-4 h-4 text-emerald-500" />
                  <span className="text-sm text-muted-foreground font-mono">{fileName}</span>
                </div>
                <h2 className="text-2xl font-bold">분석 완료 — 3건 발견</h2>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex gap-4 text-sm">
                  <span className="text-red-600 font-medium">오류 2</span>
                  <span className="text-amber-600 font-medium">경고 1</span>
                </div>
                <button
                  onClick={reset}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground border border-border px-3 py-1.5 rounded-md hover:border-foreground/30 transition-colors"
                >
                  <X className="w-3.5 h-3.5" /> 새 파일 분석
                </button>
              </div>
            </div>

            {/* Issue cards */}
            <div className="flex flex-col gap-8">
              {MOCK_ISSUES.map((issue, i) => (
                <div key={issue.id} className="border border-border rounded-xl overflow-hidden bg-white">
                  {/* Image */}
                  <div className="relative h-52 bg-muted overflow-hidden">
                    <img
                      src={issue.image}
                      alt={issue.title}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
                    <div className="absolute bottom-4 left-5 flex items-center gap-2">
                      <LevelBadge level={issue.level} />
                      <span className="text-xs text-white/80 font-mono">{issue.id}</span>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="px-6 py-5 grid md:grid-cols-2 gap-6">
                    <div>
                      <h3 className="font-semibold text-sm mb-2">{issue.title}</h3>
                      <p className="text-sm text-muted-foreground leading-relaxed">{issue.desc}</p>
                    </div>
                    <div className="border-l border-border pl-6">
                      <div className="flex items-center gap-1.5 mb-2">
                        <ArrowRight className="w-3.5 h-3.5 text-accent" />
                        <span className="text-xs font-semibold text-accent uppercase tracking-wide">수정 방법</span>
                      </div>
                      <p className="text-sm text-muted-foreground leading-relaxed">{issue.fix}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Export */}
            <div className="mt-10 flex items-center justify-between border border-border rounded-xl px-6 py-5 bg-white">
              <div>
                <p className="text-sm font-medium">전체 리포트 내보내기</p>
                <p className="text-xs text-muted-foreground mt-0.5">3건의 결과를 PDF 또는 Excel로 저장합니다.</p>
              </div>
              <div className="flex gap-2">
                <button className="text-sm font-medium border border-border px-4 py-2 rounded-md hover:bg-muted transition-colors">Excel</button>
                <button className="text-sm font-medium bg-foreground text-background px-4 py-2 rounded-md hover:opacity-80 transition-opacity">PDF 저장</button>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* STATS */}
      <section className="border-y border-border">
        <div className="max-w-5xl mx-auto px-6 py-12 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { value: "99.7%", label: "오류 검출률" },
            { value: "< 2초", label: "평균 분석 시간" },
            { value: "40+", label: "지원 파일 포맷" },
            { value: "12,000+", label: "사용 엔지니어" },
          ].map((s) => (
            <div key={s.label}>
              <p className="text-2xl font-bold mb-1">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="text-2xl font-bold mb-10">주요 기능</h2>
        <div className="grid md:grid-cols-2 gap-5">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="border border-border rounded-xl p-6 hover:border-accent/30 transition-colors">
                <Icon className="w-4.5 h-4.5 text-accent mb-4" strokeWidth={1.5} />
                <h3 className="font-semibold text-sm mb-2">{f.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border">
        <div className="max-w-5xl mx-auto px-6 py-20 text-center">
          <h2 className="text-2xl font-bold mb-3">지금 바로 무료로 시작하세요</h2>
          <p className="text-sm text-muted-foreground mb-8">신용카드 불필요. CAD 파일 5개까지 무료 검사.</p>
          <button
            onClick={() => { setStage("upload"); window.scrollTo({ top: 0, behavior: "smooth" }); }}
            className="inline-flex items-center gap-1.5 bg-foreground text-background text-sm font-medium px-6 py-2.5 rounded-md hover:opacity-80 transition-opacity"
          >
            무료 체험 시작 <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-border">
        <div className="max-w-5xl mx-auto px-6 py-8 flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ScanLine className="w-4 h-4 text-accent" />
            <span className="text-sm font-semibold">CADInspect</span>
          </div>
          <p className="text-xs text-muted-foreground">© 2026 CADInspect. All rights reserved.</p>
          <div className="flex gap-5">
            {["개인정보처리방침", "이용약관", "문의"].map((t) => (
              <a key={t} href="#" className="text-xs text-muted-foreground hover:text-foreground transition-colors">{t}</a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}