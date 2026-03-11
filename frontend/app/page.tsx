"use client";
import { useSSE } from "@/app/hooks/useSSE";
import OptionsChain from "@/app/components/OptionsChain";
import VolatilityChart from "@/app/components/VolatilityChart";
import StrategiesPanel from "@/app/components/StrategiesPanel";
import GreeksDashboard from "@/app/components/GreeksDashboard";
import type { VolSummary } from "@/app/lib/types";

const EMPTY_VOL: VolSummary = {
  hv_20: 0, hv_30: 0, hv_60: 0,
  atm_iv: 0, iv_vs_hv_ratio: null, vol_regime: "fair",
  iv_rank: null, iv_percentile: null,
  iv_current: 0, iv_52w_low: 0, iv_52w_high: 0,
};

export default function DashboardPage() {
  const { data, connected, error } = useSSE();

  const stock      = data?.stock      ?? { symbol: "GGAL", price: 0, bid: 0, ask: 0, volume: 0 };
  const chain      = data?.chain      ?? [];
  const volSurface = data?.vol_surface ?? [];
  const volSummary = data?.vol_summary ?? EMPTY_VOL;
  const strategies = data?.strategies  ?? [];
  const timestamp  = data?.timestamp   ?? "";

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Top bar */}
      <header className="border-b border-zinc-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-white">GGAL Options</span>
          <span className="text-xs text-zinc-500 font-mono border border-zinc-700 rounded px-2 py-0.5">
            Natenberg Model
          </span>
        </div>
        {error && (
          <span className="text-xs text-red-400 bg-red-900/20 border border-red-800/40 rounded px-3 py-1">
            {error}
          </span>
        )}
        <div className="flex items-center gap-2 text-sm">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-zinc-600"}`} />
          <span className="text-zinc-400">{connected ? "Live" : "Connecting..."}</span>
        </div>
      </header>

      <main className="px-4 py-4 space-y-4 max-w-[1600px] mx-auto">
        {/* Market overview + vol dashboard */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <GreeksDashboard
            volSummary={volSummary}
            stockPrice={stock.price}
            stockBid={stock.bid}
            stockAsk={stock.ask}
            stockVolume={stock.volume}
            timestamp={timestamp}
            connected={connected}
          />
          <VolatilityChart
            volSummary={volSummary}
            volSurface={volSurface}
          />
        </div>

        {/* Strategy rankings */}
        <StrategiesPanel strategies={strategies} stockPrice={stock.price} />

        {/* Options chain */}
        <OptionsChain chain={chain} stockPrice={stock.price} />
      </main>
    </div>
  );
}
