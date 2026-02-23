import { create } from "zustand";

interface BinanceTicker {
  symbol: string;        // e.g. "BTC_USDT" (internal pair key for routing)
  displaySymbol: string; // e.g. "BTC/USDT"
  lastPrice: string;
  priceChangePercent: string;
  highPrice: string;
  lowPrice: string;
  volume: string;        // base asset volume
  quoteVolume: string;   // USDT volume (turnover)
}

interface PairListStore {
  allPairs: BinanceTicker[];
  searchQuery: string;
  loading: boolean;
  error: string | null;
  fetchPairs: () => Promise<void>;
  setSearchQuery: (q: string) => void;
  getFilteredPairs: () => BinanceTicker[];
}

export const usePairListStore = create<PairListStore>((set, get) => ({
  allPairs: [],
  searchQuery: "",
  loading: false,
  error: null,

  fetchPairs: async () => {
    set({ loading: true, error: null });
    try {
      const res = await fetch("https://api.binance.com/api/v3/ticker/24hr");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Array<{
        symbol: string;
        lastPrice: string;
        priceChangePercent: string;
        highPrice: string;
        lowPrice: string;
        volume: string;
        quoteVolume: string;
      }> = await res.json();

      const usdtPairs: BinanceTicker[] = data
        .filter((item) => item.symbol.endsWith("USDT"))
        .map((item) => {
          const base = item.symbol.slice(0, -4);
          return {
            symbol: `${base}_USDT`,
            displaySymbol: `${base}/USDT`,
            lastPrice: item.lastPrice,
            priceChangePercent: item.priceChangePercent,
            highPrice: item.highPrice,
            lowPrice: item.lowPrice,
            volume: item.volume,
            quoteVolume: item.quoteVolume,
          };
        })
        .sort(
          (a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume)
        );

      set({ allPairs: usdtPairs });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ loading: false });
    }
  },

  setSearchQuery: (q: string) => {
    set({ searchQuery: q });
  },

  getFilteredPairs: () => {
    const { allPairs, searchQuery } = get();
    if (!searchQuery) return allPairs;
    const query = searchQuery.toLowerCase();
    return allPairs.filter(
      (pair) =>
        pair.displaySymbol.toLowerCase().includes(query) ||
        pair.symbol.toLowerCase().includes(query)
    );
  },
}));
