"use client";
import { useState } from "react";
import { useMarketStore } from "@/stores/marketStore";
import styles from "./Orderbook.module.css";

type Tab = "orderbook" | "trades";

export default function Orderbook() {
  const [activeTab, setActiveTab] = useState<Tab>("orderbook");
  const { orderbook, ticker, trades } = useMarketStore();

  // ── Order Book data ────────────────────────────────────────────
  const rawAsks = orderbook.asks || [];
  const rawBids = orderbook.bids || [];

  // Top 8 asks sorted descending (highest price at top)
  const asks = [...rawAsks]
    .slice(0, 8)
    .sort((a, b) => parseFloat(b[0]) - parseFloat(a[0]));

  // Top 8 bids sorted descending (highest bid first)
  const bids = [...rawBids]
    .slice(0, 8)
    .sort((a, b) => parseFloat(b[0]) - parseFloat(a[0]));

  const maxAskQty = asks.reduce((m, [, q]) => Math.max(m, parseFloat(q)), 0);
  const maxBidQty = bids.reduce((m, [, q]) => Math.max(m, parseFloat(q)), 0);

  const lowestAsk = asks.length > 0 ? parseFloat(asks[asks.length - 1][0]) : 0;
  const highestBid = bids.length > 0 ? parseFloat(bids[0][0]) : 0;
  const spread = lowestAsk > 0 && highestBid > 0 ? (lowestAsk - highestBid).toFixed(2) : null;

  const lastPrice = ticker ? parseFloat(ticker.last_price) : null;
  const changePct = ticker ? parseFloat(ticker.change_pct) : 0;
  const midPriceColor = changePct >= 0 ? "var(--green)" : "var(--red)";

  const askVol = asks.reduce((s, [, q]) => s + parseFloat(q), 0);
  const bidVol = bids.reduce((s, [, q]) => s + parseFloat(q), 0);
  const totalVol = bidVol + askVol;
  const bidPct = totalVol > 0 ? (bidVol / totalVol) * 100 : 50;
  const askPct = 100 - bidPct;

  return (
    <div className={`h-full flex flex-col text-xs ${styles.wrapper}`}>

      {/* ── Tab bar ─────────────────────────────────────────────── */}
      <div className={`flex flex-shrink-0 ${styles.tabBar}`}>
        {(["orderbook", "trades"] as Tab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`${styles.tab} ${activeTab === tab ? styles.tabActive : ""}`}
          >
            {tab === "orderbook" ? "Order Book" : "Recent Trades"}
          </button>
        ))}
      </div>

      {/* ── Order Book tab ───────────────────────────────────────── */}
      {activeTab === "orderbook" && (
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Header */}
          <div className={`flex justify-between px-3 py-1.5 font-medium flex-shrink-0 ${styles.header}`}>
            <span>Price(USDT)</span>
            <span>Amount(BTC)</span>
            <span>Total</span>
          </div>

          {/* Asks */}
          <div className="flex flex-col flex-shrink-0">
            {asks.map(([price, qty], i) => {
              const p = parseFloat(price);
              const q = parseFloat(qty);
              const barWidth = maxAskQty > 0 ? `${((q / maxAskQty) * 100).toFixed(1)}%` : "0%";
              return (
                <div
                  key={i}
                  className="relative flex justify-between px-3 py-0.5 font-mono hover:bg-[var(--bg-panel)]"
                >
                  {/* depth bar — dynamic width, must stay inline */}
                  <div className={styles.askBar} style={{ width: barWidth }} />
                  <span className={styles.askPrice}>{p.toLocaleString()}</span>
                  <span className={styles.rowQty}>{q.toFixed(4)}</span>
                  <span className={styles.rowTotal}>{(p * q).toFixed(2)}</span>
                </div>
              );
            })}
          </div>

          {/* Mid-price / spread */}
          <div className={`flex items-center justify-between px-3 py-2 flex-shrink-0 ${styles.midRow}`}>
            <span className={styles.midPrice} style={{ color: midPriceColor }}>
              {lastPrice !== null ? lastPrice.toLocaleString() : "--"}
              {changePct >= 0 ? " ▲" : " ▼"}
            </span>
            <span className={styles.spreadLabel}>
              Spread: {spread ?? "--"}
            </span>
          </div>

          {/* Bids */}
          <div className="flex flex-col flex-shrink-0">
            {bids.map(([price, qty], i) => {
              const p = parseFloat(price);
              const q = parseFloat(qty);
              const barWidth = maxBidQty > 0 ? `${((q / maxBidQty) * 100).toFixed(1)}%` : "0%";
              return (
                <div
                  key={i}
                  className="relative flex justify-between px-3 py-0.5 font-mono hover:bg-[var(--bg-panel)]"
                >
                  {/* depth bar — dynamic width, must stay inline */}
                  <div className={styles.bidBar} style={{ width: barWidth }} />
                  <span className={styles.bidPrice}>{p.toLocaleString()}</span>
                  <span className={styles.rowQty}>{q.toFixed(4)}</span>
                  <span className={styles.rowTotal}>{(p * q).toFixed(2)}</span>
                </div>
              );
            })}
          </div>

          <div className="flex-1" />

          {/* Bid / Ask volume bar */}
          <div className={`flex-shrink-0 px-3 py-2 ${styles.volBarWrapper}`}>
            <div className={`flex ${styles.volTrack}`}>
              {/* dynamic widths must stay inline */}
              <div className={styles.volBidSegment} style={{ width: `${bidPct.toFixed(1)}%` }} />
              <div className={styles.volAskSegment} style={{ width: `${askPct.toFixed(1)}%` }} />
            </div>
            <div className={`flex justify-between ${styles.volLabels}`}>
              <span className={styles.volBidLabel}>Bid {bidPct.toFixed(1)}%</span>
              <span className={styles.volAskLabel}>Ask {askPct.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* ── Recent Trades tab ────────────────────────────────────── */}
      {activeTab === "trades" && (
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Header */}
          <div className={`flex justify-between px-3 py-1.5 font-medium flex-shrink-0 ${styles.header}`}>
            <span>Price</span>
            <span>Amount</span>
            <span>Time</span>
          </div>

          <div className="flex-1 overflow-y-auto">
            {trades.slice(0, 30).map((t, i) => (
              <div
                key={i}
                className={`flex justify-between px-3 py-0.5 font-mono ${t.is_buyer_maker ? styles.tradesSellPrice : styles.tradesBuyPrice}`}
              >
                <span>{parseFloat(t.price).toLocaleString()}</span>
                <span>{parseFloat(t.qty).toFixed(4)}</span>
                <span>
                  {new Date(t.time).toLocaleTimeString("en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>
              </div>
            ))}
            {trades.length === 0 && (
              <div className={`px-3 py-4 text-center ${styles.tradesEmpty}`}>
                Loading data...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
