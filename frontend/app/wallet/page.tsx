"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

interface WalletEntry {
  asset: string;
  balance: string;
  locked: string;
}

const ASSET_ICONS: Record<string, string> = {
  BTC: "₿",
  ETH: "Ξ",
  USDT: "$",
  BNB: "B",
  SOL: "◎",
};

export default function WalletPage() {
  const [wallets, setWallets] = useState<WalletEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { token, hydrate } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, []);

  useEffect(() => {
    if (token === null && !loading) {
      router.push("/login");
      return;
    }
    if (!token) return;
    apiFetch("/api/wallet")
      .then(setWallets)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token]);

  const totalUSDT = wallets.reduce((sum, w) => {
    if (w.asset === "USDT") return sum + parseFloat(w.balance) + parseFloat(w.locked);
    return sum;
  }, 0);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>내 자산</h1>
      <p className="text-sm mb-8" style={{ color: "var(--text-secondary)" }}>
        페이퍼 트레이딩 가상 지갑
      </p>

      {/* Summary card */}
      {!loading && wallets.length > 0 && (
        <div className="mb-6 p-5 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
          <p className="text-sm mb-1" style={{ color: "var(--text-secondary)" }}>총 자산 (USDT 환산)</p>
          <p className="text-3xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>
            {totalUSDT.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            <span className="text-lg font-normal ml-2" style={{ color: "var(--text-secondary)" }}>USDT</span>
          </p>
        </div>
      )}

      {/* Wallet table */}
      <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: "var(--bg-panel)", color: "var(--text-secondary)" }}>
              <th className="text-left px-4 py-3">자산</th>
              <th className="text-right px-4 py-3">사용 가능</th>
              <th className="text-right px-4 py-3">잠금</th>
              <th className="text-right px-4 py-3">합계</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="text-center py-8" style={{ color: "var(--text-secondary)" }}>
                  로딩 중...
                </td>
              </tr>
            ) : wallets.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-center py-8" style={{ color: "var(--text-secondary)" }}>
                  보유 자산 없음
                </td>
              </tr>
            ) : (
              wallets.map((w) => {
                const total = parseFloat(w.balance) + parseFloat(w.locked);
                return (
                  <tr key={w.asset} style={{ borderTop: "1px solid var(--border)" }}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                          style={{ background: "var(--bg-secondary)", color: "var(--blue)" }}>
                          {ASSET_ICONS[w.asset] || w.asset[0]}
                        </span>
                        <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{w.asset}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono" style={{ color: "var(--text-primary)" }}>
                      {parseFloat(w.balance).toFixed(8)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono" style={{ color: "var(--text-secondary)" }}>
                      {parseFloat(w.locked).toFixed(8)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold" style={{ color: "var(--text-primary)" }}>
                      {total.toFixed(8)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Quick trade link */}
      <div className="mt-6 text-center">
        <a href="/exchange/BTC_USDT"
          className="text-sm hover:underline"
          style={{ color: "var(--blue)" }}>
          거래소로 이동 →
        </a>
      </div>
    </div>
  );
}
