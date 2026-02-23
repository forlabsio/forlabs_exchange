"use client";
import Link from "next/link";

const PAIRS = ["BTC_USDT", "ETH_USDT", "BNB_USDT", "SOL_USDT"];

export default function PairList({ currentPair }: { currentPair: string }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="px-3 py-2 text-xs font-semibold border-b sticky top-0"
        style={{ color: "var(--text-secondary)", borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        USDT 마켓
      </div>
      {PAIRS.map((pair) => (
        <Link key={pair} href={`/exchange/${pair}`}
          className="flex items-center justify-between px-3 py-2.5 text-sm transition-colors"
          style={{
            color: pair === currentPair ? "var(--text-primary)" : "var(--text-secondary)",
            background: pair === currentPair ? "var(--bg-panel)" : "transparent",
          }}>
          <span className="font-medium">{pair.replace("_", "/")}</span>
        </Link>
      ))}
    </div>
  );
}
