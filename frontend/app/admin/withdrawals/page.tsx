"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { apiFetch } from "@/lib/api";

interface WithdrawalItem {
  id: number;
  user_id: number;
  wallet_address: string | null;
  amount: number;
  to_address: string;
  network: string;
  status: string;
  tx_hash: string | null;
  admin_note: string | null;
  created_at: string | null;
  processed_at: string | null;
}

interface WithdrawalStats {
  pending_count: number;
  pending_amount_usdt: number;
  completed_count: number;
  completed_amount_usdt: number;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: "대기중", color: "#f59e0b", bg: "rgba(245,158,11,0.15)" },
  completed: { label: "완료", color: "var(--green)", bg: "rgba(34,197,94,0.15)" },
  rejected: { label: "거절", color: "var(--red)", bg: "rgba(239,68,68,0.15)" },
  approved: { label: "승인", color: "var(--blue)", bg: "rgba(59,130,246,0.15)" },
};

function ApproveModal({
  withdrawal,
  onClose,
  onDone,
}: {
  withdrawal: WithdrawalItem;
  onClose: () => void;
  onDone: () => void;
}) {
  const [txHash, setTxHash] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleApprove = async () => {
    if (!txHash.startsWith("0x")) {
      alert("유효한 TX Hash를 입력하세요");
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch(`/api/admin/withdrawals/${withdrawal.id}/approve`, {
        method: "PUT",
        body: JSON.stringify({ tx_hash: txHash, note }),
      });
      onDone();
    } catch (e) {
      alert(e instanceof Error ? e.message : "승인 실패");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!confirm("정말 거절하시겠습니까?")) return;
    setSubmitting(true);
    try {
      await apiFetch(`/api/admin/withdrawals/${withdrawal.id}/reject`, {
        method: "PUT",
        body: JSON.stringify({ note }),
      });
      onDone();
    } catch (e) {
      alert(e instanceof Error ? e.message : "거절 실패");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-lg rounded-2xl p-6" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>출금 요청 처리</h2>

        <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: "var(--bg-base)" }}>
          <div className="flex justify-between mb-2">
            <span style={{ color: "var(--text-secondary)" }}>요청자</span>
            <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>
              {withdrawal.wallet_address || `User #${withdrawal.user_id}`}
            </span>
          </div>
          <div className="flex justify-between mb-2">
            <span style={{ color: "var(--text-secondary)" }}>출금 금액</span>
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{withdrawal.amount.toFixed(2)} USDT</span>
          </div>
          <div className="flex justify-between mb-2">
            <span style={{ color: "var(--text-secondary)" }}>수신 주소</span>
            <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>{withdrawal.to_address}</span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: "var(--text-secondary)" }}>네트워크</span>
            <span className="uppercase text-xs" style={{ color: "var(--text-primary)" }}>{withdrawal.network}</span>
          </div>
        </div>

        <div className="flex flex-col gap-3 mb-4">
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>
              TX Hash (Polygon USDT 전송 후 입력)
            </label>
            <input
              type="text" value={txHash} placeholder="0x..."
              onChange={(e) => setTxHash(e.target.value)}
              className="w-full px-3 py-2 rounded text-sm font-mono outline-none"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>관리자 메모 (선택)</label>
            <input
              type="text" value={note} placeholder="메모 입력..."
              onChange={(e) => setNote(e.target.value)}
              className="w-full px-3 py-2 rounded text-sm outline-none"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
        </div>

        <div className="flex gap-3">
          <button type="button" onClick={onClose} className="flex-1 py-2 rounded text-sm"
            style={{ background: "var(--bg-base)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
            취소
          </button>
          <button type="button" onClick={handleReject} disabled={submitting}
            className="px-4 py-2 rounded text-sm font-medium"
            style={{ background: "rgba(239,68,68,0.2)", color: "var(--red)" }}>
            거절
          </button>
          <button type="button" onClick={handleApprove} disabled={submitting || !txHash}
            className="flex-1 py-2 rounded text-sm font-medium text-white"
            style={{ background: submitting || !txHash ? "#666" : "var(--green)" }}>
            {submitting ? "처리중..." : "승인 (전송 완료)"}
          </button>
        </div>

        <p className="text-xs mt-3 text-center" style={{ color: "var(--text-secondary)" }}>
          Polygon 네트워크에서 USDT를 수신 주소로 먼저 전송한 후, TX Hash를 입력하고 승인하세요.
        </p>
      </div>
    </div>
  );
}

