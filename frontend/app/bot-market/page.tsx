"use client";
import { useEffect, useState } from "react";
import { useBotStore, Bot } from "@/stores/botStore";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const POLYGON_CHAIN_ID = "0x89"; // 137
const USDT_CONTRACT = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F";
const ADMIN_WALLET = process.env.NEXT_PUBLIC_ADMIN_WALLET || "";

const STRATEGY_LABELS: Record<string, string> = {
  rsi_trend: "RSI + 추세필터",
  boll_adx: "볼린저 + ADX",
  trend_ma200: "Trend 200MA",
  adaptive_grid: "Adaptive Grid",
  breakout_lite: "Breakout Lite",
};

const STRATEGY_COLORS: Record<string, string> = {
  rsi_trend: "#a78bfa",
  boll_adx: "#fb923c",
  trend_ma200: "var(--blue)",
  adaptive_grid: "var(--green)",
  breakout_lite: "#f43f5e",
};

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span className="text-sm font-semibold" style={{ color: color || "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

function SubscribeModal({ bot, allocation, onAllocationChange, onClose, loading, setLoading, usdtBalance, onSuccess }: {
  bot: Bot;
  allocation: number;
  onAllocationChange: (v: number) => void;
  onClose: () => void;
  loading: boolean;
  setLoading: (v: boolean) => void;
  usdtBalance: number;
  onSuccess: () => void;
}) {
  const stratColor = STRATEGY_COLORS[bot.strategy_type] || "var(--blue)";
  const isFree = bot.monthly_fee === 0;

  const handleSubscribe = async () => {
    if (!window.ethereum) {
      alert("MetaMask가 필요합니다.");
      return;
    }
    if (usdtBalance < allocation) {
      alert(`USDT 잔액 부족 (보유: ${usdtBalance.toFixed(2)}, 필요: ${allocation})\n자산 페이지에서 먼저 입금하세요.`);
      return;
    }
    setLoading(true);
    try {
      // Switch to Polygon
      try {
        await window.ethereum.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: POLYGON_CHAIN_ID }],
        });
      } catch (switchError: unknown) {
        const err = switchError as { code?: number };
        if (err.code === 4902) {
          await window.ethereum.request({
            method: "wallet_addEthereumChain",
            params: [{
              chainId: POLYGON_CHAIN_ID,
              chainName: "Polygon Mainnet",
              nativeCurrency: { name: "MATIC", symbol: "MATIC", decimals: 18 },
              rpcUrls: ["https://polygon-rpc.com"],
              blockExplorerUrls: ["https://polygonscan.com"],
            }],
          });
        }
      }

      const accounts = await window.ethereum.request({ method: "eth_accounts" }) as string[];
      const from = accounts[0];

      const fee = bot.monthly_fee || 0;
      let txHash: string;

      if (fee > 0) {
        const amountHex = (BigInt(Math.round(fee * 1e6))).toString(16).padStart(64, "0");
        const toHex = ADMIN_WALLET.slice(2).toLowerCase().padStart(64, "0");
        const data = "0xa9059cbb" + toHex + amountHex;

        txHash = await window.ethereum.request({
          method: "eth_sendTransaction",
          params: [{
            from,
            to: USDT_CONTRACT,
            data,
            value: "0x0",
          }],
        }) as string;
      } else {
        txHash = "free_" + Date.now();
      }

      await apiFetch(`/api/bots/${bot.id}/subscribe`, {
        method: "POST",
        body: JSON.stringify({ allocated_usdt: allocation, tx_hash: txHash }),
      });

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "결제에 실패했습니다.";
      alert(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-sm mx-4 rounded-xl p-6 flex flex-col gap-5"
        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>

        {/* Header */}
        <div>
          <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>봇 연동 확인</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            아래 봇을 내 계정에 연동합니다.
          </p>
        </div>

        {/* Bot info */}
        <div className="rounded-lg p-4 flex flex-col gap-3" style={{ background: "var(--bg-base)" }}>
          <div className="flex items-center justify-between">
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{bot.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ background: `${stratColor}22`, color: stratColor }}>
              {STRATEGY_LABELS[bot.strategy_type] || bot.strategy_type}
            </span>
          </div>
          {bot.description && (
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {bot.description}
            </p>
          )}

          {/* Monthly fee display for paid bots */}
          {bot.monthly_fee > 0 && (
            <div className="mb-4 p-3 rounded" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>월 구독료</p>
              <p className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{bot.monthly_fee} USDT</p>
              <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>Polygon 네트워크에서 USDT로 결제됩니다</p>
            </div>
          )}

          <div className="border-t pt-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>월 이용료</span>
              <span className="text-base font-bold" style={{ color: isFree ? "var(--green)" : "var(--text-primary)" }}>
                {isFree ? "무료" : `$${bot.monthly_fee.toFixed(2)}/월`}
              </span>
            </div>
            {!isFree && (
              <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
                ※ Polygon USDT로 결제됩니다.
              </p>
            )}
          </div>
          <div className="border-t pt-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>할당 금액 (USDT)</span>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                보유: {usdtBalance.toLocaleString(undefined, { maximumFractionDigits: 2 })} USDT
              </span>
            </div>
            <input
              type="number"
              min={1}
              max={usdtBalance > 0 ? usdtBalance : undefined}
              step={1}
              value={allocation}
              onChange={(e) => onAllocationChange(Math.max(1, Number(e.target.value)))}
              title="할당 금액 (USDT)"
              placeholder="100"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-40"
            style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
            취소
          </button>
          <button
            type="button"
            onClick={handleSubscribe}
            disabled={loading}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
            style={{ background: "var(--blue)" }}>
            {loading ? "처리 중..." : (isFree ? "무료 연동" : "결제 후 연동")}
          </button>
        </div>
      </div>
    </div>
  );
}

