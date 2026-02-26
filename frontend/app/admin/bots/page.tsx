"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const STRATEGY_TYPES = [
  { value: "rsi_trend", label: "RSI + 추세필터" },
  { value: "boll_adx", label: "볼린저 + ADX" },
  { value: "trend_ma200", label: "Trend 200MA" },
  { value: "adaptive_grid", label: "Adaptive Grid" },
  { value: "breakout_lite", label: "Breakout Lite" },
];

const PAIRS = ["BTC_USDT", "ETH_USDT", "BNB_USDT", "SOL_USDT"];

interface AdminBot {
  id: number;
  name: string;
  description: string;
  strategy_type: string;
  strategy_config: Record<string, unknown>;
  status: string;
  max_drawdown_limit: number;
  monthly_fee: number;
  subscriber_count: number;
  created_at: string | null;
}

interface FormState {
  name: string;
  description: string;
  strategy_type: string;
  max_drawdown_limit: number;
  monthly_fee: number;
  // common
  pair: string;
  signal_interval: number;
  risk_pct: number;
  // rsi_trend
  rsi_period: number;
  overbought: number;
  oversold: number;
  stop_loss_atr: number;
  take_profit_atr: number;
  // boll_adx
  boll_period: number;
  boll_std: number;
  adx_threshold: number;
  bw_min: number;
  bw_max: number;
  // trend_ma200
  ma_period: number;
  slope_lookback: number;
  confirm_bars: number;
  trailing_atr: number;
  // adaptive_grid
  grid_levels: number;
  grid_spacing_atr: number;
  // breakout_lite
  donchian_period: number;
  volume_ma_period: number;
  volume_mult: number;
  adx_min: number;
}

const DEFAULT_FORM: FormState = {
  name: "",
  description: "",
  strategy_type: "rsi_trend",
  max_drawdown_limit: 20,
  monthly_fee: 0,
  pair: "BTC_USDT",
  signal_interval: 300,
  risk_pct: 1.0,
  // rsi_trend
  rsi_period: 14,
  overbought: 70,
  oversold: 30,
  stop_loss_atr: 1.5,
  take_profit_atr: 2.0,
  // boll_adx
  boll_period: 20,
  boll_std: 2.0,
  adx_threshold: 25,
  bw_min: 0.02,
  bw_max: 0.15,
  // trend_ma200
  ma_period: 200,
  slope_lookback: 10,
  confirm_bars: 3,
  trailing_atr: 2.5,
  // adaptive_grid
  grid_levels: 5,
  grid_spacing_atr: 0.5,
  // breakout_lite
  donchian_period: 20,
  volume_ma_period: 20,
  volume_mult: 1.5,
  adx_min: 20,
};

function buildStrategyConfig(form: FormState): Record<string, unknown> {
  const base = { pair: form.pair, signal_interval: form.signal_interval, risk_pct: form.risk_pct };
  switch (form.strategy_type) {
    case "rsi_trend":
      return { ...base, rsi_period: form.rsi_period, overbought: form.overbought, oversold: form.oversold, stop_loss_atr: form.stop_loss_atr, take_profit_atr: form.take_profit_atr };
    case "boll_adx":
      return { ...base, period: form.boll_period, std_dev: form.boll_std, adx_threshold: form.adx_threshold, bw_min: form.bw_min, bw_max: form.bw_max, stop_loss_atr: form.stop_loss_atr, take_profit_atr: form.take_profit_atr };
    case "trend_ma200":
      return { ...base, ma_period: form.ma_period, slope_lookback: form.slope_lookback, confirm_bars: form.confirm_bars, trailing_atr: form.trailing_atr };
    case "adaptive_grid":
      return { ...base, grid_levels: form.grid_levels, grid_spacing_atr: form.grid_spacing_atr };
    case "breakout_lite":
      return { ...base, donchian_period: form.donchian_period, volume_ma_period: form.volume_ma_period, volume_mult: form.volume_mult, adx_min: form.adx_min, trailing_atr: form.trailing_atr };
    default:
      return base;
  }
}