export default function AdminWithdrawalsPage() {
  const { user, hydrate } = useAuthStore();
  const router = useRouter();
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState<WithdrawalItem[]>([]);
  const [stats, setStats] = useState<WithdrawalStats | null>(null);
  const [selected, setSelected] = useState<WithdrawalItem | null>(null);

  useEffect(() => { hydrate(); }, []);

  const fetchData = async () => {
    try {
      const [wData, sData] = await Promise.all([
        apiFetch(`/api/admin/withdrawals?status=${filter}`),
        apiFetch("/api/admin/withdrawals/stats"),
      ]);
      setItems(wData);
      setStats(sData);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    if (user && user.role !== "admin") router.push("/exchange/BTC_USDT");
    if (user?.role === "admin") fetchData();
  }, [user, filter]);

  if (!user || user.role !== "admin") {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "var(--text-secondary)" }}>
        접근 권한이 없습니다.
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" style={{ color: "var(--text-primary)" }}>
      <h1 className="text-2xl font-bold mb-6">출금 관리</h1>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>대기 건수</p>
            <p className="text-2xl font-bold" style={{ color: "#f59e0b" }}>{stats.pending_count}</p>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>대기 금액</p>
            <p className="text-2xl font-bold" style={{ color: "#f59e0b" }}>{stats.pending_amount_usdt.toFixed(2)}</p>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>완료 건수</p>
            <p className="text-2xl font-bold" style={{ color: "var(--green)" }}>{stats.completed_count}</p>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>총 출금액</p>
            <p className="text-2xl font-bold" style={{ color: "var(--green)" }}>{stats.completed_amount_usdt.toFixed(2)}</p>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        {[
          { value: "all", label: "전체" },
          { value: "pending", label: "대기중" },
          { value: "completed", label: "완료" },
          { value: "rejected", label: "거절" },
        ].map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            className="px-4 py-2 rounded text-sm font-medium"
            style={{
              background: filter === f.value ? "var(--blue)" : "var(--bg-panel)",
              color: filter === f.value ? "#fff" : "var(--text-secondary)",
            }}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>ID</th>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>요청자</th>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>금액</th>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>수신 주소</th>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>상태</th>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>TX Hash</th>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>요청일</th>
              <th className="text-left p-3" style={{ color: "var(--text-secondary)" }}>액션</th>
            </tr>
          </thead>
          <tbody>
            {items.map((w) => {
              const st = STATUS_CONFIG[w.status] || { label: w.status, color: "var(--text-secondary)", bg: "transparent" };
              return (
                <tr key={w.id} style={{
                  borderBottom: "1px solid var(--border)",
                  background: w.status === "pending" ? "rgba(245,158,11,0.05)" : undefined,
                }}>
                  <td className="p-3">#{w.id}</td>
                  <td className="p-3 font-mono text-xs">
                    {w.wallet_address ? `${w.wallet_address.slice(0, 6)}...${w.wallet_address.slice(-4)}` : `-`}
                  </td>
                  <td className="p-3 font-semibold">{w.amount.toFixed(2)} USDT</td>
                  <td className="p-3 font-mono text-xs">
                    {w.to_address.slice(0, 8)}...{w.to_address.slice(-4)}
                  </td>
                  <td className="p-3">
                    <span className="px-2 py-1 rounded text-xs" style={{ background: st.bg, color: st.color }}>
                      {st.label}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-xs">
                    {w.tx_hash ? (
                      <a href={`https://polygonscan.com/tx/${w.tx_hash}`} target="_blank" rel="noopener noreferrer"
                        style={{ color: "var(--blue)" }}>
                        {w.tx_hash.slice(0, 10)}...
                      </a>
                    ) : "-"}
                  </td>
                  <td className="p-3 text-xs">
                    {w.created_at ? new Date(w.created_at).toLocaleDateString("ko-KR") : "-"}
                  </td>
                  <td className="p-3">
                    {w.status === "pending" ? (
                      <button
                        type="button"
                        onClick={() => setSelected(w)}
                        className="px-3 py-1 rounded text-xs font-medium"
                        style={{ background: "rgba(59,130,246,0.2)", color: "var(--blue)" }}>
                        처리
                      </button>
                    ) : (
                      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                        {w.admin_note || "처리됨"}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={8} className="p-8 text-center" style={{ color: "var(--text-secondary)" }}>
                  출금 요청이 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Approve/Reject modal */}
      {selected && (
        <ApproveModal
          withdrawal={selected}
          onClose={() => setSelected(null)}
          onDone={() => { setSelected(null); fetchData(); }}
        />
      )}
    </div>
  );
}
