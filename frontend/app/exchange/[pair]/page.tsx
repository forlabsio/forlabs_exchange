"use client";
import { useEffect } from "react";
import { use } from "react";
import { useMarketStore } from "@/stores/marketStore";
import PairList from "@/components/exchange/PairList";
import Orderbook from "@/components/exchange/Orderbook";
import RecentTrades from "@/components/exchange/RecentTrades";
import OpenOrders from "@/components/exchange/OpenOrders";
import dynamic from "next/dynamic";
import OrderForm from "@/components/exchange/OrderForm";

const ChartWidget = dynamic(() => import("@/components/exchange/ChartWidget"), { ssr: false });

export default function ExchangePage({ params }: { params: Promise<{ pair: string }> }) {
  const { pair } = use(params);
  const { connect, disconnect, ticker } = useMarketStore();

  useEffect(() => {
    connect(pair);
    return () => disconnect();
  }, [pair]);

  return (
    <div className="flex" style={{ height: "calc(100vh - 56px)", background: "var(--bg-primary)" }}>
      {/* Left: Pair List */}
      <div className="w-52 border-r flex-shrink-0" style={{ borderColor: "var(--border)" }}>
        <PairList currentPair={pair} />
      </div>

      {/* Center: Chart + Order Form + Open Orders */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Ticker bar */}
        <div className="flex items-center gap-6 px-4 py-2 border-b flex-shrink-0 text-sm"
          style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
          <span className="font-bold text-base">{pair.replace("_", "/")}</span>
          {ticker ? (
            <>
              <span className="text-xl font-mono font-bold"
                style={{ color: parseFloat(ticker.change_pct) >= 0 ? "var(--green)" : "var(--red)" }}>
                {parseFloat(ticker.last_price).toLocaleString()}
              </span>
              <span style={{ color: parseFloat(ticker.change_pct) >= 0 ? "var(--green)" : "var(--red)" }}>
                {parseFloat(ticker.change_pct) >= 0 ? "+" : ""}{ticker.change_pct}%
              </span>
              <span style={{ color: "var(--text-secondary)" }}>고: {parseFloat(ticker.high).toLocaleString()}</span>
              <span style={{ color: "var(--text-secondary)" }}>저: {parseFloat(ticker.low).toLocaleString()}</span>
              <span style={{ color: "var(--text-secondary)" }}>거래량: {parseFloat(ticker.volume).toLocaleString()}</span>
            </>
          ) : (
            <span style={{ color: "var(--text-secondary)" }}>연결 중...</span>
          )}
        </div>

        {/* Chart */}
        <div className="flex-1 min-h-0">
          <ChartWidget pair={pair} />
        </div>

        {/* Order Form */}
        <div className="flex-shrink-0 border-t" style={{ borderColor: "var(--border)", height: "220px" }}>
          <OrderForm pair={pair} />
        </div>

        {/* Open Orders */}
        <div className="flex-shrink-0 border-t" style={{ borderColor: "var(--border)", height: "180px" }}>
          <OpenOrders />
        </div>
      </div>

      {/* Right: Orderbook + Trades */}
      <div className="w-64 border-l flex flex-col flex-shrink-0" style={{ borderColor: "var(--border)" }}>
        <div style={{ flex: "1 1 60%", minHeight: 0, overflow: "hidden" }}>
          <Orderbook />
        </div>
        <div className="border-t flex-shrink-0" style={{ borderColor: "var(--border)", height: "200px" }}>
          <RecentTrades />
        </div>
      </div>
    </div>
  );
}
