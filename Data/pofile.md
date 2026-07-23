import { useState, useRef } from "react";
import { ScanLine, ChevronRight, Upload, AlertTriangle, CheckCircle, Info, Layers, ShieldCheck, BarChart2, X, ArrowRight, ArrowLeft } from "lucide-react";

const FEATURES = [
  { icon: ScanLine, title: "실시간 형상 분석", desc: "치수 오류와 면 결함을 업로드 즉시 검출합니다." },
  { icon: ShieldCheck, title: "KS / ISO 규격 검증", desc: "국내외 표준 규격과 자동 대조하여 준수 여부를 확인합니다." },
  { icon: Layers, title: "어셈블리 간섭 검사", desc: "3D 공간에서 충돌 및 클리어런스 부족 구간을 표시합니다." },
  { icon: BarChart2, title: "품질 리포트 생성", desc: "결과를 PDF/Excel로 즉시 출력하고 이력을 추적합니다." },
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
    desc: "bracket_v3.STEP의 228번 요소에서 홀 직경이 설계 기준(12.00mm)보다 0.8mm 초과 가공되었습니다. 볼트 체결 시 유격이 발생하여 구조적 결함으로 이어질 수 있습니다.",
    fix: "홀 직경을 Ø12.00 ±0.05mm 이내로 재가공하거나, 부시(bush)를 삽입하여 내경을 보정하십시오. 가공 후 게이지 측정으로 공차를 재확인하세요.",
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
    desc: "housing_final.STEP의 측면 쉘 구간 벽 두께가 0.8mm로 측정되었습니다. ABS 기준 최소 1.2mm에 미달하여 사출 성형 시 변형이 발생할 수 있습니다.",
    fix: "해당 구간의 벽 두께를 1.2mm 이상으로 수정하십시오. PC 또는 PA66으로 재질 변경 시 0.9mm까지 허용 가능합니다.",
    image: "https://images.unsplash.com/photo-1565372195458-9de0b320ef04?w=600&h=340&fit=crop&auto=format",
  },
];

