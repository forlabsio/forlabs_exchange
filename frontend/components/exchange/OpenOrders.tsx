"use client";
import { useEffect, useState } from "react";
import { useOrderStore } from "@/stores/orderStore";
import { useAuthStore } from "@/stores/authStore";

export default function OpenOrders() {
  const [tab, setTab] = useState<"open" | "history">("open");
  const { openOrders, orderHistory, fetchOpenOrders, fetchHistory, cancelOrder } = useOrderStore();
  const { token } = useAuthStore();

  useEffect(() => {
    if (!token) return;
    fetchOpenOrders().catch(() => {});
    fetchHistory().catch(() => {});
  }, [token]);

  const orders = tab === "open" ? openOrders : orderHistory;

  return (
    <div className="h-full flex flex-col text-xs">
      <div className="flex border-b flex-shrink-0" style={{ borderColor: "var(--border)" }}>
        {(["open", "history"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className="px-4 py-2 border-b-2 transition-colors"
            style={{
              borderBottomColor: tab === t ? "var(--blue)" : "transparent",
              color: tab === t ? "var(--text-primary)" : "var(--text-secondary)",
            }}>
            {t === "open" ? "미체결 주문" : "주문 내역"}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-x-auto overflow-y-auto">
        {!token ? (
          <div className="px-3 py-4 text-center" style={{ color: "var(--text-secondary)" }}>
            로그인 후 이용 가능합니다
          </div>
        ) : orders.length === 0 ? (
          <div className="px-3 py-4 text-center" style={{ color: "var(--text-secondary)" }}>
            주문 없음
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr style={{ color: "var(--text-secondary)" }}>
                <th className="text-left px-3 py-2">페어</th>
                <th className="text-left px-3 py-2">방향</th>
                <th className="text-left px-3 py-2">유형</th>
                <th className="text-left px-3 py-2">가격</th>
                <th className="text-left px-3 py-2">수량</th>
                {tab === "history" && <th className="text-left px-3 py-2">상태</th>}
                {tab === "open" && <th className="text-left px-3 py-2">취소</th>}
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} style={{ borderTop: "1px solid var(--border)", color: "var(--text-primary)" }}>
                  <td className="px-3 py-1.5">{o.pair?.replace("_", "/")}</td>
                  <td className="px-3 py-1.5" style={{ color: o.side === "buy" ? "var(--green)" : "var(--red)" }}>
                    {o.side === "buy" ? "매수" : "매도"}
                  </td>
                  <td className="px-3 py-1.5">{o.type === "limit" ? "지정가" : "시장가"}</td>
                  <td className="px-3 py-1.5 font-mono">
                    {o.price ? parseFloat(o.price).toLocaleString() : "시장가"}
                  </td>
                  <td className="px-3 py-1.5 font-mono">{parseFloat(o.quantity).toFixed(5)}</td>
                  {tab === "history" && <td className="px-3 py-1.5">{o.status}</td>}
                  {tab === "open" && (
                    <td className="px-3 py-1.5">
                      <button onClick={() => cancelOrder(o.id).then(() => fetchOpenOrders())}
                        className="px-2 py-0.5 rounded"
                        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                        취소
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
