"use client";
import type { VolSummary } from "@/app/lib/types";

interface Props {
  volSummary: VolSummary;
  stockPrice: number;
  stockBid: number;
  stockAsk: number;
  stockVolume: number;
  timestamp: string;
  connected: boolean;
}

function StatCard({ label, value, sub, color = "text-white" }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="bg-zinc-800 rounded-lg p-3">
      <p className="text-zinc-400 text-xs uppercase tracking-wide mb-1">{label}</p>
      <p className={`font-semibold text-lg font-mono ${color}`}>{value}</p>
      {sub && <p className="text-zinc-500 text-xs mt-0.5">{sub}</p>}
    </div>
  );
}

export default function GreeksDashboard({
  volSummary, stockPrice, stockBid, stockAsk, stockVolume, timestamp, connected
}: Props) {
  const ts = timestamp ? new Date(timestamp + "Z").toLocaleTimeString() : "--:--:--";

  return (
    <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800 space-y-4">
      {/* Header with connection status */}
      <div className="flex items-center justify-between">
        <h2 className="text-white font-semibold text-base">Market Overview</h2>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
          <span className="text-xs text-zinc-400">{connected ? `Live · ${ts}` : "Reconnecting..."}</span>
        </div>
      </div>

      {/* Stock quote */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <StatCard
          label="GGAL Price"
          value={stockPrice ? `$${stockPrice.toFixed(2)}` : "—"}
          color="text-yellow-300"
        />
        <StatCard
          label="Bid / Ask"
          value={stockBid && stockAsk ? `${stockBid.toFixed(2)} / ${stockAsk.toFixed(2)}` : "—"}
          color="text-zinc-300"
        />
        <StatCard
          label="Volume"
          value={stockVolume ? stockVolume.toLocaleString() : "—"}
          color="text-zinc-300"
        />
        <StatCard
          label="Spread"
          value={stockBid && stockAsk ? `${(stockAsk - stockBid).toFixed(2)}` : "—"}
          sub={stockBid && stockAsk ? `${(((stockAsk - stockBid) / stockPrice) * 100).toFixed(2)}%` : undefined}
          color="text-zinc-300"
        />
      </div>

      {/* Volatility metrics */}
      <div>
        <p className="text-zinc-400 text-xs uppercase tracking-wide font-medium mb-2">Volatility Metrics</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <StatCard
            label="HV 20-Day"
            value={volSummary.hv_20 ? `${(volSummary.hv_20 * 100).toFixed(1)}%` : "—"}
            color="text-purple-400"
          />
          <StatCard
            label="HV 30-Day"
            value={volSummary.hv_30 ? `${(volSummary.hv_30 * 100).toFixed(1)}%` : "—"}
            color="text-purple-400"
          />
          <StatCard
            label="HV 60-Day"
            value={volSummary.hv_60 ? `${(volSummary.hv_60 * 100).toFixed(1)}%` : "—"}
            color="text-purple-400"
          />
          <StatCard
            label="ATM IV"
            value={volSummary.atm_iv ? `${(volSummary.atm_iv * 100).toFixed(1)}%` : "—"}
            color="text-blue-400"
          />
          <StatCard
            label="IV Rank"
            value={volSummary.iv_rank !== null && volSummary.iv_rank !== undefined
              ? `${volSummary.iv_rank.toFixed(0)}%`
              : "—"}
            sub="0–100 scale"
            color={
              (volSummary.iv_rank ?? 50) > 60 ? "text-red-400" :
              (volSummary.iv_rank ?? 50) < 40 ? "text-green-400" : "text-yellow-400"
            }
          />
          <StatCard
            label="IV / HV Ratio"
            value={volSummary.iv_vs_hv_ratio ? volSummary.iv_vs_hv_ratio.toFixed(2) : "—"}
            sub={
              volSummary.vol_regime === "overpriced" ? "Sell vol signal" :
              volSummary.vol_regime === "underpriced" ? "Buy vol signal" : "Neutral"
            }
            color={
              volSummary.vol_regime === "overpriced" ? "text-red-400" :
              volSummary.vol_regime === "underpriced" ? "text-green-400" : "text-yellow-400"
            }
          />
        </div>
      </div>

      {/* Natenberg signal */}
      <div className={`rounded-lg px-4 py-3 border text-sm ${
        volSummary.vol_regime === "overpriced"
          ? "bg-red-900/20 border-red-800/40 text-red-300"
          : volSummary.vol_regime === "underpriced"
          ? "bg-green-900/20 border-green-800/40 text-green-300"
          : "bg-yellow-900/20 border-yellow-800/40 text-yellow-300"
      }`}>
        {volSummary.vol_regime === "overpriced" && (
          <><strong>Natenberg Signal:</strong> IV is elevated vs HV. Options appear <strong>overpriced</strong>. Prefer volatility-selling strategies (short straddles, iron condors, credit spreads).</>
        )}
        {volSummary.vol_regime === "underpriced" && (
          <><strong>Natenberg Signal:</strong> IV is depressed vs HV. Options appear <strong>underpriced</strong>. Prefer volatility-buying strategies (long straddles, strangles, backspreads).</>
        )}
        {volSummary.vol_regime === "fair" && (
          <><strong>Natenberg Signal:</strong> IV is in line with HV. Options are <strong>fairly priced</strong>. Focus on directional or income strategies.</>
        )}
      </div>
    </div>
  );
}
