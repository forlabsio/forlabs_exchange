"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { apiFetch } from "@/lib/api";

interface Subscription {
  id: number;
  user_id: number;
  wallet_address: string | null;
  bot_id: number;
  bot_name: string | null;
  is_active: boolean;
  allocated_usdt: number;
  payment_amount: number;
  tx_hash: string | null;
  started_at: string | null;
  expires_at: string | null;
  ended_at: string | null;
}

interface Payment {
  id: number;
  wallet_address: string | null;
  bot_name: string | null;
  tx_hash: string;
  amount: number;
  network: string;
  verified_at: string | null;
}

interface Stats {
  active_subscriptions: number;
  expired_subscriptions: number;
  total_revenue_usdt: number;
}

export default function AdminSubscriptionsPage() {
  const { user, hydrate } = useAuthStore();
  const router = useRouter();
  const [tab, setTab] = useState<"subscriptions" | "payments">("subscriptions");
  const [filter, setFilter] = useState("all");
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => { hydrate(); }, []);

  useEffect(() => {
    if (user && user.role !== "admin") router.push("/exchange/BTC_USDT");
    if (user?.role === "admin") {
      fetchData();
    }
  }, [user, filter]);

  const fetchData = async () => {
    try {
      const [subsData, statsData, paymentsData] = await Promise.all([
        apiFetch(`/api/admin/subscriptions?status=${filter}`),
        apiFetch("/api/admin/subscriptions/stats"),
        apiFetch("/api/admin/payments"),
      ]);
      setSubs(subsData);
      setStats(statsData);
      setPayments(paymentsData);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleSubscription = async (subId: number, isActive: boolean) => {
    try {
      await apiFetch(`/api/admin/subscriptions/${subId}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !isActive }),
      });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const isExpiringSoon = (expiresAt: string | null) => {
    if (!expiresAt) return false;
    const diff = new Date(expiresAt).getTime() - Date.now();
    return diff > 0 && diff < 3 * 24 * 60 * 60 * 1000;
  };

  const filtered = subs.filter((s) =>
    !search || (s.wallet_address?.toLowerCase().includes(search.toLowerCase()) ||
      s.bot_name?.toLowerCase().includes(search.toLowerCase()))
  );

  if (!user || user.role !== "admin") return null;

  return (
    <div className="p-6 max-w-7xl mx-auto" style={{ color: "var(--text-primary)" }}>
      <h1 className="text-2xl font-bold mb-6">구독 관리</h1>

      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>활성 구독</p>
            <p className="text-2xl font-bold" style={{ color: "var(--green)" }}>{stats.active_subscriptions}</p>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>만료 구독</p>
            <p className="text-2xl font-bold" style={{ color: "var(--red)" }}>{stats.expired_subscriptions}</p>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>총 수익</p>
            <p className="text-2xl font-bold" style={{ color: "var(--blue)" }}>{stats.total_revenue_usdt.toFixed(2)} USDT</p>
          </div>
        </div>
      )}

      <div className="flex gap-4 mb-4">
        <button onClick={() => setTab("subscriptions")}
          className="px-4 py-2 rounded text-sm font-medium"
          style={{ background: tab === "subscriptions" ? "var(--blue)" : "var(--bg-panel)", color: tab === "subscriptions" ? "#fff" : "var(--text-secondary)" }}>
          구독 목록
        </button>
        <button onClick={() => setTab("payments")}
          className="px-4 py-2 rounded text-sm font-medium"
          style={{ background: tab === "payments" ? "var(--blue)" : "var(--bg-panel)", color: tab === "payments" ? "#fff" : "var(--text-secondary)" }}>
          결제 내역
        </button>
      </div>

      {tab === "subscriptions" && (
        <>
          <div className="flex gap-4 mb-4">
            <input
              type="text" placeholder="지갑 주소 또는 봇 이름 검색..."
              value={search} onChange={(e) => setSearch(e.target.value)}
              className="flex-1 px-4 py-2 rounded text-sm outline-none"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
            <select value={filter} onChange={(e) => setFilter(e.target.value)}
              className="px-4 py-2 rounded text-sm"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              <option value="all">전체</option>
              <option value="active">활성</option>
              <option value="expired">만료</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>지갑</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>봇</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>상태</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>배정 USDT</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>결제액</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>만료일</th>
                  <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>액션</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={s.id} style={{
                    borderBottom: "1px solid var(--border)",
                    background: isExpiringSoon(s.expires_at) ? "rgba(245, 158, 11, 0.1)" : undefined,
                  }}>
                    <td className="p-3 font-mono text-xs">
                      {s.wallet_address ? `${s.wallet_address.slice(0, 6)}...${s.wallet_address.slice(-4)}` : "-"}
                    </td>
                    <td className="p-3">{s.bot_name || "-"}</td>
                    <td className="p-3">
                      <span className="px-2 py-1 rounded text-xs" style={{
                        background: s.is_active ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
                        color: s.is_active ? "var(--green)" : "var(--red)",
                      }}>
                        {s.is_active ? (isExpiringSoon(s.expires_at) ? "만료 임박" : "활성") : "만료"}
                      </span>
                    </td>
                    <td className="p-3">{s.allocated_usdt}</td>
                    <td className="p-3">{s.payment_amount} USDT</td>
                    <td className="p-3 text-xs">
                      {s.expires_at ? new Date(s.expires_at).toLocaleDateString("ko-KR") : "-"}
                    </td>
                    <td className="p-3">
                      <button
                        onClick={() => toggleSubscription(s.id, s.is_active)}
                        className="px-3 py-1 rounded text-xs"
                        style={{
                          background: s.is_active ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)",
                          color: s.is_active ? "var(--red)" : "var(--green)",
                        }}>
                        {s.is_active ? "비활성화" : "활성화"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "payments" && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>지갑</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>봇</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>금액</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>네트워크</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>TX Hash</th>
                <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>검증일</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="p-3 font-mono text-xs">
                    {p.wallet_address ? `${p.wallet_address.slice(0, 6)}...${p.wallet_address.slice(-4)}` : "-"}
                  </td>
                  <td className="p-3">{p.bot_name || "-"}</td>
                  <td className="p-3">{p.amount} USDT</td>
                  <td className="p-3 text-xs uppercase">{p.network}</td>
                  <td className="p-3 font-mono text-xs">
                    <a href={`https://polygonscan.com/tx/${p.tx_hash}`} target="_blank" rel="noopener noreferrer"
                      style={{ color: "var(--blue)" }}>
                      {p.tx_hash.slice(0, 10)}...
                    </a>
                  </td>
                  <td className="p-3 text-xs">
                    {p.verified_at ? new Date(p.verified_at).toLocaleDateString("ko-KR") : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
