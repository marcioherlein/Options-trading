"use client";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { VolSummary, VolSurfacePoint } from "@/app/lib/types";

interface Props {
  volSummary: VolSummary;
  volSurface: VolSurfacePoint[];
}

const REGIME_COLOR = {
  overpriced: "#f87171",   // red
  underpriced: "#4ade80", // green
  fair: "#facc15",         // yellow
};

const REGIME_LABEL = {
  overpriced: "IV > HV — Options Overpriced → Sell Vol",
  underpriced: "IV < HV — Options Underpriced → Buy Vol",
  fair: "IV ≈ HV — Options Fairly Priced",
};

export default function VolatilityChart({ volSummary, volSurface }: Props) {
  const regime = volSummary.vol_regime ?? "fair";
  const regimeColor = REGIME_COLOR[regime];

  // Build smile data: group by expiry, plot strike vs IV
  const expiryGroups: Record<string, { strike: number; call_iv?: number; put_iv?: number }[]> = {};
  for (const pt of volSurface) {
    if (!expiryGroups[pt.expiry]) expiryGroups[pt.expiry] = [];
    expiryGroups[pt.expiry].push({ strike: pt.strike, call_iv: pt.call_iv, put_iv: pt.put_iv });
  }

  const expiries = Object.keys(expiryGroups).sort();
  // Use first (nearest) expiry for smile chart
  const smileData = expiries.length > 0
    ? [...(expiryGroups[expiries[0]] ?? [])].sort((a, b) => a.strike - b.strike)
    : [];

  // HV comparison bars
  const hvData = [
    { name: "HV 20d", value: volSummary.hv_20 ? +(volSummary.hv_20 * 100).toFixed(1) : 0 },
    { name: "HV 30d", value: volSummary.hv_30 ? +(volSummary.hv_30 * 100).toFixed(1) : 0 },
    { name: "HV 60d", value: volSummary.hv_60 ? +(volSummary.hv_60 * 100).toFixed(1) : 0 },
    { name: "ATM IV", value: volSummary.atm_iv ? +(volSummary.atm_iv * 100).toFixed(1) : 0 },
  ];

  const ivRank = volSummary.iv_rank ?? null;

  return (
    <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-white font-semibold text-base">Volatility Dashboard</h2>
        <span
          className="text-xs font-semibold px-3 py-1 rounded-full border"
          style={{ color: regimeColor, borderColor: regimeColor }}
        >
          {REGIME_LABEL[regime]}
        </span>
      </div>

      {/* IV Rank Gauge */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "IV Rank", value: ivRank !== null ? `${ivRank.toFixed(0)}%` : "—" },
          { label: "IV Pct", value: volSummary.iv_percentile !== null ? `${volSummary.iv_percentile?.toFixed(0)}%` : "—" },
          { label: "ATM IV", value: volSummary.atm_iv ? `${(volSummary.atm_iv * 100).toFixed(1)}%` : "—" },
          { label: "IV/HV", value: volSummary.iv_vs_hv_ratio ? volSummary.iv_vs_hv_ratio.toFixed(2) : "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-zinc-800 rounded-lg p-3 text-center">
            <p className="text-zinc-400 text-xs mb-1">{label}</p>
            <p className="text-white font-semibold text-lg">{value}</p>
          </div>
        ))}
      </div>

      {/* IV vs HV comparison */}
      <div>
        <p className="text-zinc-400 text-xs mb-2 font-medium uppercase tracking-wide">IV vs Historical Volatility</p>
        <div className="flex gap-3 flex-wrap">
          {hvData.map(({ name, value }) => (
            <div key={name} className="flex items-center gap-2 bg-zinc-800 rounded px-3 py-2">
              <span className={`w-2 h-2 rounded-full ${name === "ATM IV" ? "bg-blue-400" : "bg-purple-400"}`} />
              <span className="text-zinc-400 text-xs">{name}</span>
              <span className="text-white font-mono text-sm font-semibold">{value}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* IV Smile Chart */}
      {smileData.length > 0 && (
        <div>
          <p className="text-zinc-400 text-xs mb-2 font-medium uppercase tracking-wide">
            IV Smile — {expiries[0]}
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={smileData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="strike"
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickFormatter={(v) => v.toFixed(0)}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickFormatter={(v) => `${v}%`}
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(val: number) => [`${val?.toFixed(1)}%`]}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }} />
              <Line type="monotone" dataKey="call_iv" stroke="#4ade80" dot={false} name="Call IV %" strokeWidth={2} />
              <Line type="monotone" dataKey="put_iv"  stroke="#f87171" dot={false} name="Put IV %"  strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 52-week IV range */}
      {volSummary.iv_52w_low !== undefined && (
        <div>
          <p className="text-zinc-400 text-xs mb-1 font-medium uppercase tracking-wide">52-Week IV Range</p>
          <div className="relative h-4 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="absolute top-0 h-4 rounded-full"
              style={{
                left: 0,
                width: ivRank !== null ? `${ivRank}%` : "50%",
                backgroundColor: regimeColor,
                opacity: 0.7,
              }}
            />
          </div>
          <div className="flex justify-between text-xs text-zinc-500 mt-1">
            <span>{(volSummary.iv_52w_low * 100).toFixed(1)}% Low</span>
            <span>{(volSummary.iv_52w_high * 100).toFixed(1)}% High</span>
          </div>
        </div>
      )}
    </div>
  );
}
