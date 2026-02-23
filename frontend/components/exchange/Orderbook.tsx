"use client";
import { useMarketStore } from "@/stores/marketStore";

export default function Orderbook() {
  const { orderbook, ticker } = useMarketStore();
  const asks = [...(orderbook.asks || [])].slice(0, 15).reverse();
  const bids = (orderbook.bids || []).slice(0, 15);

  return (
    <div className="h-full flex flex-col text-xs">
      <div className="flex justify-between px-3 py-1.5 border-b font-medium flex-shrink-0"
        style={{ color: "var(--text-secondary)", borderColor: "var(--border)" }}>
        <span>가격 (USDT)</span><span>수량</span><span>합계</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {asks.map(([price, qty], i) => (
          <div key={i} className="flex justify-between px-3 py-0.5 font-mono hover:bg-[var(--bg-panel)]"
            style={{ color: "var(--red)" }}>
            <span>{parseFloat(price).toLocaleString()}</span>
            <span>{parseFloat(qty).toFixed(4)}</span>
            <span>{(parseFloat(price) * parseFloat(qty)).toFixed(2)}</span>
          </div>
        ))}
        <div className="flex items-center justify-center py-2 font-bold text-sm border-y flex-shrink-0"
          style={{ borderColor: "var(--border)", color: "var(--text-primary)", background: "var(--bg-panel)" }}>
          {ticker ? parseFloat(ticker.last_price).toLocaleString() : "--"}
        </div>
        {bids.map(([price, qty], i) => (
          <div key={i} className="flex justify-between px-3 py-0.5 font-mono hover:bg-[var(--bg-panel)]"
            style={{ color: "var(--green)" }}>
            <span>{parseFloat(price).toLocaleString()}</span>
            <span>{parseFloat(qty).toFixed(4)}</span>
            <span>{(parseFloat(price) * parseFloat(qty)).toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