function BotCard({ bot, onSubscribe, onUnsubscribe }: {
  bot: Bot;
  onSubscribe: (bot: Bot) => void;
  onUnsubscribe: (id: number) => void;
}) {
  const p = bot.performance;
  const stratColor = STRATEGY_COLORS[bot.strategy_type] || "var(--blue)";
  const isActive = bot.status === "active";

  return (
    <div className="rounded-xl flex flex-col gap-4 p-5"
      style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>

      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h3 className="font-semibold text-base leading-tight" style={{ color: "var(--text-primary)" }}>
            {bot.name}
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ background: `${stratColor}22`, color: stratColor }}>
              {STRATEGY_LABELS[bot.strategy_type] || bot.strategy_type}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full"
              style={{
                background: isActive ? "rgba(14,203,129,0.15)" : "rgba(246,70,93,0.15)",
                color: isActive ? "var(--green)" : "var(--red)",
              }}>
              {isActive ? "Active" : "Evicted"}
            </span>
          </div>
        </div>
      </div>

      {/* Description */}
      {bot.description && (
        <p className="text-xs leading-relaxed line-clamp-2" style={{ color: "var(--text-secondary)" }}>
          {bot.description}
        </p>
      )}

      {/* Stats grid 2x2 */}
      <div className="rounded-lg" style={{ background: "var(--bg-base)" }}>
        <div className="grid grid-cols-2 gap-3 py-3 px-3">
          <StatBox
            label="수익률"
            value={`${p.monthly_return_pct >= 0 ? "+" : ""}${p.monthly_return_pct.toFixed(2)}%`}
            color={p.monthly_return_pct >= 0 ? "var(--green)" : "var(--red)"}
          />
          <StatBox
            label="최대 낙폭 (MDD)"
            value={`${p.max_drawdown_pct.toFixed(2)}%`}
            color="var(--red)"
          />
          <StatBox
            label="샤프 비율"
            value={p.sharpe_ratio.toFixed(2)}
          />
          <StatBox
            label="승률"
            value={`${p.win_rate.toFixed(1)}%`}
            color={p.win_rate >= 50 ? "var(--green)" : "var(--red)"}
          />
        </div>
        <div className="px-3 pb-2.5 flex items-center gap-1.5">
          <span className="text-xs px-1.5 py-0.5 rounded"
            style={{ background: "rgba(255,255,255,0.06)", color: "var(--text-secondary)" }}>
            전일 데이터 기준
          </span>
          {p.calculated_at && (
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
              {new Date(p.calculated_at).toLocaleDateString("ko-KR", { month: "2-digit", day: "2-digit" })} 집계
            </span>
          )}
        </div>
      </div>

      {/* Footer info */}
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
        <div className="flex items-center gap-3">
          <span>운용 {bot.operation_days}일</span>
          <span>·</span>
          <span>구독자 {bot.subscriber_count}명</span>
          <span>·</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
            {bot.monthly_fee === 0 ? "무료" : `$${bot.monthly_fee.toFixed(2)}/월`}
          </span>
        </div>
      </div>

      {/* Action button */}
      {bot.is_subscribed ? (
        <button
          type="button"
          onClick={() => onUnsubscribe(bot.id)}
          className="w-full py-2.5 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
          style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
          연동 해제
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onSubscribe(bot)}
          disabled={!isActive}
          className="w-full py-2.5 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: "var(--blue)" }}>
          봇 연동
        </button>
      )}
    </div>
  );
}

