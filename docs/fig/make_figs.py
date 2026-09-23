"""제출본에 넣을 그래프. 숫자는 전부 저장소 문서와 /api/stats 실측값이다."""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

for name in ("Malgun Gothic", "맑은 고딕", "NanumGothic"):
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        rcParams["font.family"] = name
        break
rcParams["axes.unicode_minus"] = False
OUT = sys.argv[1]
INK, SUB, ACC, WARN = "#123a5c", "#5a6a7a", "#1f77b4", "#b4600a"
GRID = "#d6dee6"

def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)

def base(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=SUB, labelsize=8)
    ax.yaxis.grid(True, color=GRID, lw=.6)
    ax.set_axisbelow(True)

# 1. 퍼널 — 09-14 주 (사람 수)
fig, ax = plt.subplots(figsize=(5.4, 2.5))
steps = ["방문", "검사 시작", "결과 봄", "다시 검사"]
vals = [31, 11, 11, 10]
bars = ax.bar(steps, vals, color=[INK, ACC, ACC, "#2ca02c"], width=.62)
for b, v, pct in zip(bars, vals, ["", "35%", "100%", "91%"]):
    ax.text(b.get_x() + b.get_width() / 2, v + .7, f"{v}명",
            ha="center", fontsize=9, color=INK, fontweight="bold")
    if pct:
        ax.text(b.get_x() + b.get_width() / 2, v / 2, pct, ha="center",
                fontsize=9, color="white", fontweight="bold")
ax.set_ylim(0, 37); ax.set_ylabel("사람 수", fontsize=8, color=SUB)
ax.annotate("", xy=(1, 13), xytext=(0, 31),
            arrowprops=dict(arrowstyle="->", color=WARN, lw=1.6))
ax.text(.5, 25, "65% 이탈", color=WARN, fontsize=9, fontweight="bold")
base(ax)
save(fig, "fig_funnel.png")

# 2. 주간 추이
fig, ax = plt.subplots(figsize=(5.4, 2.05))
wk = ["08-24", "08-31", "09-07", "09-14"]
vis, chk, rec = [7, 42, 38, 31], [1, 2, 10, 11], [0, 0, 5, 10]
ax.plot(wk, vis, "-o", color=INK, lw=1.8, ms=5, label="방문한 사람")
ax.plot(wk, chk, "-o", color=ACC, lw=1.8, ms=5, label="검사한 사람")
ax.plot(wk, rec, "-o", color="#2ca02c", lw=2.2, ms=6, label="재검사한 사람 (북극성)")
for x, y in zip(wk, rec):
    ax.text(x, y + 1.8, str(y), ha="center", fontsize=8, color="#2ca02c",
            fontweight="bold")
ax.axhline(20, color=WARN, ls="--", lw=1.1)
ax.text(3.08, 20, "8주 목표 20명", color=WARN, fontsize=7.6, va="center")
ax.set_xlim(-.25, 3.05)
ax.set_ylim(-3, 50); ax.set_ylabel("사람 수", fontsize=8, color=SUB)
ax.legend(fontsize=7.4, frameon=False, loc="upper center", ncol=3,
          bbox_to_anchor=(.5, 1.18), handlelength=1.4, columnspacing=1.2)
base(ax)
save(fig, "fig_weekly.png")

# 3. 실기 응시자와 합격률
fig, ax = plt.subplots(figsize=(5.4, 2.4))
yr = ["2021", "2022", "2023", "2024", "2025"]
take = [5464, 3557, 3234, 3100, 3399]
rate = [45.3, 51.1, 50.1, 53.0, 50.6]
fail = [round(t * (100 - r) / 100) for t, r in zip(take, rate)]
ax.bar(yr, take, color="#cfdae6", width=.6, label="실기 응시자")
ax.bar(yr, fail, color=WARN, width=.6, label="불합격")
for x, t, f in zip(yr, take, fail):
    ax.text(x, t + 90, f"{t:,}", ha="center", fontsize=7.6, color=SUB)
    ax.text(x, f / 2, f"{f:,}", ha="center", fontsize=8, color="white",
            fontweight="bold")
ax2 = ax.twinx()
ax2.plot(yr, rate, "-o", color=INK, lw=1.8, ms=5)
ax2.set_ylim(0, 100); ax2.set_ylabel("합격률 (%)", fontsize=8, color=INK)
ax2.tick_params(colors=INK, labelsize=8)
for s in ("top", "left"):
    ax2.spines[s].set_visible(False)
ax.set_ylim(0, 6400); ax.set_ylabel("사람 수", fontsize=8, color=SUB)
ax.legend(fontsize=7.5, frameon=False, loc="upper right")
base(ax)
save(fig, "fig_exam.png")

