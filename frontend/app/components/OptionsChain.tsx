"use client";
import { useState } from "react";
import type { OptionContract } from "@/app/lib/types";

interface Props {
  chain: OptionContract[];
  stockPrice: number;
}

type SortKey = "strike" | "iv" | "volume" | "open_interest" | "greeks.delta";

function getVal(opt: OptionContract, key: SortKey): number {
  if (key === "greeks.delta") return Math.abs(opt.greeks?.delta ?? 0);
  return (opt as unknown as Record<string, number>)[key] ?? 0;
}

export default function OptionsChain({ chain, stockPrice }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("strike");
  const [sortAsc, setSortAsc] = useState(true);
  const [filter, setFilter] = useState<"all" | "call" | "put">("all");
  const [expiryFilter, setExpiryFilter] = useState("all");

  const expiries = ["all", ...Array.from(new Set(chain.map((o) => o.expiry))).sort()];

  const sorted = [...chain]
    .filter((o) => filter === "all" || o.type === filter)
    .filter((o) => expiryFilter === "all" || o.expiry === expiryFilter)
    .sort((a, b) => {
      const diff = getVal(a, sortKey) - getVal(b, sortKey);
      return sortAsc ? diff : -diff;
    });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setAscDir((v) => !v);
    else { setSortKey(key); setSortAsc(true); }
  };

  function setAscDir(fn: (v: boolean) => boolean) {
    setSortAsc(fn);
  }

  const th = (label: string, key: SortKey) => (
    <th
      className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase cursor-pointer hover:text-white select-none"
      onClick={() => handleSort(key)}
    >
      {label} {sortKey === key ? (sortAsc ? "↑" : "↓") : ""}
    </th>
  );

  const ivColor = (iv: number) =>
    iv > 0.6 ? "text-red-400" : iv > 0.4 ? "text-yellow-400" : "text-green-400";

  return (
    <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h2 className="text-white font-semibold text-base">Options Chain — GGAL</h2>
        <div className="flex gap-2 text-xs">
          {(["all", "call", "put"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full border ${
                filter === f
                  ? "bg-blue-600 border-blue-500 text-white"
                  : "border-zinc-700 text-zinc-400 hover:text-white"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
          <select
            className="bg-zinc-800 border border-zinc-700 text-zinc-300 text-xs rounded px-2 py-1"
            value={expiryFilter}
            onChange={(e) => setExpiryFilter(e.target.value)}
          >
            {expiries.map((e) => (
              <option key={e} value={e}>{e === "all" ? "All Expiries" : e}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase">Type</th>
              {th("Strike", "strike")}
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase">Expiry</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase">Bid</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase">Ask</th>
              {th("IV %", "iv")}
              {th("Delta", "greeks.delta")}
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase">Theta</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase">Vega</th>
              {th("Volume", "volume")}
              {th("OI", "open_interest")}
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-400 uppercase">ITM</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((opt, i) => {
              const isAtm = Math.abs(opt.strike - stockPrice) / stockPrice < 0.02;
              return (
                <tr
                  key={`${opt.symbol}-${i}`}
                  className={`border-b border-zinc-800/50 hover:bg-zinc-800/40 transition-colors ${
                    isAtm ? "bg-zinc-800/20" : ""
                  }`}
                >
                  <td className="px-3 py-2">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                      opt.type === "call" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
                    }`}>
                      {opt.type.toUpperCase()}
                    </span>
                  </td>
                  <td className={`px-3 py-2 font-mono font-semibold ${isAtm ? "text-yellow-300" : "text-white"}`}>
                    {opt.strike.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-zinc-400 text-xs">{opt.expiry}</td>
                  <td className="px-3 py-2 text-zinc-300 font-mono">{opt.bid.toFixed(2)}</td>
                  <td className="px-3 py-2 text-zinc-300 font-mono">{opt.ask.toFixed(2)}</td>
                  <td className={`px-3 py-2 font-mono font-semibold ${ivColor(opt.iv)}`}>
                    {(opt.iv * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 text-zinc-300 font-mono">
                    {(opt.greeks?.delta ?? 0).toFixed(3)}
                  </td>
                  <td className="px-3 py-2 text-orange-400 font-mono text-xs">
                    {(opt.greeks?.theta ?? 0).toFixed(4)}
                  </td>
                  <td className="px-3 py-2 text-purple-400 font-mono text-xs">
                    {(opt.greeks?.vega ?? 0).toFixed(4)}
                  </td>
                  <td className="px-3 py-2 text-zinc-400 font-mono">{opt.volume.toLocaleString()}</td>
                  <td className="px-3 py-2 text-zinc-400 font-mono">{opt.open_interest.toLocaleString()}</td>
                  <td className="px-3 py-2">
                    {opt.is_itm ? (
                      <span className="text-xs text-green-400">✓ ITM</span>
                    ) : (
                      <span className="text-xs text-zinc-600">OTM</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={12} className="text-center text-zinc-500 py-8 text-sm">
                  No options data yet — waiting for live feed...
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