const CAD_PARTS = [
  {
    src: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=320&h=220&fit=crop&auto=format",
    alt: "CAD 기어 부품",
    style: "top-16 left-[-40px] w-56 rotate-[-8deg] opacity-60",
  },
  {
    src: "https://images.unsplash.com/photo-1565372195458-9de0b320ef04?w=280&h=200&fit=crop&auto=format",
    alt: "CAD 하우징 부품",
    style: "bottom-24 left-8 w-48 rotate-[6deg] opacity-50",
  },
  {
    src: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=300&h=210&fit=crop&auto=format",
    alt: "CAD 회로 부품",
    style: "top-20 right-[-30px] w-52 rotate-[7deg] opacity-55",
  },
  {
    src: "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=260&h=180&fit=crop&auto=format",
    alt: "CAD 기계 부품",
    style: "bottom-16 right-4 w-44 rotate-[-5deg] opacity-45",
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

type Page = "home" | "upload" | "result";

function Navbar({ onHome }: { onHome: () => void }) {
  return (
    <nav className="border-b border-border sticky top-0 bg-white/90 backdrop-blur-sm z-40">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <button onClick={onHome} className="flex items-center gap-2">
          <ScanLine className="w-4 h-4 text-accent" strokeWidth={2} />
          <span className="font-semibold text-sm">CADInspect</span>
        </button>
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
  );
}

/* ─── HOME PAGE ─── */
function HomePage({ onStart }: { onStart: () => void }) {
  return (
    <div className="min-h-screen bg-background">
      {/* HERO */}
      <section className="max-w-5xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-1.5 text-xs font-medium text-accent border border-blue-200 bg-blue-50 px-3 py-1 rounded-full mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-accent" />
          AI 기반 자동 검출 엔진
        </div>
        <h1 className="text-4xl md:text-5xl font-bold leading-tight tracking-tight mb-4">
          CAD 설계 오류,<br />출하 전에 잡습니다
        </h1>
        <p className="text-sm text-muted-foreground mb-10 max-w-xs mx-auto">
          파일 하나로 치수·간섭·규격 위반을 2초 안에 검출합니다.
        </p>
        <button
          onClick={onStart}
          className="inline-flex items-center gap-2 bg-foreground text-background text-sm font-medium px-6 py-3 rounded-md hover:opacity-80 transition-opacity"
        >
          파일 분석 시작 <ChevronRight className="w-4 h-4" />
        </button>
      </section>

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
                <Icon className="w-4 h-4 text-accent mb-4" strokeWidth={1.5} />
                <h3 className="font-semibold text-sm mb-1.5">{f.title}</h3>
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
            onClick={onStart}
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

/* ─── UPLOAD PAGE ─── */
function UploadPage({ onBack, onDone }: { onBack: () => void; onDone: (name: string) => void }) {
  const [progress, setProgress] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setAnalyzing(true);
    setProgress(0);
    let p = 0;
    const iv = setInterval(() => {
      p += Math.random() * 18 + 5;
      if (p >= 100) {
        p = 100;
        clearInterval(iv);
        setTimeout(() => onDone(f.name), 400);
      }
      setProgress(Math.min(p, 100));
    }, 180);
  }

  return (
    <div className="min-h-screen bg-background relative overflow-hidden flex flex-col">
      {/* CAD part images in background */}
      {CAD_PARTS.map((p) => (
        <div key={p.alt} className={`absolute pointer-events-none select-none ${p.style}`}>
          <img
            src={p.src}
            alt={p.alt}
            className="w-full h-full object-cover rounded-xl shadow-lg"
          />
          <div className="absolute inset-0 rounded-xl bg-white/30" />
        </div>
      ))}

      {/* Back button */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-8 w-full">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> 돌아가기
        </button>
      </div>

      {/* Center content */}
      <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 py-16">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex w-12 h-12 rounded-full bg-white border border-border shadow-sm items-center justify-center mb-4">
              <ScanLine className="w-5 h-5 text-accent" />
            </div>
            <h2 className="text-2xl font-bold mb-1">CAD 파일 업로드</h2>
            <p className="text-sm text-muted-foreground">STEP · IGES · DXF · DWG 지원</p>
          </div>

          {!analyzing ? (
            <>
              <input
                ref={fileRef}
                type="file"
                className="hidden"
                accept=".step,.stp,.iges,.igs,.dxf,.dwg"
                onChange={handleFile}
              />
              <button
                onClick={() => fileRef.current?.click()}
                className="w-full bg-white border-2 border-dashed border-border rounded-2xl px-8 py-14 flex flex-col items-center gap-3 hover:border-accent/50 hover:bg-blue-50/30 transition-all group shadow-sm"
              >
                <div className="w-11 h-11 rounded-full bg-muted flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                  <Upload className="w-5 h-5 text-muted-foreground group-hover:text-accent transition-colors" />
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium text-foreground">클릭하여 파일 선택</p>
                  <p className="text-xs text-muted-foreground mt-1">최대 500MB</p>
                </div>
              </button>

              <p className="text-center text-xs text-muted-foreground mt-5">
                업로드된 파일은 분석 후 즉시 삭제됩니다.
              </p>
            </>
          ) : (
            <div className="w-full bg-white border border-border rounded-2xl px-8 py-12 flex flex-col items-center gap-5 shadow-sm">
              <div className="w-10 h-10 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium">분석 중...</p>
                <p className="text-xs text-muted-foreground mt-0.5">형상 · 치수 · 규격 검사</p>
              </div>
              <div className="w-full">
                <div className="flex justify-between text-xs text-muted-foreground mb-2">
                  <span>진행률</span>
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
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── RESULT PAGE ─── */
function ResultPage({ fileName, onBack }: { fileName: string; onBack: () => void }) {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-6 py-10">
        {/* Back + header */}
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" /> 새 파일 분석
        </button>

        <div className="flex items-start justify-between mb-10 flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle className="w-4 h-4 text-emerald-500" />
              <span className="text-xs text-muted-foreground font-mono">{fileName}</span>
            </div>
            <h2 className="text-2xl font-bold">분석 완료 — 3건 발견</h2>
          </div>
          <div className="flex gap-4 text-sm pt-1">
            <span className="text-red-600 font-medium">오류 2</span>
            <span className="text-amber-600 font-medium">경고 1</span>
          </div>
        </div>

        {/* Issues */}
        <div className="flex flex-col gap-7">
          {MOCK_ISSUES.map((issue) => (
            <div key={issue.id} className="border border-border rounded-xl overflow-hidden bg-white">
              <div className="relative h-52 bg-muted overflow-hidden">
                <img src={issue.image} alt={issue.title} className="w-full h-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
                <div className="absolute bottom-4 left-5 flex items-center gap-2">
                  <LevelBadge level={issue.level} />
                  <span className="text-xs text-white/80 font-mono">{issue.id}</span>
                </div>
              </div>
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
        <div className="mt-8 flex items-center justify-between border border-border rounded-xl px-6 py-5 bg-white">
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
    </div>
  );
}

/* ─── ROOT ─── */
export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [fileName, setFileName] = useState("");

  return (
    <>
      <Navbar onHome={() => setPage("home")} />
      {page === "home" && <HomePage onStart={() => setPage("upload")} />}
      {page === "upload" && (
        <UploadPage
          onBack={() => setPage("home")}
          onDone={(name) => { setFileName(name); setPage("result"); }}
        />
      )}
      {page === "result" && <ResultPage fileName={fileName} onBack={() => setPage("upload")} />}
    </>
  );
}