# 4. 정확도 — 표본 3종
fig, ax = plt.subplots(figsize=(5.4, 2.2))
kinds = ["우리가 만든\n기준 도면 25장", "우리가 만든\n합성 도면 100장",
         "학생에게 받은\n실제 도면 23장"]
found = [100, 100, 100]
ax.barh(kinds, found, color=[ACC, ACC, INK], height=.5)
for i, (k, v) in enumerate(zip(kinds, found)):
    ax.text(v - 2, i, f"{v}%", ha="right", va="center", color="white",
            fontsize=10, fontweight="bold")
ax.text(101, 2, "헛지적 0건", va="center", fontsize=8.5, color=WARN,
        fontweight="bold")
ax.set_xlim(0, 118); ax.set_xlabel("찾아야 할 문제를 찾은 비율", fontsize=8,
                                   color=SUB)
ax.invert_yaxis()
base(ax); ax.yaxis.grid(False); ax.xaxis.grid(True, color=GRID, lw=.6)
save(fig, "fig_accuracy.png")

# 5. AI 모델 실측 (2026-09-18, 실제 도면 10장)
fig, ax = plt.subplots(figsize=(5.4, 2.3))
mods = ["gemini-3.6-flash\n(예전 1순위)", "gemini-3.1-flash-lite\n(지금 1순위)",
        "gemini-3.5-flash", "gemini-3.5-flash-lite"]
med = [7.5, 3.2, 14.3, 2.1]
cols = [WARN, "#2ca02c", ACC, WARN]
b = ax.bar(mods, med, color=cols, width=.55)
for bb, v in zip(b, med):
    ax.text(bb.get_x() + bb.get_width() / 2, v + .35, f"{v}초", ha="center",
            fontsize=8.5, color=INK, fontweight="bold")
ax.text(0, 9.2, "20번 중 18번 실패", color=WARN, fontsize=8, ha="center",
        fontweight="bold")
ax.text(3, 3.8, "20번 모두 감점 0", color=WARN, fontsize=8, ha="center",
        fontweight="bold")
ax.axhline(8, color=SUB, ls=":", lw=1.1)
ax.text(3.45, 8.3, "8초 상한", fontsize=7.5, color=SUB, ha="right")
ax.set_ylim(0, 16.5); ax.set_ylabel("응답 시간 중앙값 (초)", fontsize=8, color=SUB)
ax.tick_params(axis="x", labelsize=7)
base(ax)
save(fig, "fig_ai.png")

# 6. 배점 100점
fig, ax = plt.subplots(figsize=(5.6, 1.9))
items = [("투상도 선택과 배열", 30, "#123a5c"), ("치수", 15, "#1f77b4"),
         ("끼워맞춤·치수공차", 10, "#4f9ad0"), ("표면거칠기", 10, "#7fb8e0"),
         ("기하공차", 10, "#a5cdea"), ("도면 배치와 외관", 10, "#c2dcf0"),
         ("주서·표제란", 8, "#dbe9f6"), ("재료·열처리", 7, "#eef4fa")]
left = 0
for i, (name, v, c) in enumerate(items):
    ax.barh([0], [v], left=left, color=c, height=.5, edgecolor="white", lw=1)
    mid = left + v / 2
    ax.text(mid, 0, str(v), ha="center", va="center", fontsize=8.5,
            color="white" if v >= 15 else INK, fontweight="bold")
    y = .46 if i % 2 == 0 else .74          # 이름이 길어 두 줄로 엇갈려 놓는다
    ax.plot([mid, mid], [.26, y - .04], color=GRID, lw=.7)
    ax.text(mid, y, name, ha="center", va="bottom", fontsize=6.6, color=SUB)
    left += v
ax.set_xlim(-1, 101); ax.set_ylim(-.62, 1.06); ax.axis("off")
ax.text(15, -.55, "AI 가 채점 (30점)", ha="center", fontsize=7.5, color=INK,
        fontweight="bold")
ax.text(65, -.55, "규칙 코드가 채점 (70점)", ha="center", fontsize=7.5,
        color=ACC, fontweight="bold")
save(fig, "fig_score.png")

# 7. 문제 기록 24건
fig, ax = plt.subplots(figsize=(3.1, 2.3))
ax.pie([17, 2, 5], labels=["해결 17", "부분 2", "열림 5"],
       colors=["#2ca02c", "#f0c419", WARN], autopct="",
       textprops=dict(fontsize=8.5, color=INK), startangle=90,
       wedgeprops=dict(width=.42, edgecolor="white"))
ax.text(0, 0, "24건", ha="center", va="center", fontsize=13, color=INK,
        fontweight="bold")
save(fig, "fig_problems.png")
print("그래프 7장 완료")
