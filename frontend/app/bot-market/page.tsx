"use client";
import { useEffect } from "react";
import { useBotStore } from "@/stores/botStore";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

export default function BotMarketPage() {
  const { bots, fetchBots, subscribe, unsubscribe } = useBotStore();
  const { token, hydrate } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    hydrate();
    fetchBots().catch(() => {});
  }, []);

  const handleSubscribe = async (botId: number) => {
    if (!token) { router.push("/login"); return; }
    try {
      await subscribe(botId);
      alert("봇 연동이 완료되었습니다!");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("Subscription required")) {
        alert("구독 회원 전용입니다. 관리자에게 문의하세요.");
      } else if (msg.includes("Already subscribed")) {
        alert("이미 연동된 봇입니다.");
      } else {
        alert("연동 실패: " + msg);
      }
    }
  };

  const handleUnsubscribe = async (botId: number) => {
    if (!token) { router.push("/login"); return; }
    try {
      await unsubscribe(botId);
      alert("봇 연동이 해제되었습니다.");
    } catch (e: unknown) {
      alert("해제 실패: " + (e instanceof Error ? e.message : String(e)));
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
          봇 마켓
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          구독 회원 전용 · 봇을 선택하면 내 지갑과 연동하여 자동매매를 시작합니다.
        </p>
      </div>

      {/* Subscription notice */}
      {!token && (
        <div className="mb-6 p-4 rounded-lg border" style={{ background: "var(--bg-panel)", borderColor: "var(--border)" }}>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            봇 마켓을 이용하려면{" "}
            <a href="/login" style={{ color: "var(--blue)" }}>로그인</a>
            {" "}후 구독이 필요합니다.
          </p>
        </div>
      )}

      {/* Bot grid */}
      {bots.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
          <p className="text-lg mb-2">등록된 봇이 없습니다</p>
          <p className="text-sm">운영팀이 봇을 등록하면 여기에 표시됩니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {bots.map((bot) => (
            <div key={bot.id} className="p-5 rounded-lg flex flex-col gap-3"
              style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
              {/* Bot header */}
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-base" style={{ color: "var(--text-primary)" }}>
                    {bot.name}
                  </h3>
                  <span className="text-xs px-2 py-0.5 rounded mt-1 inline-block"
                    style={{ background: "rgba(14,203,129,0.15)", color: "var(--green)" }}>
                    Active
                  </span>
                </div>
              </div>

              {/* Description */}
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {bot.description}
              </p>

              {/* Action buttons */}
              <div className="flex gap-2 mt-auto pt-2">
                <button
                  onClick={() => handleSubscribe(bot.id)}
                  className="flex-1 py-2 rounded text-sm font-medium text-white transition-opacity hover:opacity-90"
                  style={{ background: "var(--blue)" }}>
                  연동하기
                </button>
                <button
                  onClick={() => handleUnsubscribe(bot.id)}
                  className="px-3 py-2 rounded text-sm transition-colors hover:text-white"
                  style={{
                    background: "var(--bg-secondary)",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border)"
                  }}>
                  해제
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
