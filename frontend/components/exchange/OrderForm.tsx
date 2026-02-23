"use client";
import { useState } from "react";
import { useMarketStore } from "@/stores/marketStore";
import { useOrderStore } from "@/stores/orderStore";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

type Side = "buy" | "sell";
type OType = "limit" | "market";

export default function OrderForm({ pair }: { pair: string }) {
  const [side, setSide] = useState<Side>("buy");
  const [orderType, setOrderType] = useState<OType>("limit");
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [pct, setPct] = useState(0);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const { ticker } = useMarketStore();
  const { placeOrder, fetchOpenOrders } = useOrderStore();
  const { token } = useAuthStore();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent, submitSide: Side) => {
    e.preventDefault();
    if (!token) { router.push("/login"); return; }
    setLoading(true);
    setMsg("");
    try {
      await placeOrder({
        pair,
        side: submitSide,
        type: orderType,
        quantity: parseFloat(quantity),
        price: orderType === "limit" ? parseFloat(price) : undefined,
      });
      setMsg("주문이 완료되었습니다.");
      setQuantity("");
      setPct(0);
      await fetchOpenOrders();
    } catch (err: unknown) {
      setMsg("주문 실패: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Order type tabs */}
      <div className="flex border-b flex-shrink-0" style={{ borderColor: "var(--border)" }}>
        {(["limit", "market"] as OType[]).map((t) => (
          <button key={t} onClick={() => setOrderType(t)}
            className="px-4 py-2 text-xs border-b-2 transition-colors"
            style={{
              borderBottomColor: orderType === t ? "var(--blue)" : "transparent",
              color: orderType === t ? "var(--text-primary)" : "var(--text-secondary)",
            }}>
            {t === "limit" ? "지정가" : "시장가"}
          </button>
        ))}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Buy form */}
        <form onSubmit={(e) => handleSubmit(e, "buy")}
          className="flex-1 p-3 border-r flex flex-col gap-2"
          style={{ borderColor: "var(--border)" }}>
          {orderType === "limit" && (
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>가격 (USDT)</label>
              <input type="number" value={price} onChange={e => setPrice(e.target.value)}
                placeholder={ticker?.last_price || "0"} step="0.01"
                className="w-full px-3 py-1.5 rounded text-xs outline-none"
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
            </div>
          )}
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>수량</label>
            <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)}
              placeholder="0.00000" step="0.00001" min="0"
              className="w-full px-3 py-1.5 rounded text-xs outline-none"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </div>
          <div>
            <input type="range" min={0} max={100} step={25} value={pct}
              onChange={e => setPct(Number(e.target.value))}
              className="w-full" style={{ accentColor: "var(--green)" }} />
            <div className="flex justify-between text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
              {[0, 25, 50, 75, 100].map(p => <span key={p}>{p}%</span>)}
            </div>
          </div>
          <button type="submit" disabled={loading} onClick={() => setSide("buy")}
            className="w-full py-2 rounded font-semibold text-white text-sm mt-auto"
            style={{ background: "var(--green)", opacity: loading ? 0.7 : 1 }}>
            매수
          </button>
          {msg && side === "buy" && (
            <p className="text-xs text-center" style={{ color: msg.includes("실패") ? "var(--red)" : "var(--green)" }}>{msg}</p>
          )}
        </form>

        {/* Sell form */}
        <form onSubmit={(e) => handleSubmit(e, "sell")}
          className="flex-1 p-3 flex flex-col gap-2">
          {orderType === "limit" && (
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>가격 (USDT)</label>
              <input type="number" value={price} onChange={e => setPrice(e.target.value)}
                placeholder={ticker?.last_price || "0"} step="0.01"
                className="w-full px-3 py-1.5 rounded text-xs outline-none"
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
            </div>
          )}
          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-secondary)" }}>수량</label>
            <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)}
              placeholder="0.00000" step="0.00001" min="0"
              className="w-full px-3 py-1.5 rounded text-xs outline-none"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </div>
          <div>
            <input type="range" min={0} max={100} step={25} value={pct}
              onChange={e => setPct(Number(e.target.value))}
              className="w-full" style={{ accentColor: "var(--red)" }} />
            <div className="flex justify-between text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
              {[0, 25, 50, 75, 100].map(p => <span key={p}>{p}%</span>)}
            </div>
          </div>
          <button type="submit" disabled={loading} onClick={() => setSide("sell")}
            className="w-full py-2 rounded font-semibold text-white text-sm mt-auto"
            style={{ background: "var(--red)", opacity: loading ? 0.7 : 1 }}>
            매도
          </button>
          {msg && side === "sell" && (
            <p className="text-xs text-center" style={{ color: msg.includes("실패") ? "var(--red)" : "var(--green)" }}>{msg}</p>
          )}
        </form>
      </div>
    </div>
  );
}
