"use client";
import { useState, useEffect } from "react";
import { useMarketStore } from "@/stores/marketStore";
import { useOrderStore } from "@/stores/orderStore";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import styles from "./OrderForm.module.css";

type Side = "buy" | "sell";
type OType = "limit" | "market";

export default function OrderForm({ pair }: { pair: string }) {
  const [side, setSide] = useState<Side>("buy");
  const [orderType, setOrderType] = useState<OType>("limit");
  const [price, setPrice] = useState("");
  const [amount, setAmount] = useState("");
  const [total, setTotal] = useState("");
  const [pct, setPct] = useState(0);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const { ticker } = useMarketStore();
  const { placeOrder, fetchOpenOrders } = useOrderStore();
  const { token } = useAuthStore();
  const router = useRouter();

  const baseAsset = pair.split("_")[0];
  const quoteAsset = pair.split("_")[1] ?? "USDT";

  // Reset form when side changes
  useEffect(() => {
    setPrice("");
    setAmount("");
    setTotal("");
    setPct(0);
    setMsg(null);
  }, [side]);

  // Clear price + total when switching to market order
  useEffect(() => {
    setPrice("");
    setTotal("");
  }, [orderType]);

  /* ── Helpers ── */
  const parseNum = (s: string): number | null => {
    const n = parseFloat(s);
    return isNaN(n) ? null : n;
  };

  /* ── Recalculation handlers ── */
  const handlePriceChange = (val: string) => {
    setPrice(val);
    const p = parseNum(val);
    const a = parseNum(amount);
    if (p !== null && a !== null) {
      setTotal((p * a).toFixed(2));
    } else {
      setTotal("");
    }
  };

  const handleAmountChange = (val: string) => {
    setAmount(val);
    const a = parseNum(val);
    const p = orderType === "limit" ? parseNum(price) : null;
    if (a !== null && p !== null) {
      setTotal((p * a).toFixed(2));
    } else {
      setTotal("");
    }
    setPct(0);
  };

  const handleTotalChange = (val: string) => {
    setTotal(val);
    const t = parseNum(val);
    const p = orderType === "limit" ? parseNum(price) : null;
    if (t !== null && p !== null && p > 0) {
      setAmount((t / p).toFixed(6));
    } else {
      setAmount("");
    }
  };

  const handleSliderChange = (val: number) => {
    setPct(val);
    const p =
      orderType === "limit"
        ? parseNum(price)
        : parseNum(ticker?.last_price ?? "");
    if (p !== null && p > 0 && val > 0) {
      // Placeholder available: 10 000 USDT (buy) or 1 base asset (sell)
      const available = side === "buy" ? 10000 : 1;
      if (side === "buy") {
        const newTotal = ((val / 100) * available).toFixed(2);
        const newAmount = (parseFloat(newTotal) / p).toFixed(6);
        setTotal(newTotal);
        setAmount(newAmount);
      } else {
        const newAmount = ((val / 100) * available).toFixed(6);
        const newTotal = (parseFloat(newAmount) * p).toFixed(2);
        setAmount(newAmount);
        setTotal(newTotal);
      }
    } else if (val === 0) {
      setAmount("");
      setTotal("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) { router.push("/login"); return; }
    setLoading(true);
    setMsg(null);
    try {
      await placeOrder({
        pair,
        side,
        type: orderType,
        quantity: parseFloat(amount),
        price: orderType === "limit" ? parseFloat(price) : undefined,
      });
      setMsg({ text: "Order placed successfully.", ok: true });
      setAmount("");
      setTotal("");
      setPct(0);
      await fetchOpenOrders();
    } catch (err: unknown) {
      setMsg({
        text: "Order failed: " + (err instanceof Error ? err.message : String(err)),
        ok: false,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.wrapper}>

      {/* ── Side tabs: Buy / Sell ── */}
      <div className={styles.sideTabs}>
        {(["buy", "sell"] as Side[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSide(s)}
            className={styles.sideTab}
            data-side={s}
            data-active={side === s ? "true" : "false"}
          >
            {s === "buy" ? "Buy" : "Sell"}
          </button>
        ))}
      </div>

      {/* ── Order type: Limit / Market ── */}
      <div className={styles.typeTabs}>
        {(["limit", "market"] as OType[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setOrderType(t)}
            className={
              orderType === t
                ? `${styles.typeTab} ${styles.typeTabActive}`
                : styles.typeTab
            }
          >
            {t === "limit" ? "Limit" : "Market"}
          </button>
        ))}
      </div>

      {/* ── Form body ── */}
      <form onSubmit={handleSubmit} className={styles.formBody}>

        {/* Available balance */}
        <div className={styles.available}>
          <span>Available</span>
          <span className={styles.availableValue}>
            -- {side === "buy" ? quoteAsset : baseAsset}
          </span>
        </div>

        {/* Price input – hidden for market orders */}
        {orderType === "limit" && (
          <div className={styles.field}>
            <label className={styles.label}>
              Price ({quoteAsset})
            </label>
            <input
              type="number"
              value={price}
              onChange={(e) => handlePriceChange(e.target.value)}
              placeholder={ticker?.last_price ?? "0.00"}
              step="0.01"
              min="0"
              className={styles.input}
            />
          </div>
        )}

        {/* Amount input */}
        <div className={styles.field}>
          <label className={styles.label}>
            Amount ({baseAsset})
          </label>
          <input
            type="number"
            value={amount}
            onChange={(e) => handleAmountChange(e.target.value)}
            placeholder="0.00000"
            step="0.00001"
            min="0"
            className={styles.input}
          />
        </div>

        {/* Slider */}
        <div className={styles.sliderWrapper} data-side={side}>
          <input
            type="range"
            min={0}
            max={100}
            step={25}
            value={pct}
            onChange={(e) => handleSliderChange(Number(e.target.value))}
            className={styles.slider}
            aria-label="Order amount percentage"
          />
          <div className={styles.sliderLabels}>
            {[0, 25, 50, 75, 100].map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => handleSliderChange(p)}
                className={styles.sliderPct}
                data-active={pct === p ? "true" : "false"}
              >
                {p}%
              </button>
            ))}
          </div>
        </div>

        {/* Total input */}
        <div className={styles.field}>
          <label className={styles.label}>
            Total ({quoteAsset})
          </label>
          <input
            type="number"
            value={total}
            onChange={(e) => handleTotalChange(e.target.value)}
            placeholder="0.00"
            step="0.01"
            min="0"
            readOnly={orderType === "market"}
            className={
              orderType === "market"
                ? `${styles.input} ${styles.inputReadonly}`
                : styles.input
            }
          />
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={loading}
          className={
            side === "buy"
              ? `${styles.submitBtn} ${styles.submitBtnBuy}`
              : `${styles.submitBtn} ${styles.submitBtnSell}`
          }
        >
          {loading
            ? "Placing..."
            : `${side === "buy" ? "Buy" : "Sell"} ${baseAsset}`}
        </button>

        {/* Feedback message */}
        {msg && (
          <p className={msg.ok ? styles.msgOk : styles.msgErr}>
            {msg.text}
          </p>
        )}
      </form>
    </div>
  );
}