export default function BotMarketPage() {
  const { bots, fetchBots, unsubscribe } = useBotStore();
  const { token, hydrate } = useAuthStore();
  const router = useRouter();

  const [pendingBot, setPendingBot] = useState<Bot | null>(null);
  const [subscribing, setSubscribing] = useState(false);
  const [usdtBalance, setUsdtBalance] = useState<number>(0);
  const [pendingAllocation, setPendingAllocation] = useState<number>(100);

  useEffect(() => {
    hydrate().then(() => fetchBots().catch(() => {}));
  }, []);

  useEffect(() => {
    if (!token) return;
    fetchUsdtBalance();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const fetchUsdtBalance = () => {
    if (!token) return;
    apiFetch("/api/wallet")
      .then((data: Array<{ asset: string; balance: string }>) => {
        const usdt = data.find((w) => w.asset === "USDT");
        setUsdtBalance(usdt ? parseFloat(usdt.balance) : 0);
      })
      .catch(() => {});
  };

  const handleSubscribeClick = (bot: Bot) => {
    if (!token) { router.push("/login"); return; }
    fetchUsdtBalance();
    setPendingAllocation(100);
    setPendingBot(bot);
  };

  const handleSubscribeSuccess = async () => {
    await fetchBots();
    fetchUsdtBalance();
    alert("봇 연동이 완료되었습니다!");
  };

  const handleUnsubscribe = async (botId: number) => {
    if (!token) { router.push("/login"); return; }
    try {
      await unsubscribe(botId);
      await fetchBots();
      alert("봇 연동이 해제되었습니다.");
    } catch (e: unknown) {
      alert("해제 실패: " + (e instanceof Error ? e.message : String(e)));
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {pendingBot && (
        <SubscribeModal
          bot={pendingBot}
          allocation={pendingAllocation}
          onAllocationChange={setPendingAllocation}
          onClose={() => setPendingBot(null)}
          loading={subscribing}
          setLoading={setSubscribing}
          usdtBalance={usdtBalance}
          onSuccess={handleSubscribeSuccess}
        />
      )}

      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>봇 마켓</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          봇을 선택하면 내 지갑과 연동하여 자동매매를 시작합니다.
        </p>
      </div>

      {!token && (
        <div className="mb-6 p-4 rounded-lg border" style={{ background: "var(--bg-panel)", borderColor: "var(--border)" }}>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            봇 마켓을 이용하려면{" "}
            <a href="/login" style={{ color: "var(--blue)" }}>로그인</a>
            이 필요합니다.
          </p>
        </div>
      )}

      {bots.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
          <p className="text-lg mb-2">등록된 봇이 없습니다</p>
          <p className="text-sm">운영팀이 봇을 등록하면 여기에 표시됩니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {bots.map((bot) => (
            <BotCard
              key={bot.id}
              bot={bot}
              onSubscribe={handleSubscribeClick}
              onUnsubscribe={handleUnsubscribe}
            />
          ))}
        </div>
      )}
    </div>
  );
}
