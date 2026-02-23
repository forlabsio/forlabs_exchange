"use client";
import { useEffect, useRef, useState } from "react";
import { createChart, IChartApi, ISeriesApi, CandlestickSeries } from "lightweight-charts";
import { apiFetch } from "@/lib/api";

const INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"] as const;
const INTERVAL_LABELS: Record<string, string> = {
  "1m": "1분", "5m": "5분", "15m": "15분", "30m": "30분",
  "1h": "1시간", "4h": "4시간", "1d": "1일", "1w": "1주",
};

export default function ChartWidget({ pair }: { pair: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [interval, setIntervalState] = useState("1h");

  const loadData = async (iv: string) => {
    if (!seriesRef.current) return;
    try {
      const data = await apiFetch(`/api/market/${pair}/klines?interval=${iv}&limit=500`);
      seriesRef.current.setData(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        data.map((k: any) => ({
          time: k.time as number,
          open: parseFloat(k.open),
          high: parseFloat(k.high),
          low: parseFloat(k.low),
          close: parseFloat(k.close),
        }))
      );
    } catch (e) {
      console.error("Failed to load klines", e);
    }
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { color: "#0b0e11" }, textColor: "#848e9c" },
      grid: { vertLines: { color: "#2b3139" }, horzLines: { color: "#2b3139" } },
      rightPriceScale: { borderColor: "#2b3139" },
      timeScale: { borderColor: "#2b3139", timeVisible: true, secondsVisible: false },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#0ecb81",
      downColor: "#f6465d",
      borderUpColor: "#0ecb81",
      borderDownColor: "#f6465d",
      wickUpColor: "#0ecb81",
      wickDownColor: "#f6465d",
    });

    chartRef.current = chart;
    seriesRef.current = series;
    loadData("1h");

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chart) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [pair]);

  const handleIntervalChange = (iv: string) => {
    setIntervalState(iv);
    loadData(iv);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Interval selector */}
      <div className="flex items-center gap-1 px-3 py-1.5 border-b flex-shrink-0"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        {INTERVALS.map((iv) => (
          <button key={iv} onClick={() => handleIntervalChange(iv)}
            className="px-2 py-0.5 rounded text-xs transition-colors"
            style={{
              color: interval === iv ? "var(--text-primary)" : "var(--text-secondary)",
              background: interval === iv ? "var(--bg-panel)" : "transparent",
              fontWeight: interval === iv ? "600" : "400",
            }}>
            {INTERVAL_LABELS[iv]}
          </button>
        ))}
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
