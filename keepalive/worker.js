// 공개 서버(Render 무료)를 깨워 둔다 — 15분 동안 요청이 없으면 잠든다(plan/문제점/P31).
// GitHub 예약 실행은 5분마다로 적어도 하루 3~6번만 돌았다. Cloudflare Cron Trigger 는 무료 계정 칸(5개)이
// 이미 다 차 있어서, Durable Object 알람이 5분마다 스스로 다음 알람을 거는 방식으로 돈다.
// 첫 화면(/)은 방문으로 세이므로 깨울 때 쓰지 않는다 — /api/health 는 세지 않는다.
const HEALTH = "https://naverogq.onrender.com/api/health";
const EVERY = 5 * 60 * 1000;
const QUIET_UTC = [15, 16, 17];   // 한국 시간 0~3시는 쉰다 — 무료 서버 시간을 아낀다(GitHub 예약 실행과 같은 시간대)

async function ping() {
  const t = Date.now();
  const r = await fetch(HEALTH);
  return { at: new Date().toISOString(), status: r.status, ms: Date.now() - t };
}

export class Pinger {
  constructor(state) {
    this.storage = state.storage;
  }

  // 알람이 없으면 건다(다시 걸어도 하나만 남는다). 마지막으로 깨운 기록을 돌려준다
  async fetch() {
    if ((await this.storage.getAlarm()) === null) await this.storage.setAlarm(Date.now() + 1000);
    return Response.json({ next: await this.storage.getAlarm(), last: (await this.storage.get("last")) || null });
  }

  async alarm() {
    try {
      if (!QUIET_UTC.includes(new Date().getUTCHours())) await this.storage.put("last", await ping());
    } finally {
      await this.storage.setAlarm(Date.now() + EVERY);   // 깨우다 실패해도 다음 알람은 건다
    }
  }
}

// 이 주소를 열면 알람이 걸려 있는지 확인하고(없으면 건다) 마지막 기록을 보여 준다.
// GitHub 예약 실행도 돌 때마다 이 주소를 불러, 알람이 끊겼으면 다시 건다.
export default {
  async fetch(request, env) {
    return env.PINGER.get(env.PINGER.idFromName("naverogq")).fetch(request);
  },
};
