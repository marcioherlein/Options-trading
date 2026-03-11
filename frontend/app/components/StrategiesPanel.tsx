"use client";
import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";
import type { Strategy } from "@/app/lib/types";

interface Props {
  strategies: Strategy[];
  stockPrice: number;
}

const TYPE_CONFIG = {
  sell_vol:    { label: "Sell Vol",    color: "#f87171", bg: "bg-red-900/30",    border: "border-red-800/50" },
  buy_vol:     { label: "Buy Vol",     color: "#4ade80", bg: "bg-green-900/30",  border: "border-green-800/50" },
  directional: { label: "Directional", color: "#60a5fa", bg: "bg-blue-900/30",   border: "border-blue-800/50" },
  neutral:     { label: "Neutral/Arb", color: "#facc15", bg: "bg-yellow-900/30", border: "border-yellow-800/50" },
};

function buildPnLData(strategy: Strategy, stockPrice: number) {
  const range = stockPrice * 0.3;
  const steps = 60;
  const data = [];
  for (let i = 0; i <= steps; i++) {
    const S = stockPrice - range + (2 * range * i) / steps;
    let pnl = 0;

    for (const leg of strategy.legs) {
      if (leg.type === "stock") {
        pnl += (leg.action === "BUY" ? 1 : -1) * (S - stockPrice) * leg.qty;
        continue;
      }
      const isCall = leg.type === "call";
      const intrinsic = isCall ? Math.max(S - leg.strike, 0) : Math.max(leg.strike - S, 0);
      const dir = leg.action === "BUY" ? 1 : -1;
      pnl += dir * intrinsic * leg.qty;
    }

    // Subtract or add premium (net debit/credit approximation)
    data.push({ price: +S.toFixed(2), pnl: +pnl.toFixed(4) });
  }
  return data;
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 70 ? "#4ade80" : score >= 50 ? "#facc15" : "#f87171";
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-1.5 rounded-full transition-all" style={{ width: `${score}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-semibold" style={{ color }}>{score.toFixed(0)}</span>
    </div>
  );
}

export default function StrategiesPanel({ strategies, stockPrice }: Props) {
  const [selected, setSelected] = useState<number>(0);

  if (!strategies.length) {
    return (
      <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800 text-center text-zinc-500 text-sm py-12">
        Waiting for strategy analysis...
      </div>
    );
  }

  const top5 = strategies.slice(0, 5);
  const strat = top5[selected];
  const pnlData = strat ? buildPnLData(strat, stockPrice) : [];
  const cfg = strat ? TYPE_CONFIG[strat.type] : TYPE_CONFIG.neutral;

  return (
    <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
      <h2 className="text-white font-semibold text-base mb-3">Top Strategies — Today</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Strategy list */}
        <div className="space-y-2">
          {top5.map((s, i) => {
            const c = TYPE_CONFIG[s.type];
            return (
              <button
                key={`${s.name}-${i}`}
                onClick={() => setSelected(i)}
                className={`w-full text-left rounded-lg p-3 border transition-all ${c.bg} ${c.border} ${
                  selected === i ? "ring-1 ring-offset-0" : "opacity-80 hover:opacity-100"
                }`}
                style={selected === i ? { outline: `1px solid ${c.color}` } : {}}
              >
                <div className="flex items-center justify-between">
                  <span className="text-white font-semibold text-sm">{s.name}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ color: c.color, backgroundColor: `${c.color}20` }}>
                    {c.label}
                  </span>
                </div>
                <ScoreBar score={s.score} />
                <p className="text-zinc-400 text-xs mt-1">{s.description}</p>
                <div className="flex gap-3 mt-2 text-xs text-zinc-400">
                  <span>DTE: <span className="text-white">{s.dte}</span></span>
                  <span>PoP: <span className="text-white">{s.prob_of_profit.toFixed(0)}%</span></span>
                  <span>Max Profit: <span className="text-green-400">
                    {s.max_profit !== null ? s.max_profit.toFixed(2) : "∞"}
                  </span></span>
                  <span>Max Loss: <span className="text-red-400">
                    {s.max_loss !== null ? s.max_loss.toFixed(2) : "∞"}
                  </span></span>
                </div>
              </button>
            );
          })}
        </div>

        {/* P&L diagram + details */}
        {strat && (
          <div className="space-y-3">
            <div>
              <p className="text-zinc-400 text-xs mb-1 font-medium uppercase tracking-wide">
                P&L at Expiry — {strat.name}
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={pnlData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="price" tick={{ fill: "#71717a", fontSize: 9 }} tickFormatter={(v) => v.toFixed(0)} />
                  <YAxis tick={{ fill: "#71717a", fontSize: 9 }} tickFormatter={(v) => v.toFixed(1)} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
                    labelStyle={{ color: "#a1a1aa", fontSize: 10 }}
                    formatter={(val) => [(val as number).toFixed(4), "P&L"]}
                    labelFormatter={(v) => `Price: ${Number(v).toFixed(2)}`}
                  />
                  <ReferenceLine y={0} stroke="#52525b" strokeDasharray="4 2" />
                  <ReferenceLine x={stockPrice} stroke="#facc15" strokeDasharray="4 2" label={{ value: "Current", fill: "#facc15", fontSize: 9 }} />
                  {strat.breakevens.map((be) => (
                    <ReferenceLine key={be} x={be} stroke={cfg.color} strokeDasharray="3 3"
                      label={{ value: `BE ${be.toFixed(0)}`, fill: cfg.color, fontSize: 8 }} />
                  ))}
                  <Line type="monotone" dataKey="pnl" stroke={cfg.color} dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Legs */}
            <div>
              <p className="text-zinc-400 text-xs mb-1 font-medium uppercase tracking-wide">Entry Legs</p>
              <div className="space-y-1">
                {strat.legs.map((leg, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs bg-zinc-800 rounded px-2 py-1">
                    <span className={`font-semibold ${leg.action === "BUY" ? "text-green-400" : leg.action === "SELL" ? "text-red-400" : "text-blue-400"}`}>
                      {leg.action}
                    </span>
                    <span className="text-white">{leg.qty}x</span>
                    <span className="text-zinc-300 uppercase">{leg.type}</span>
                    {leg.type !== "stock" && <span className="text-zinc-400">@ {leg.strike.toFixed(2)}</span>}
                    {leg.expiry !== "-" && <span className="text-zinc-500">{leg.expiry}</span>}
                  </div>
                ))}
              </div>
            </div>

            {/* Greeks */}
            <div>
              <p className="text-zinc-400 text-xs mb-1 font-medium uppercase tracking-wide">Net Greeks</p>
              <div className="grid grid-cols-3 gap-1 text-xs">
                {[
                  ["Δ Delta", strat.net_delta.toFixed(3), "text-blue-400"],
                  ["Θ Theta", strat.net_theta.toFixed(4), "text-orange-400"],
                  ["V Vega",  strat.net_vega.toFixed(4),  "text-purple-400"],
                ].map(([label, val, cls]) => (
                  <div key={label} className="bg-zinc-800 rounded p-2 text-center">
                    <p className="text-zinc-500 text-xs">{label}</p>
                    <p className={`font-mono font-semibold ${cls}`}>{val}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Natenberg note */}
            <div className="bg-zinc-800/60 rounded-lg px-3 py-2 border-l-2" style={{ borderColor: cfg.color }}>
              <p className="text-xs text-zinc-400 italic">{strat.natenberg_note}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
