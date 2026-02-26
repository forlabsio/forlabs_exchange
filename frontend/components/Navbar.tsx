"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function Navbar() {
  const { token, user, logout, hydrate } = useAuthStore();
  const router = useRouter();
  const [isSimulation, setIsSimulation] = useState(false);

  useEffect(() => {
    hydrate();
  }, []);

  useEffect(() => {
    if (user?.role === "admin") {
      apiFetch("/api/admin/system-status")
        .then((data) => setIsSimulation(!data.live_trading))
        .catch(() => {});
    }
  }, [user]);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <nav className="flex items-center justify-between px-6 h-14 border-b flex-shrink-0"
      style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}>
      <div className="flex items-center gap-8">
        <Link href="/exchange/BTC_USDT" className="text-lg font-bold" style={{ color: "var(--blue)" }}>
          ForLabsEX
        </Link>
        <div className="flex items-center gap-6 text-sm" style={{ color: "var(--text-secondary)" }}>
          <Link href="/exchange/BTC_USDT" className="hover:text-white transition-colors">거래소</Link>
          <Link href="/futures/BTC_USDT" className="hover:text-white transition-colors">선물</Link>
<Link href="/announcements" className="hover:text-white transition-colors">공지사항</Link>
          <Link href="/bot-market" className="hover:text-white transition-colors">봇 마켓</Link>
          {token && (
            <Link href="/my-bots" className="hover:text-white transition-colors">내 봇</Link>
          )}
          {user?.role === "admin" && (
            <>
              <Link href="/admin/bots" className="hover:text-white transition-colors font-medium" style={{ color: "#f59e0b" }}>
                봇 관리
              </Link>
              <Link href="/admin/subscriptions" className="hover:text-white transition-colors font-medium" style={{ color: "#f59e0b" }}>
                구독 관리
              </Link>
              <Link href="/admin/withdrawals" className="hover:text-white transition-colors font-medium" style={{ color: "#f59e0b" }}>
                출금 관리
              </Link>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-4 text-sm">
        {token ? (
          <>
            {isSimulation && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wide animate-pulse"
                style={{ background: "rgba(239,68,68,0.2)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.4)" }}>
                SIMULATION
              </span>
            )}
            <Link href="/wallet" style={{ color: "var(--text-secondary)" }} className="hover:text-white transition-colors">자산</Link>
            <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
              {user?.wallet_address ? `${user.wallet_address.slice(0, 6)}...${user.wallet_address.slice(-4)}` : ""}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              className="px-4 py-1.5 rounded text-sm"
              style={{ background: "var(--bg-panel)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
              로그아웃
            </button>
          </>
        ) : (
          <>
          <Link href="/login"
            className="px-4 py-1.5 rounded text-sm font-medium text-white"
            style={{ background: "#f6851b" }}>
            지갑 연결
          </Link>
          </>
        )}
      </div>
    </nav>
  );
}
