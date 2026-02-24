# Chart Indicators Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all 12 chart indicators (MA, EMA, BOLL, SAR, VOL, MACD, RSI, KDJ, WR, DMI, CCI, OBV) in ChartWidget using lightweight-charts v5 panes.

**Architecture:** Pure calculation functions in `lib/indicators.ts`. ChartWidget stores raw kline data in a ref and calls `syncIndicators()` whenever kline data loads or active indicators change. Overlay indicators (MA, EMA, BOLL, SAR) render in the main pane (pane 0); oscillators (VOL, MACD, RSI, KDJ, WR, DMI, CCI, OBV) each get a dedicated sub-pane created with `chart.addPane()` on activation and removed with `chart.removePane()` on deactivation.

**Tech Stack:** Next.js 16, React 19, lightweight-charts v5.1, TypeScript

---

### Task 1: Create `lib/indicators.ts` — pure calculation functions

**Files:**
- Create: `lib/indicators.ts`

No tests for pure math functions (they'd just duplicate the math). Implement and verify with console.log in browser.

**Step 1: Create the file**

```typescript
// lib/indicators.ts

export interface KlinePoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ── Overlay indicators (main pane) ──────────────────────────────

/** Simple Moving Average */
export function calcMA(
  data: KlinePoint[],
  period: number
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

/** Exponential Moving Average */
export function calcEMA(
  data: KlinePoint[],
  period: number
): { time: number; value: number }[] {
  if (data.length < period) return [];
  const k = 2 / (period + 1);
  const result: { time: number; value: number }[] = [];
  let ema = data.slice(0, period).reduce((s, d) => s + d.close, 0) / period;
  result.push({ time: data[period - 1].time, value: ema });
  for (let i = period; i < data.length; i++) {
    ema = data[i].close * k + ema * (1 - k);
    result.push({ time: data[i].time, value: ema });
  }
  return result;
}

/** Bollinger Bands */
export function calcBOLL(
  data: KlinePoint[],
  period = 20,
  mult = 2
): { time: number; upper: number; middle: number; lower: number }[] {
  const result: { time: number; upper: number; middle: number; lower: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1).map((d) => d.close);
    const mean = slice.reduce((s, v) => s + v, 0) / period;
    const variance = slice.reduce((s, v) => s + (v - mean) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    result.push({
      time: data[i].time,
      upper: mean + mult * std,
      middle: mean,
      lower: mean - mult * std,
    });
  }
  return result;
}

/** Parabolic SAR */
export function calcSAR(
  data: KlinePoint[],
  step = 0.02,
  maxAF = 0.2
): { time: number; value: number }[] {
  if (data.length < 2) return [];
  const result: { time: number; value: number }[] = [];
  let bull = true;
  let af = step;
  let ep = data[0].high;
  let sar = data[0].low;

  for (let i = 1; i < data.length; i++) {
    const prevSar = sar;
    if (bull) {
      sar = prevSar + af * (ep - prevSar);
      sar = Math.min(sar, data[i - 1].low, i >= 2 ? data[i - 2].low : data[i - 1].low);
      if (data[i].low < sar) {
        bull = false;
        sar = ep;
        ep = data[i].low;
        af = step;
      } else {
        if (data[i].high > ep) {
          ep = data[i].high;
          af = Math.min(af + step, maxAF);
        }
      }
    } else {
      sar = prevSar + af * (ep - prevSar);
      sar = Math.max(sar, data[i - 1].high, i >= 2 ? data[i - 2].high : data[i - 1].high);
      if (data[i].high > sar) {
        bull = true;
        sar = ep;
        ep = data[i].high;
        af = step;
      } else {
        if (data[i].low < ep) {
          ep = data[i].low;
          af = Math.min(af + step, maxAF);
        }
      }
    }
    result.push({ time: data[i].time, value: sar });
  }
  return result;
}

// ── Sub-pane indicators ─────────────────────────────────────────

/** Volume with up/down color */
export function calcVOL(
  data: KlinePoint[]
): { time: number; value: number; color: string }[] {
  return data.map((d) => ({
    time: d.time,
    value: d.volume,
    color: d.close >= d.open ? "#0ecb81" : "#f6465d",
  }));
}

/** MACD (12/26/9) */
export function calcMACD(data: KlinePoint[]): {
  macd: { time: number; value: number }[];
  signal: { time: number; value: number }[];
  hist: { time: number; value: number; color: string }[];
} {
  const ema12 = calcEMA(data, 12);
  const ema26 = calcEMA(data, 26);
  // Align: ema26 starts at index 25, ema12 starts at index 11 of data
  // Both arrays are already aligned by time
  const macdRaw: { time: number; value: number }[] = [];
  const timeToEma12 = new Map(ema12.map((d) => [d.time, d.value]));
  for (const e26 of ema26) {
    const e12 = timeToEma12.get(e26.time);
    if (e12 !== undefined) {
      macdRaw.push({ time: e26.time, value: e12 - e26.value });
    }
  }

  // Signal = EMA9 of MACD
  const signalRaw: { time: number; value: number }[] = [];
  if (macdRaw.length >= 9) {
    const k = 2 / 10;
    let sigEma = macdRaw.slice(0, 9).reduce((s, d) => s + d.value, 0) / 9;
    signalRaw.push({ time: macdRaw[8].time, value: sigEma });
    for (let i = 9; i < macdRaw.length; i++) {
      sigEma = macdRaw[i].value * k + sigEma * (1 - k);
      signalRaw.push({ time: macdRaw[i].time, value: sigEma });
    }
  }

  const timeToSig = new Map(signalRaw.map((d) => [d.time, d.value]));
  const hist: { time: number; value: number; color: string }[] = [];
  for (const m of macdRaw) {
    const sig = timeToSig.get(m.time);
    if (sig !== undefined) {
      const val = m.value - sig;
      hist.push({ time: m.time, value: val, color: val >= 0 ? "#0ecb81" : "#f6465d" });
    }
  }

  return { macd: macdRaw, signal: signalRaw, hist };
}

/** RSI */
export function calcRSI(
  data: KlinePoint[],
  period = 14
): { time: number; value: number }[] {
  if (data.length <= period) return [];
  const result: { time: number; value: number }[] = [];
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = data[i].close - data[i - 1].close;
    if (diff > 0) gains += diff;
    else losses -= diff;
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;
  const rsi = (v: number) => (v === 0 ? 100 : v === Infinity ? 0 : 100 - 100 / (1 + v));
  result.push({ time: data[period].time, value: rsi(avgGain / (avgLoss || 1e-10)) });
  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close;
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    result.push({ time: data[i].time, value: rsi(avgGain / (avgLoss || 1e-10)) });
  }
  return result;
}

/** KDJ (Stochastic, K=9, D=3) */
export function calcKDJ(
  data: KlinePoint[],
  kPeriod = 9,
  dSmooth = 3
): {
  k: { time: number; value: number }[];
  d: { time: number; value: number }[];
  j: { time: number; value: number }[];
} {
  const kArr: { time: number; value: number }[] = [];
  const dArr: { time: number; value: number }[] = [];
  const jArr: { time: number; value: number }[] = [];
  let kPrev = 50, dPrev = 50;
  for (let i = kPeriod - 1; i < data.length; i++) {
    const slice = data.slice(i - kPeriod + 1, i + 1);
    const highest = Math.max(...slice.map((d) => d.high));
    const lowest = Math.min(...slice.map((d) => d.low));
    const rsv = highest === lowest ? 50 : ((data[i].close - lowest) / (highest - lowest)) * 100;
    const k = (2 / 3) * kPrev + (1 / 3) * rsv;
    const d = (2 / 3) * dPrev + (1 / 3) * k;
    const j = 3 * k - 2 * d;
    kArr.push({ time: data[i].time, value: k });
    dArr.push({ time: data[i].time, value: d });
    jArr.push({ time: data[i].time, value: j });
    kPrev = k;
    dPrev = d;
  }
  return { k: kArr, d: dArr, j: jArr };
}

/** Williams %R */
export function calcWR(
  data: KlinePoint[],
  period = 14
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const highest = Math.max(...slice.map((d) => d.high));
    const lowest = Math.min(...slice.map((d) => d.low));
    const wr = highest === lowest ? -50 : ((highest - data[i].close) / (highest - lowest)) * -100;
    result.push({ time: data[i].time, value: wr });
  }
  return result;
}

/** DMI (+DI, -DI, ADX) */
export function calcDMI(
  data: KlinePoint[],
  period = 14
): {
  plusDI: { time: number; value: number }[];
  minusDI: { time: number; value: number }[];
  adx: { time: number; value: number }[];
} {
  if (data.length < period + 1) return { plusDI: [], minusDI: [], adx: [] };
  const trs: number[] = [];
  const plusDMs: number[] = [];
  const minusDMs: number[] = [];
  for (let i = 1; i < data.length; i++) {
    const hl = data[i].high - data[i].low;
    const hc = Math.abs(data[i].high - data[i - 1].close);
    const lc = Math.abs(data[i].low - data[i - 1].close);
    trs.push(Math.max(hl, hc, lc));
    const upMove = data[i].high - data[i - 1].high;
    const downMove = data[i - 1].low - data[i].low;
    plusDMs.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDMs.push(downMove > upMove && downMove > 0 ? downMove : 0);
  }
  const smooth = (arr: number[], p: number) => {
    let s = arr.slice(0, p).reduce((a, b) => a + b, 0);
    const out = [s];
    for (let i = p; i < arr.length; i++) {
      s = s - s / p + arr[i];
      out.push(s);
    }
    return out;
  };
  const atr14 = smooth(trs, period);
  const pDM14 = smooth(plusDMs, period);
  const mDM14 = smooth(minusDMs, period);
  const plusDI: { time: number; value: number }[] = [];
  const minusDI: { time: number; value: number }[] = [];
  const adx: { time: number; value: number }[] = [];
  const dxArr: number[] = [];
  for (let i = 0; i < atr14.length; i++) {
    const pdi = atr14[i] === 0 ? 0 : (pDM14[i] / atr14[i]) * 100;
    const mdi = atr14[i] === 0 ? 0 : (mDM14[i] / atr14[i]) * 100;
    const dx = pdi + mdi === 0 ? 0 : (Math.abs(pdi - mdi) / (pdi + mdi)) * 100;
    const t = data[i + period].time;
    plusDI.push({ time: t, value: pdi });
    minusDI.push({ time: t, value: mdi });
    dxArr.push(dx);
  }
  // ADX = smoothed DX
  if (dxArr.length >= period) {
    let adxVal = dxArr.slice(0, period).reduce((s, v) => s + v, 0) / period;
    adx.push({ time: plusDI[period - 1].time, value: adxVal });
    for (let i = period; i < dxArr.length; i++) {
      adxVal = (adxVal * (period - 1) + dxArr[i]) / period;
      adx.push({ time: plusDI[i].time, value: adxVal });
    }
  }
  return { plusDI, minusDI, adx };
}

/** CCI */
export function calcCCI(
  data: KlinePoint[],
  period = 14
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const tps = slice.map((d) => (d.high + d.low + d.close) / 3);
    const mean = tps.reduce((s, v) => s + v, 0) / period;
    const meanDev = tps.reduce((s, v) => s + Math.abs(v - mean), 0) / period;
    result.push({
      time: data[i].time,
      value: meanDev === 0 ? 0 : (tps[period - 1] - mean) / (0.015 * meanDev),
    });
  }
  return result;
}

/** OBV */
export function calcOBV(data: KlinePoint[]): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  let obv = 0;
  result.push({ time: data[0].time, value: 0 });
  for (let i = 1; i < data.length; i++) {
    if (data[i].close > data[i - 1].close) obv += data[i].volume;
    else if (data[i].close < data[i - 1].close) obv -= data[i].volume;
    result.push({ time: data[i].time, value: obv });
  }
  return result;
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd /Users/heesangchae/crypto-exchange/frontend
PATH="/Users/heesangchae/.nvm/versions/node/v22.18.0/bin:$PATH" npx tsc --noEmit
```

Expected: No errors for `lib/indicators.ts`.

**Step 3: Commit**

```bash
git add lib/indicators.ts
git commit -m "feat: add chart indicator calculation functions (MA/EMA/BOLL/SAR/VOL/MACD/RSI/KDJ/WR/DMI/CCI/OBV)"
```

---

### Task 2: Rewrite `ChartWidget.tsx` — wire indicators to chart

**Files:**
- Modify: `components/exchange/ChartWidget.tsx`

**Context:**
- lightweight-charts v5 API: `chart.addSeries(SeriesType, options, paneOrIndex)`
- For sub-panes: `const pane = chart.addPane()` → `chart.addSeries(LineSeries, opts, pane)` → on deactivate: `chart.removeSeries(series)` then `chart.removePane(pane)`
- Pane 0 is the main price pane (candlestick)
- `LineSeries`, `HistogramSeries` imported from `lightweight-charts`
- Import `IPane` type if needed: `import type { IPane } from 'lightweight-charts'`

**Step 1: Rewrite ChartWidget.tsx**

Full replacement of the file. Key changes:
1. Import `LineSeries`, `HistogramSeries` from `lightweight-charts`
2. Add `klineDataRef` to store raw `KlinePoint[]` data
3. Add `overlaySeriesRef` (Map: string → ISeriesApi[]) for MA/EMA/BOLL/SAR
4. Add `subPaneSeriesRef` (Map: string → ISeriesApi[]) and `subPaneRef` (Map: string → IPane) for oscillators
5. `loadData(iv)` stores raw kline data in `klineDataRef`, then calls `syncIndicators()`
6. `syncIndicators()` pure function: for each active indicator, add series if not present; for each inactive indicator, remove series (and pane if sub-pane)
7. `useEffect([activeIndicators])` calls `syncIndicators()` when toggles change

```typescript
"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";
import type { IPane } from "lightweight-charts";
import { apiFetch } from "@/lib/api";
import styles from "./ChartWidget.module.css";
import {
  KlinePoint,
  calcMA, calcEMA, calcBOLL, calcSAR,
  calcVOL, calcMACD, calcRSI, calcKDJ, calcWR, calcDMI, calcCCI, calcOBV,
} from "@/lib/indicators";

const INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"] as const;
const INTERVAL_LABELS: Record<string, string> = {
  "1m": "1분", "5m": "5분", "15m": "15분", "30m": "30분",
  "1h": "1시간", "4h": "4시간", "1d": "1일", "1w": "1주",
};
const INDICATORS = ["MA", "EMA", "BOLL", "SAR", "VOL", "MACD", "RSI", "KDJ", "WR", "DMI", "CCI", "OBV"] as const;

// Sub-pane indicators (need their own pane below main chart)
const SUB_PANE_INDICATORS = new Set(["VOL", "MACD", "RSI", "KDJ", "WR", "DMI", "CCI", "OBV"]);

export default function ChartWidget({ pair }: { pair: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const klineDataRef = useRef<KlinePoint[]>([]);
  // Overlay series: indicatorKey → array of series in main pane
  const overlaySeriesRef = useRef<Map<string, ISeriesApi<"Line" | "Histogram">[]>>(new Map());
  // Sub-pane series: indicatorKey → array of series
  const subPaneSeriesRef = useRef<Map<string, ISeriesApi<"Line" | "Histogram">[]>>(new Map());
  // Sub-pane refs: indicatorKey → pane
  const subPaneRef = useRef<Map<string, IPane>>(new Map());

  const [interval, setIntervalState] = useState("1h");
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(new Set());

  const toggleIndicator = (name: string) => {
    setActiveIndicators((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  // Remove all series for a given indicator key
  const removeIndicator = useCallback((key: string) => {
    const chart = chartRef.current;
    if (!chart) return;
    const overlaySeries = overlaySeriesRef.current.get(key);
    if (overlaySeries) {
      overlaySeries.forEach((s) => { try { chart.removeSeries(s); } catch {} });
      overlaySeriesRef.current.delete(key);
    }
    const subSeries = subPaneSeriesRef.current.get(key);
    if (subSeries) {
      subSeries.forEach((s) => { try { chart.removeSeries(s); } catch {} });
      subPaneSeriesRef.current.delete(key);
    }
    const pane = subPaneRef.current.get(key);
    if (pane) {
      try { chart.removePane(pane); } catch {}
      subPaneRef.current.delete(key);
    }
  }, []);

  const syncIndicators = useCallback((active: Set<string>) => {
    const chart = chartRef.current;
    const data = klineDataRef.current;
    if (!chart || data.length === 0) return;

    // Remove all indicators not in active set
    for (const key of [...overlaySeriesRef.current.keys(), ...subPaneSeriesRef.current.keys()]) {
      if (!active.has(key)) removeIndicator(key);
    }

    for (const key of active) {
      // Skip if already rendered
      if (overlaySeriesRef.current.has(key) || subPaneSeriesRef.current.has(key)) continue;

      if (key === "MA") {
        const periods = [7, 25, 99];
        const colors = ["#f6a600", "#f0c419", "#cd84f1"];
        const series: ISeriesApi<"Line">[] = [];
        periods.forEach((p, idx) => {
          const s = chart.addSeries(LineSeries, {
            color: colors[idx], lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
          }, 0);
          s.setData(calcMA(data, p));
          series.push(s);
        });
        overlaySeriesRef.current.set("MA", series);

      } else if (key === "EMA") {
        const periods = [12, 26];
        const colors = ["#1e90ff", "#ff69b4"];
        const series: ISeriesApi<"Line">[] = [];
        periods.forEach((p, idx) => {
          const s = chart.addSeries(LineSeries, {
            color: colors[idx], lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
          }, 0);
          s.setData(calcEMA(data, p));
          series.push(s);
        });
        overlaySeriesRef.current.set("EMA", series);

      } else if (key === "BOLL") {
        const boll = calcBOLL(data);
        const upper = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 0);
        const middle = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 0);
        const lower = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 0);
        upper.setData(boll.map((d) => ({ time: d.time, value: d.upper })));
        middle.setData(boll.map((d) => ({ time: d.time, value: d.middle })));
        lower.setData(boll.map((d) => ({ time: d.time, value: d.lower })));
        overlaySeriesRef.current.set("BOLL", [upper, middle, lower]);

      } else if (key === "SAR") {
        const sar = calcSAR(data);
        const s = chart.addSeries(LineSeries, {
          color: "#ff6b6b", lineWidth: 1, lineStyle: 4, // dotted
          priceLineVisible: false, lastValueVisible: false,
        }, 0);
        s.setData(sar);
        overlaySeriesRef.current.set("SAR", [s]);

      } else if (key === "VOL") {
        const pane = chart.addPane();
        const s = chart.addSeries(HistogramSeries, {
          priceFormat: { type: "volume" }, priceScaleId: "vol",
        }, pane);
        s.setData(calcVOL(data));
        subPaneSeriesRef.current.set("VOL", [s]);
        subPaneRef.current.set("VOL", pane);

      } else if (key === "MACD") {
        const { macd, signal, hist } = calcMACD(data);
        const pane = chart.addPane();
        const histS = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane);
        const macdS = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        const signalS = chart.addSeries(LineSeries, { color: "#ff69b4", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        histS.setData(hist);
        macdS.setData(macd);
        signalS.setData(signal);
        subPaneSeriesRef.current.set("MACD", [histS, macdS, signalS]);
        subPaneRef.current.set("MACD", pane);

      } else if (key === "RSI") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#9b59b6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        s.setData(calcRSI(data));
        subPaneSeriesRef.current.set("RSI", [s]);
        subPaneRef.current.set("RSI", pane);

      } else if (key === "KDJ") {
        const { k, d, j } = calcKDJ(data);
        const pane = chart.addPane();
        const kS = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        const dS = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        const jS = chart.addSeries(LineSeries, { color: "#00bfff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        kS.setData(k);
        dS.setData(d);
        jS.setData(j);
        subPaneSeriesRef.current.set("KDJ", [kS, dS, jS]);
        subPaneRef.current.set("KDJ", pane);

      } else if (key === "WR") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#9b59b6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        s.setData(calcWR(data));
        subPaneSeriesRef.current.set("WR", [s]);
        subPaneRef.current.set("WR", pane);

      } else if (key === "DMI") {
        const { plusDI, minusDI, adx } = calcDMI(data);
        const pane = chart.addPane();
        const pS = chart.addSeries(LineSeries, { color: "#00ff7f", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        const mS = chart.addSeries(LineSeries, { color: "#ff4444", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        const aS = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        pS.setData(plusDI);
        mS.setData(minusDI);
        aS.setData(adx);
        subPaneSeriesRef.current.set("DMI", [pS, mS, aS]);
        subPaneRef.current.set("DMI", pane);

      } else if (key === "CCI") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#9b59b6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        s.setData(calcCCI(data));
        subPaneSeriesRef.current.set("CCI", [s]);
        subPaneRef.current.set("CCI", pane);

      } else if (key === "OBV") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane);
        s.setData(calcOBV(data));
        subPaneSeriesRef.current.set("OBV", [s]);
        subPaneRef.current.set("OBV", pane);
      }
    }
  }, [removeIndicator]);

  const loadData = useCallback(async (iv: string) => {
    if (!candleSeriesRef.current) return;
    try {
      const raw = await apiFetch(`/api/market/${pair}/klines?interval=${iv}&limit=500`);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const klines: KlinePoint[] = raw.map((k: any) => ({
        time: k.time as number,
        open: parseFloat(k.open),
        high: parseFloat(k.high),
        low: parseFloat(k.low),
        close: parseFloat(k.close),
        volume: parseFloat(k.volume),
      }));
      candleSeriesRef.current.setData(klines);
      klineDataRef.current = klines;
      // Re-render all active indicators with new data
      // Remove existing indicator series first so they get re-added with fresh data
      for (const key of [...overlaySeriesRef.current.keys()]) removeIndicator(key);
      for (const key of [...subPaneSeriesRef.current.keys()]) removeIndicator(key);
      // Re-add from current activeIndicators state (read via callback trick below)
      setActiveIndicators((prev) => {
        syncIndicators(prev);
        return prev;
      });
    } catch (e) {
      console.error("Failed to load klines", e);
    }
  }, [pair, syncIndicators, removeIndicator]);

  // Create chart once on mount
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: "#0b0e11" }, textColor: "#848e9c" },
      grid: { vertLines: { color: "#2b3139" }, horzLines: { color: "#2b3139" } },
      rightPriceScale: { borderColor: "#2b3139" },
      timeScale: { borderColor: "#2b3139", timeVisible: true, secondsVisible: false },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#0ecb81", downColor: "#f6465d",
      borderUpColor: "#0ecb81", borderDownColor: "#f6465d",
      wickUpColor: "#0ecb81", wickDownColor: "#f6465d",
    });
    chartRef.current = chart;
    candleSeriesRef.current = series;
    return () => { chart.remove(); };
  }, []);

  // Reload klines when pair or interval changes
  useEffect(() => {
    loadData(interval);
  }, [pair, interval, loadData]);

  // Sync indicators when active set changes
  useEffect(() => {
    syncIndicators(activeIndicators);
  }, [activeIndicators, syncIndicators]);

  return (
    <div className="flex flex-col h-full">
      <div className={`flex items-center gap-1 px-3 py-1.5 border-b flex-shrink-0 ${styles.toolbar}`}>
        {INTERVALS.map((iv) => (
          <button key={iv} type="button" onClick={() => setIntervalState(iv)}
            className={`px-2 py-0.5 rounded text-xs transition-colors cursor-pointer ${styles.intervalBtn}`}
            data-active={interval === iv ? "true" : "false"}>
            {INTERVAL_LABELS[iv]}
          </button>
        ))}
        <span className={styles.separator} />
        {INDICATORS.map((name) => (
          <button key={name} type="button" onClick={() => toggleIndicator(name)}
            className={`px-2 py-0.5 rounded text-xs transition-colors cursor-pointer ${styles.indicatorBtn}`}
            data-active={activeIndicators.has(name) ? "true" : "false"}>
            {name}
          </button>
        ))}
        <div className="ml-auto flex items-center">
          <button type="button" className={`px-2 py-0.5 text-xs cursor-pointer ${styles.iconBtn}`}>👁</button>
          <button type="button" className={`px-2 py-0.5 text-xs cursor-pointer ${styles.iconBtn}`}>▾</button>
        </div>
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
```

**Step 2: Check TypeScript**

```bash
cd /Users/heesangchae/crypto-exchange/frontend
PATH="/Users/heesangchae/.nvm/versions/node/v22.18.0/bin:$PATH" npx tsc --noEmit 2>&1 | head -50
```

Fix any type errors. Common issues:
- `IPane` import: if not exported from `lightweight-charts`, use `ReturnType<IChartApi['addPane']>` instead
- `HistogramSeries` color data: `{ time, value, color }` — ensure `color` is passed correctly
- `lineStyle` property on LineSeries: type might be `LineStyle` enum, import it if needed

**Step 3: Build check**

```bash
cd /Users/heesangchae/crypto-exchange/frontend
PATH="/Users/heesangchae/.nvm/versions/node/v22.18.0/bin:$PATH" node node_modules/.bin/next build 2>&1 | tail -20
```

Expected: Build succeeds (or only pre-existing warnings, no new errors).

**Step 4: Commit**

```bash
git add components/exchange/ChartWidget.tsx
git commit -m "feat: implement all 12 chart indicators with dynamic pane management"
```

---

### Task 3: Smoke-test in browser

**This is a manual verification step — no code to write.**

1. Start dev server: `PATH="/Users/heesangchae/.nvm/versions/node/v22.18.0/bin:$PATH" npm run dev`
2. Open `http://localhost:3000/exchange/BTC_USDT`
3. Click each indicator button and verify:
   - MA → 3 colored lines appear on candlestick chart
   - EMA → 2 colored lines appear on candlestick chart
   - BOLL → 3 lines (upper/middle/lower band) appear
   - SAR → dotted line on candlestick chart
   - VOL → volume histogram panel appears below
   - MACD → histogram + 2 lines in new panel
   - RSI → purple line in new panel
   - KDJ → 3 lines in new panel
   - WR → line in new panel
   - DMI → 3 lines (+DI/-DI/ADX) in new panel
   - CCI → line in new panel
   - OBV → line in new panel
4. Click active indicator again → panel/lines disappear
5. Switch coin → indicators persist, data refreshes
6. Switch interval → indicators update with new data

**If any indicator fails:** Check browser console for errors. Common issues:
- `chart.removePane is not a function` → LWC v5 doesn't support it; fallback: hide pane instead
- Empty data array passed to series → check calculation function output
- Time alignment issues → ensure `time` values are UNIX timestamps (seconds, not ms)
