"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

interface WalletEntry {
  asset: string;
  balance: string;
  locked: string;
  price_usdt: number;
  value_usdt: number;
}

interface WithdrawableInfo {
  wallet_balance_usdt: number;
  locked_in_bots_usdt: number;
  total_pnl_usdt: number;
  pending_withdrawal_usdt: number;
  withdrawable_usdt: number;
  bot_details: { bot_id: number; bot_name: string; allocated_usdt: number; pnl_usdt: number }[];
}

interface WithdrawalRecord {
  id: number;
  amount: number;
  to_address: string;
  status: string;
  tx_hash: string | null;
  admin_note: string | null;
  created_at: string | null;
  processed_at: string | null;
}

const ASSET_ICONS: Record<string, string> = {
  BTC: "₿",
  ETH: "Ξ",
  USDT: "$",
  BNB: "B",
  SOL: "◎",
};

const ASSET_COLORS: Record<string, string> = {
  BTC: "#f7931a",
  ETH: "#627eea",
  USDT: "#26a17b",
  BNB: "#f3ba2f",
  SOL: "#9945ff",
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: "대기중", color: "#f59e0b" },
  approved: { label: "승인됨", color: "var(--blue)" },
  completed: { label: "완료", color: "var(--green)" },
  rejected: { label: "거절됨", color: "var(--red)" },
};

const POLYGON_CHAIN_ID = "0x89";
const USDT_CONTRACT = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F";
const ADMIN_WALLET = process.env.NEXT_PUBLIC_ADMIN_WALLET || "";

function DepositModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [amount, setAmount] = useState("");
  const [step, setStep] = useState<"input" | "sending" | "verifying" | "done">("input");
  const [error, setError] = useState("");

  const handleDeposit = async () => {
    const num = parseFloat(amount);
    if (!num || num < 1) {
      setError("최소 1 USDT 이상 입금하세요");
      return;
    }
    if (!window.ethereum) {
      setError("MetaMask가 필요합니다");
      return;
    }
    if (!ADMIN_WALLET) {
      setError("관리자 지갑 주소가 설정되지 않았습니다");
      return;
    }

    setError("");
    setStep("sending");

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

      // Send USDT via ERC-20 transfer
      const amountHex = (BigInt(Math.round(num * 1e6))).toString(16).padStart(64, "0");
      const toHex = ADMIN_WALLET.slice(2).toLowerCase().padStart(64, "0");
      const data = "0xa9059cbb" + toHex + amountHex;

      const txHash = await window.ethereum.request({
        method: "eth_sendTransaction",
        params: [{ from, to: USDT_CONTRACT, data, value: "0x0" }],
      }) as string;

      // Verify on backend
      setStep("verifying");
      await apiFetch("/api/wallet/deposit/verify", {
        method: "POST",
        body: JSON.stringify({ tx_hash: txHash }),
      });

      setStep("done");
      setTimeout(() => onSuccess(), 1500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "입금 실패");
      setStep("input");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-md rounded-2xl p-6" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>USDT 입금</h2>

        {step === "done" ? (
          <div className="text-center py-8">
            <p className="text-2xl mb-2" style={{ color: "var(--green)" }}>입금 완료!</p>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>잔액이 반영되었습니다.</p>
          </div>
        ) : (
          <>
            <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: "var(--bg-base)" }}>
              <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>입금 네트워크</p>
              <p className="font-semibold" style={{ color: "var(--text-primary)" }}>Polygon (USDT)</p>
              <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
                MetaMask에서 Polygon 네트워크의 USDT를 전송합니다.
              </p>
            </div>

            <div className="mb-4">
              <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>입금 금액 (USDT)</label>
              <input
                type="number" step="1" min="1" placeholder="100" title="입금 금액"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                disabled={step !== "input"}
                className="w-full px-3 py-2 rounded text-sm outline-none"
                style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              />
            </div>

            {error && <p className="text-xs mb-3" style={{ color: "var(--red)" }}>{error}</p>}

            <div className="flex gap-3">
              <button type="button" onClick={onClose} disabled={step !== "input"}
                className="flex-1 py-2 rounded text-sm"
                style={{ background: "var(--bg-base)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                취소
              </button>
              <button type="button" onClick={handleDeposit} disabled={step !== "input"}
                className="flex-1 py-2 rounded text-sm font-medium text-white"
                style={{ background: step !== "input" ? "#666" : "var(--blue)" }}>
                {step === "sending" ? "MetaMask 확인 중..." : step === "verifying" ? "검증 중..." : "입금하기"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function AdminDepositModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const { user } = useAuthStore();
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleDeposit = async () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) {
      setError("유효한 금액을 입력하세요");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await apiFetch("/api/wallet/deposit", {
        method: "POST",
        body: JSON.stringify({ user_id: user!.id, asset: "USDT", amount: num }),
      });
      setDone(true);
      setTimeout(() => onSuccess(), 1200);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "충전 실패");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-md rounded-2xl p-6" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>관리자 직접 충전</h2>

        {done ? (
          <div className="text-center py-8">
            <p className="text-2xl mb-2" style={{ color: "var(--green)" }}>충전 완료!</p>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>잔액이 반영되었습니다.</p>
          </div>
        ) : (
          <>
            <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.3)" }}>
              <p className="text-xs font-medium" style={{ color: "#f59e0b" }}>관리자 전용</p>
              <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                온체인 전송 없이 내부 잔액에 직접 반영됩니다.
              </p>
            </div>

            <div className="mb-4">
              <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>충전 금액 (USDT)</label>
              <input
                type="number" step="1" min="1" placeholder="1000" title="충전 금액"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                className="w-full px-3 py-2 rounded text-sm outline-none"
                style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              />
            </div>

            {error && <p className="text-xs mb-3" style={{ color: "var(--red)" }}>{error}</p>}

            <div className="flex gap-3">
              <button type="button" onClick={onClose}
                className="flex-1 py-2 rounded text-sm"
                style={{ background: "var(--bg-base)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                취소
              </button>
              <button type="button" onClick={handleDeposit} disabled={submitting}
                className="flex-1 py-2 rounded text-sm font-medium text-white"
                style={{ background: submitting ? "#666" : "#f59e0b" }}>
                {submitting ? "처리중..." : "직접 충전"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function WithdrawModal({
  info,
  walletAddress,
  onClose,
  onSuccess,
}: {
  info: WithdrawableInfo;
  walletAddress: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [toAddress, setToAddress] = useState(walletAddress);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) {
      setError("유효한 금액을 입력하세요");
      return;
    }
    if (num > info.withdrawable_usdt) {
      setError(`출금 가능 금액 초과 (최대: ${info.withdrawable_usdt.toFixed(2)} USDT)`);
      return;
    }
    if (!toAddress || !toAddress.startsWith("0x")) {
      setError("유효한 지갑 주소를 입력하세요");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await apiFetch("/api/wallet/withdraw", {
        method: "POST",
        body: JSON.stringify({ amount: num, to_address: toAddress }),
      });
      onSuccess();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "출금 요청 실패";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-md rounded-2xl p-6" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>출금 요청</h2>

        {/* Withdrawable summary */}
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: "var(--bg-base)" }}>
          <div className="flex justify-between mb-1">
            <span style={{ color: "var(--text-secondary)" }}>봇 수익 (PnL)</span>
            <span style={{ color: info.total_pnl_usdt >= 0 ? "var(--green)" : "var(--red)" }}>
              {info.total_pnl_usdt >= 0 ? "+" : ""}{info.total_pnl_usdt.toFixed(2)} USDT
            </span>
          </div>
          <div className="flex justify-between mb-1">
            <span style={{ color: "var(--text-secondary)" }}>지갑 잔액</span>
            <span style={{ color: "var(--text-primary)" }}>{info.wallet_balance_usdt.toFixed(2)} USDT</span>
          </div>
          {info.pending_withdrawal_usdt > 0 && (
            <div className="flex justify-between mb-1">
              <span style={{ color: "var(--text-secondary)" }}>대기중 출금</span>
              <span style={{ color: "#f59e0b" }}>-{info.pending_withdrawal_usdt.toFixed(2)} USDT</span>
            </div>
          )}
          <div className="flex justify-between pt-2 font-semibold" style={{ borderTop: "1px solid var(--border)" }}>
            <span style={{ color: "var(--text-primary)" }}>출금 가능</span>
            <span style={{ color: "var(--green)" }}>{info.withdrawable_usdt.toFixed(2)} USDT</span>
          </div>
        </div>

        {/* Bot PnL details */}
        {info.bot_details.length > 0 && (
          <div className="mb-4">
            <p className="text-xs mb-2" style={{ color: "var(--text-secondary)" }}>봇별 수익 상세</p>
            {info.bot_details.map((b) => (
              <div key={b.bot_id} className="flex justify-between text-xs py-1">
                <span style={{ color: "var(--text-primary)" }}>{b.bot_name}</span>
                <span style={{ color: b.pnl_usdt >= 0 ? "var(--green)" : "var(--red)" }}>
                  {b.pnl_usdt >= 0 ? "+" : ""}{b.pnl_usdt.toFixed(2)} USDT
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Form */}
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>출금 금액 (USDT)</label>
            <div className="flex gap-2">
              <input
                type="number" step="0.01" placeholder="0.00" title="출금 금액"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                className="flex-1 px-3 py-2 rounded text-sm outline-none"
                style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              />
              <button
                onClick={() => setAmount(info.withdrawable_usdt.toFixed(2))}
                className="px-3 py-2 rounded text-xs"
                style={{ background: "rgba(59,130,246,0.2)", color: "var(--blue)" }}>
                전액
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>수신 지갑 주소 (Polygon)</label>
            <input
              type="text" value={toAddress}
              onChange={(e) => setToAddress(e.target.value)}
              className="w-full px-3 py-2 rounded text-sm font-mono outline-none"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
        </div>

        {error && <p className="text-xs mt-3" style={{ color: "var(--red)" }}>{error}</p>}

        <div className="flex gap-3 mt-5">
          <button onClick={onClose} className="flex-1 py-2 rounded text-sm"
            style={{ background: "var(--bg-base)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
            취소
          </button>
          <button onClick={handleSubmit} disabled={submitting}
            className="flex-1 py-2 rounded text-sm font-medium text-white"
            style={{ background: submitting ? "#666" : "var(--blue)" }}>
            {submitting ? "처리중..." : "출금 요청"}
          </button>
        </div>

        <p className="text-xs mt-3 text-center" style={{ color: "var(--text-secondary)" }}>
          관리자 승인 후 Polygon USDT로 전송됩니다
        </p>
      </div>
    </div>
  );
}

export default function WalletPage() {
  const [wallets, setWallets] = useState<WalletEntry[]>([]);
  const [withdrawInfo, setWithdrawInfo] = useState<WithdrawableInfo | null>(null);
  const [withdrawals, setWithdrawals] = useState<WithdrawalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [showDeposit, setShowDeposit] = useState(false);
  const [showAdminDeposit, setShowAdminDeposit] = useState(false);
  const { token, user, hydrate } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, []);

  const loadData = async () => {
    try {
      const [w, info, hist] = await Promise.all([
        apiFetch("/api/wallet"),
        apiFetch("/api/wallet/withdrawable"),
        apiFetch("/api/wallet/withdrawals"),
      ]);
      setWallets(w);
      setWithdrawInfo(info);
      setWithdrawals(hist);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token === null && !loading) {
      router.push("/login");
      return;
    }
    if (!token) return;
    loadData();
  }, [token]);

  const totalValueUsdt = wallets.reduce((sum, w) => sum + (w.value_usdt || 0), 0);
  const hasNonUsdt = wallets.some((w) => w.asset !== "USDT" && parseFloat(w.balance) > 0);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>내 자산</h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>입금 · 봇 투자 · 출금</p>
        </div>
        <div className="flex gap-2">
          {user?.role === "admin" && (
            <button type="button" onClick={() => setShowAdminDeposit(true)}
              className="px-4 py-2.5 rounded-lg text-sm font-medium"
              style={{ background: "rgba(245,158,11,0.2)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.3)" }}>
              직접 충전
            </button>
          )}
          <button type="button" onClick={() => setShowDeposit(true)}
            className="px-4 py-2.5 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--blue)" }}>
            입금
          </button>
          {withdrawInfo && withdrawInfo.withdrawable_usdt > 0 && (
            <button type="button" onClick={() => setShowWithdraw(true)}
              className="px-4 py-2.5 rounded-lg text-sm font-medium text-white"
              style={{ background: "var(--green)" }}>
              출금
            </button>
          )}
        </div>
      </div>

      {/* Total summary */}
      {!loading && wallets.length > 0 && (
        <div className="mb-4 p-5 rounded-2xl" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
          <p className="text-xs mb-2" style={{ color: "var(--text-secondary)" }}>총 자산 (USDT 환산)</p>
          <p className="text-3xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>
            {totalValueUsdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            <span className="text-base font-normal ml-2" style={{ color: "var(--text-secondary)" }}>USDT</span>
          </p>
          {hasNonUsdt && (
            <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
              현재 시세 기준 환산값 (실시간 변동)
            </p>
          )}
        </div>
      )}

      {/* Balance breakdown */}
      {withdrawInfo && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div className="p-3 rounded-xl" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>출금 가능</p>
            <p className="text-lg font-bold font-mono" style={{ color: "var(--green)" }}>
              {withdrawInfo.withdrawable_usdt.toFixed(2)}
            </p>
          </div>
          <div className="p-3 rounded-xl" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>봇 투자중</p>
            <p className="text-lg font-bold font-mono" style={{ color: "var(--blue)" }}>
              {withdrawInfo.locked_in_bots_usdt.toFixed(2)}
            </p>
          </div>
          <div className="p-3 rounded-xl" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>봇 수익</p>
            <p className="text-lg font-bold font-mono" style={{ color: withdrawInfo.total_pnl_usdt >= 0 ? "var(--green)" : "var(--red)" }}>
              {withdrawInfo.total_pnl_usdt >= 0 ? "+" : ""}{withdrawInfo.total_pnl_usdt.toFixed(2)}
            </p>
          </div>
        </div>
      )}

      {/* Asset cards */}
      {loading ? (
        <div className="text-center py-16" style={{ color: "var(--text-secondary)" }}>로딩 중...</div>
      ) : wallets.length === 0 ? (
        <div className="text-center py-16" style={{ color: "var(--text-secondary)" }}>보유 자산 없음</div>
      ) : (
        <div className="flex flex-col gap-3">
          {wallets.map((w) => {
            const balance = parseFloat(w.balance);
            const locked = parseFloat(w.locked);
            const total = balance + locked;
            const color = ASSET_COLORS[w.asset] || "var(--blue)";
            const isNonUsdt = w.asset !== "USDT";

            return (
              <div key={w.asset} className="rounded-xl p-4"
                style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full flex items-center justify-center text-base font-bold flex-shrink-0"
                      style={{ background: `${color}20`, color }}>
                      {ASSET_ICONS[w.asset] || w.asset[0]}
                    </div>
                    <div>
                      <p className="font-semibold" style={{ color: "var(--text-primary)" }}>{w.asset}</p>
                      {isNonUsdt && w.price_usdt > 0 && (
                        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                          1 {w.asset} = ${w.price_usdt.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-mono font-semibold" style={{ color: "var(--text-primary)" }}>
                      {total.toFixed(w.asset === "USDT" ? 2 : 8)} {w.asset}
                    </p>
                    {isNonUsdt && w.value_usdt > 0 && (
                      <p className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
                        ≈ ${w.value_usdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT
                      </p>
                    )}
                    {locked > 0 && (
                      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                        잠금: {locked.toFixed(8)}
                      </p>
                    )}
                  </div>
                </div>

                {isNonUsdt && w.value_usdt > 0 && totalValueUsdt > 0 && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs mb-1" style={{ color: "var(--text-secondary)" }}>
                      <span>포트폴리오 비중</span>
                      <span>{((w.value_usdt / totalValueUsdt) * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg-base)" }}>
                      <div className="h-full rounded-full transition-all"
                        style={{ width: `${(w.value_usdt / totalValueUsdt) * 100}%`, background: color }} />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Withdrawal history */}
      {withdrawals.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>출금 내역</h2>
          <div className="flex flex-col gap-2">
            {withdrawals.map((w) => {
              const st = STATUS_LABELS[w.status] || { label: w.status, color: "var(--text-secondary)" };
              return (
                <div key={w.id} className="rounded-lg p-3 flex items-center justify-between"
                  style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                        {w.amount.toFixed(2)} USDT
                      </span>
                      <span className="px-2 py-0.5 rounded text-xs" style={{ background: `${st.color}20`, color: st.color }}>
                        {st.label}
                      </span>
                    </div>
                    <p className="text-xs font-mono mt-1" style={{ color: "var(--text-secondary)" }}>
                      → {w.to_address.slice(0, 10)}...{w.to_address.slice(-6)}
                    </p>
                    {w.tx_hash && (
                      <a href={`https://polygonscan.com/tx/${w.tx_hash}`} target="_blank" rel="noopener noreferrer"
                        className="text-xs" style={{ color: "var(--blue)" }}>
                        TX: {w.tx_hash.slice(0, 12)}...
                      </a>
                    )}
                    {w.admin_note && (
                      <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>메모: {w.admin_note}</p>
                    )}
                  </div>
                  <div className="text-right text-xs" style={{ color: "var(--text-secondary)" }}>
                    {w.created_at && new Date(w.created_at).toLocaleDateString("ko-KR")}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-6 flex gap-4 justify-center text-sm">
        <a href="/exchange/BTC_USDT" className="hover:underline" style={{ color: "var(--blue)" }}>거래소로 이동 →</a>
        <a href="/my-bots" className="hover:underline" style={{ color: "var(--text-secondary)" }}>내 봇 →</a>
      </div>

      {/* Admin direct deposit modal */}
      {showAdminDeposit && (
        <AdminDepositModal
          onClose={() => setShowAdminDeposit(false)}
          onSuccess={() => {
            setShowAdminDeposit(false);
            loadData();
          }}
        />
      )}

      {/* Deposit modal */}
      {showDeposit && (
        <DepositModal
          onClose={() => setShowDeposit(false)}
          onSuccess={() => {
            setShowDeposit(false);
            loadData();
          }}
        />
      )}

      {/* Withdraw modal */}
      {showWithdraw && withdrawInfo && user && (
        <WithdrawModal
          info={withdrawInfo}
          walletAddress={user.wallet_address || ""}
          onClose={() => setShowWithdraw(false)}
          onSuccess={() => {
            setShowWithdraw(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}
