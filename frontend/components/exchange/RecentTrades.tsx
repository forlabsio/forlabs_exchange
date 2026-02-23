"use client";
import { useMarketStore } from "@/stores/marketStore";

export default function RecentTrades() {
  const { trades } = useMarketStore();

  return (
    <div className="h-full flex flex-col text-xs">
      <div className="flex justify-between px-3 py-1.5 border-b font-medium flex-shrink-0"
        style={{ color: "var(--text-secondary)", borderColor: "var(--border)" }}>
        <span>가격</span><span>수량</span><span>시간</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {trades.slice(0, 30).map((t, i) => (
          <div key={i} className="flex justify-between px-3 py-0.5 font-mono"
            style={{ color: t.is_buyer_maker ? "var(--red)" : "var(--green)" }}>
            <span>{parseFloat(t.price).toLocaleString()}</span>
            <span>{parseFloat(t.qty).toFixed(4)}</span>
            <span>{new Date(t.time).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
          </div>
        ))}
        {trades.length === 0 && (
          <div className="px-3 py-4 text-center" style={{ color: "var(--text-secondary)" }}>
            데이터 로딩 중...
          </div>
        )}
      </div>
    </div>
  );
}