function parseFormFromBot(bot: AdminBot): FormState {
  const c = bot.strategy_config || {};
  return {
    name: bot.name,
    description: bot.description,
    strategy_type: bot.strategy_type,
    max_drawdown_limit: bot.max_drawdown_limit,
    monthly_fee: bot.monthly_fee,
    pair: (c.pair as string) || "BTC_USDT",
    signal_interval: (c.signal_interval as number) || 300,
    risk_pct: (c.risk_pct as number) || 1.0,
    rsi_period: (c.rsi_period as number) || 14,
    overbought: (c.overbought as number) || 70,
    oversold: (c.oversold as number) || 30,
    stop_loss_atr: (c.stop_loss_atr as number) || 1.5,
    take_profit_atr: (c.take_profit_atr as number) || 2.0,
    boll_period: (c.period as number) || 20,
    boll_std: (c.std_dev as number) || 2.0,
    adx_threshold: (c.adx_threshold as number) || 25,
    bw_min: (c.bw_min as number) || 0.02,
    bw_max: (c.bw_max as number) || 0.15,
    ma_period: (c.ma_period as number) || 200,
    slope_lookback: (c.slope_lookback as number) || 10,
    confirm_bars: (c.confirm_bars as number) || 3,
    trailing_atr: (c.trailing_atr as number) || 2.5,
    grid_levels: (c.grid_levels as number) || 5,
    grid_spacing_atr: (c.grid_spacing_atr as number) || 0.5,
    donchian_period: (c.donchian_period as number) || 20,
    volume_ma_period: (c.volume_ma_period as number) || 20,
    volume_mult: (c.volume_mult as number) || 1.5,
    adx_min: (c.adx_min as number) || 20,
  };
}

function InputRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full px-3 py-2 rounded-lg text-sm outline-none";
const inputStyle = { background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" };

function BotModal({ initial, onClose, onSave }: {
  initial?: AdminBot | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const [form, setForm] = useState<FormState>(initial ? parseFormFromBot(initial) : DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (key: keyof FormState, value: string | number) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = {
        name: form.name,
        description: form.description,
        strategy_type: form.strategy_type,
        strategy_config: buildStrategyConfig(form),
        max_drawdown_limit: form.max_drawdown_limit,
        monthly_fee: form.monthly_fee,
      };
      if (initial) {
        await apiFetch(`/api/admin/bots/${initial.id}`, { method: "PUT", body: JSON.stringify(body) });
      } else {
        await apiFetch("/api/admin/bots", { method: "POST", body: JSON.stringify(body) });
      }
      onSave();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-xl p-6 flex flex-col gap-4"
        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>

        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            {initial ? "봇 수정" : "새 봇 등록"}
          </h2>
          <button type="button" onClick={onClose} className="text-xl leading-none" style={{ color: "var(--text-secondary)" }}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <InputRow label="봇 이름">
            <input className={inputCls} style={inputStyle} value={form.name}
              onChange={(e) => set("name", e.target.value)} required placeholder="Alpha RSI Bot" />
          </InputRow>

          <InputRow label="설명">
            <textarea className={inputCls} style={{ ...inputStyle, resize: "vertical" }} rows={2}
              value={form.description} onChange={(e) => set("description", e.target.value)}
              placeholder="봇 설명을 입력하세요" />
          </InputRow>

          <InputRow label="전략 타입">
            <select className={inputCls} style={inputStyle} value={form.strategy_type}
              onChange={(e) => set("strategy_type", e.target.value)}>
              {STRATEGY_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </InputRow>

          {/* Common params */}
          <div className="grid grid-cols-3 gap-2">
            <InputRow label="거래 페어">
              <select className={inputCls} style={inputStyle} value={form.pair}
                onChange={(e) => set("pair", e.target.value)}>
                {PAIRS.map((p) => <option key={p} value={p}>{p.replace("_", "/")}</option>)}
              </select>
            </InputRow>
            <InputRow label="리스크 (%)">
              <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.risk_pct}
                min={0.1} max={5} onChange={(e) => set("risk_pct", Number(e.target.value))} />
            </InputRow>
            <InputRow label="신호 주기 (초)">
              <input type="number" className={inputCls} style={inputStyle} value={form.signal_interval}
                min={60} onChange={(e) => set("signal_interval", Number(e.target.value))} />
            </InputRow>
          </div>

          {/* RSI + Trend Filter */}
          {form.strategy_type === "rsi_trend" && (
            <div className="grid grid-cols-3 gap-2">
              <InputRow label="RSI 기간">
                <input type="number" className={inputCls} style={inputStyle} value={form.rsi_period}
                  onChange={(e) => set("rsi_period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="과매수">
                <input type="number" className={inputCls} style={inputStyle} value={form.overbought}
                  onChange={(e) => set("overbought", Number(e.target.value))} />
              </InputRow>
              <InputRow label="과매도">
                <input type="number" className={inputCls} style={inputStyle} value={form.oversold}
                  onChange={(e) => set("oversold", Number(e.target.value))} />
              </InputRow>
              <InputRow label="SL (ATR배수)">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.stop_loss_atr}
                  onChange={(e) => set("stop_loss_atr", Number(e.target.value))} />
              </InputRow>
              <InputRow label="TP (ATR배수)">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.take_profit_atr}
                  onChange={(e) => set("take_profit_atr", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          {/* Bollinger + ADX */}
          {form.strategy_type === "boll_adx" && (
            <div className="grid grid-cols-3 gap-2">
              <InputRow label="볼린저 기간">
                <input type="number" className={inputCls} style={inputStyle} value={form.boll_period}
                  onChange={(e) => set("boll_period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="표준편차">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.boll_std}
                  onChange={(e) => set("boll_std", Number(e.target.value))} />
              </InputRow>
              <InputRow label="ADX 한도">
                <input type="number" className={inputCls} style={inputStyle} value={form.adx_threshold}
                  onChange={(e) => set("adx_threshold", Number(e.target.value))} />
              </InputRow>
              <InputRow label="BW 최소">
                <input type="number" step="0.01" className={inputCls} style={inputStyle} value={form.bw_min}
                  onChange={(e) => set("bw_min", Number(e.target.value))} />
              </InputRow>
              <InputRow label="BW 최대">
                <input type="number" step="0.01" className={inputCls} style={inputStyle} value={form.bw_max}
                  onChange={(e) => set("bw_max", Number(e.target.value))} />
              </InputRow>
              <InputRow label="SL (ATR배수)">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.stop_loss_atr}
                  onChange={(e) => set("stop_loss_atr", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          {/* Trend 200MA */}
          {form.strategy_type === "trend_ma200" && (
            <div className="grid grid-cols-3 gap-2">
              <InputRow label="MA 기간">
                <input type="number" className={inputCls} style={inputStyle} value={form.ma_period}
                  onChange={(e) => set("ma_period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="기울기 룩백">
                <input type="number" className={inputCls} style={inputStyle} value={form.slope_lookback}
                  onChange={(e) => set("slope_lookback", Number(e.target.value))} />
              </InputRow>
              <InputRow label="확인 봉수">
                <input type="number" className={inputCls} style={inputStyle} value={form.confirm_bars}
                  onChange={(e) => set("confirm_bars", Number(e.target.value))} />
              </InputRow>
              <InputRow label="트레일링 (ATR배수)">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.trailing_atr}
                  onChange={(e) => set("trailing_atr", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          {/* Adaptive Grid */}
          {form.strategy_type === "adaptive_grid" && (
            <div className="grid grid-cols-2 gap-2">
              <InputRow label="그리드 단수">
                <input type="number" className={inputCls} style={inputStyle} value={form.grid_levels}
                  min={3} max={10} onChange={(e) => set("grid_levels", Number(e.target.value))} />
              </InputRow>
              <InputRow label="간격 (ATR배수)">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.grid_spacing_atr}
                  onChange={(e) => set("grid_spacing_atr", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          {/* Breakout Lite */}
          {form.strategy_type === "breakout_lite" && (
            <div className="grid grid-cols-3 gap-2">
              <InputRow label="돈치안 기간">
                <input type="number" className={inputCls} style={inputStyle} value={form.donchian_period}
                  onChange={(e) => set("donchian_period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="거래량 MA">
                <input type="number" className={inputCls} style={inputStyle} value={form.volume_ma_period}
                  onChange={(e) => set("volume_ma_period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="거래량 배수">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.volume_mult}
                  onChange={(e) => set("volume_mult", Number(e.target.value))} />
              </InputRow>
              <InputRow label="ADX 최소">
                <input type="number" className={inputCls} style={inputStyle} value={form.adx_min}
                  onChange={(e) => set("adx_min", Number(e.target.value))} />
              </InputRow>
              <InputRow label="트레일링 (ATR배수)">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.trailing_atr}
                  onChange={(e) => set("trailing_atr", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <InputRow label="최대 낙폭 한도 (%)">
              <input type="number" className={inputCls} style={inputStyle} value={form.max_drawdown_limit}
                onChange={(e) => set("max_drawdown_limit", Number(e.target.value))} />
            </InputRow>
            <InputRow label="월 구독료 ($)">
              <input type="number" step="0.01" className={inputCls} style={inputStyle} value={form.monthly_fee}
                onChange={(e) => set("monthly_fee", Number(e.target.value))} />
            </InputRow>
          </div>

          {error && <p className="text-xs" style={{ color: "var(--red)" }}>{error}</p>}

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              취소
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--blue)" }}>
              {saving ? "저장 중..." : "저장"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminBotsPage() {
  const { token, user, hydrate } = useAuthStore();
  const router = useRouter();
  const [bots, setBots] = useState<AdminBot[]>([]);
  const [modal, setModal] = useState<{ open: boolean; bot: AdminBot | null }>({ open: false, bot: null });
  const [liveTrading, setLiveTrading] = useState(false);

  useEffect(() => {
    hydrate().then(() => {
      const t = localStorage.getItem("token");
      if (!t) { router.push("/login"); return; }
    });
  }, []);

  useEffect(() => {
    if (user && user.role !== "admin") { router.push("/"); }
    if (user && user.role === "admin") {
      loadBots();
      apiFetch("/api/admin/system-status")
        .then((data) => setLiveTrading(data.live_trading))
        .catch(() => {});
    }
  }, [user]);

  const loadBots = async () => {
    try {
      const data = await apiFetch("/api/admin/bots");
      setBots(data);
    } catch {
      // handled by redirect
    }
  };

  const handleDelete = async (bot: AdminBot) => {
    if (!confirm(`"${bot.name}" 봇을 퇴출하시겠습니까? 모든 구독자의 연동이 해제됩니다.`)) return;
    await apiFetch(`/api/admin/bots/${bot.id}`, { method: "DELETE" });
    loadBots();
  };

  const STRATEGY_LABELS: Record<string, string> = {
    rsi_trend: "RSI + 추세필터", boll_adx: "볼린저 + ADX", trend_ma200: "Trend 200MA", adaptive_grid: "Adaptive Grid", breakout_lite: "Breakout Lite",
  };

  if (!user || user.role !== "admin") {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "var(--text-secondary)" }}>
        접근 권한이 없습니다.
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>봇 관리</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            총 {bots.length}개 봇 · 관리자 전용
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ open: true, bot: null })}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--blue)" }}>
          + 새 봇 등록
        </button>
      </div>

      {bots.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
          <p className="text-lg mb-2">등록된 봇이 없습니다</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--bg-panel)", borderBottom: "1px solid var(--border)" }}>
                {["봇 이름", "전략", "상태", "구독자", "구독료", "등록일", ""].map((h) => (
                  <th key={h} className="py-3 px-4 text-left font-medium" style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bots.map((bot) => (
                <tr key={bot.id} style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-base)" }}>
                  <td className="py-3 px-4 font-medium" style={{ color: "var(--text-primary)" }}>{bot.name}</td>
                  <td className="py-3 px-4" style={{ color: "var(--text-secondary)" }}>
                    {STRATEGY_LABELS[bot.strategy_type] || bot.strategy_type}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{
                      background: bot.status === "active" ? "rgba(14,203,129,0.15)" : "rgba(246,70,93,0.15)",
                      color: bot.status === "active" ? "var(--green)" : "var(--red)",
                    }}>
                      {bot.status === "active" ? "Active" : "Evicted"}
                    </span>
                  </td>
                  <td className="py-3 px-4" style={{ color: "var(--text-primary)" }}>{bot.subscriber_count}명</td>
                  <td className="py-3 px-4" style={{ color: "var(--text-primary)" }}>
                    {bot.monthly_fee === 0 ? "무료" : `$${bot.monthly_fee}`}
                  </td>
                  <td className="py-3 px-4 text-xs" style={{ color: "var(--text-secondary)" }}>
                    {bot.created_at ? new Date(bot.created_at).toLocaleDateString("ko-KR") : "-"}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setModal({ open: true, bot })}
                        className="text-xs px-2.5 py-1 rounded transition-opacity hover:opacity-70"
                        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                        수정
                      </button>
                      {bot.status === "active" && (
                        <button
                          type="button"
                          onClick={() => handleDelete(bot)}
                          className="text-xs px-2.5 py-1 rounded transition-opacity hover:opacity-70"
                          style={{ background: "rgba(246,70,93,0.15)", border: "1px solid rgba(246,70,93,0.3)", color: "var(--red)" }}>
                          퇴출
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* System Management */}
      <div className="mt-12 p-6 rounded-xl" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>시스템 관리</h2>
        <p className="text-xs mb-4" style={{ color: "var(--text-secondary)" }}>
          트레이딩 모드 전환 및 데이터 초기화
        </p>

        <div className="flex items-center gap-4 mb-6 p-4 rounded-lg" style={{ background: "var(--bg-base)" }}>
          <div className="flex-1">
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              현재 모드: <span style={{ color: liveTrading ? "var(--green)" : "#ef4444" }}>
                {liveTrading ? "운영 (Live)" : "시뮬레이션"}
              </span>
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              {liveTrading ? "Binance 실거래 주문이 실행됩니다" : "내부 매칭 엔진으로 시뮬레이션합니다"}
            </p>
          </div>
          <button
            type="button"
            onClick={async () => {
              let confirmBody = {};
              if (liveTrading) {
                const input = prompt(
                  "⚠️ 경고: 시뮬레이션 전환 시 실제 유저 잔액이 가짜 거래로 오염될 수 있습니다.\n" +
                  "활성 구독이 있다면 반드시 모든 봇을 중지한 후 전환하세요.\n\n" +
                  '확인하려면 "SWITCH_TO_SIM"을 입력하세요:'
                );
                if (input !== "SWITCH_TO_SIM") return;
                confirmBody = { confirm: "SWITCH_TO_SIM" };
              } else {
                if (!confirm("운영 모드(실거래)로 전환하시겠습니까?\nBinance에서 실제 주문이 실행됩니다.")) return;
              }
              try {
                const res = await apiFetch("/api/admin/toggle-live-trading", {
                  method: "POST",
                  body: JSON.stringify(confirmBody),
                });
                setLiveTrading(res.live_trading);
                alert(res.message);
              } catch (e) {
                alert(e instanceof Error ? e.message : "전환 실패");
              }
            }}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{
              background: liveTrading ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
              color: liveTrading ? "#ef4444" : "var(--green)",
              border: `1px solid ${liveTrading ? "rgba(239,68,68,0.3)" : "rgba(34,197,94,0.3)"}`,
            }}>
            {liveTrading ? "시뮬레이션으로 전환" : "운영 모드로 전환"}
          </button>
        </div>

        <button
          type="button"
          onClick={async () => {
            const input = prompt('모든 거래 데이터(주문, 잔액, 구독, 출금 등)가 삭제됩니다.\n확인하려면 "RESET"을 입력하세요:');
            if (input !== "RESET") return;
            try {
              const res = await apiFetch("/api/admin/reset-trading-data", {
                method: "POST",
                body: JSON.stringify({ confirm: "RESET" }),
              });
              alert(res.message || "초기화 완료");
            } catch (e) {
              alert(e instanceof Error ? e.message : "초기화 실패");
            }
          }}
          className="px-4 py-2 rounded-lg text-sm font-medium"
          style={{ background: "rgba(239,68,68,0.15)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.3)" }}>
          거래 데이터 초기화
        </button>
      </div>

      {modal.open && (
        <BotModal
          initial={modal.bot}
          onClose={() => setModal({ open: false, bot: null })}
          onSave={() => { setModal({ open: false, bot: null }); loadBots(); }}
        />
      )}
    </div>
  );
}
