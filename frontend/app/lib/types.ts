export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface OptionContract {
  symbol: string;
  strike: number;
  expiry: string;
  type: "call" | "put";
  bid: number;
  ask: number;
  last: number;
  mid: number;
  volume: number;
  open_interest: number;
  iv: number;
  theoretical_value: number;
  time_to_expiry: number;
  is_itm: boolean;
  greeks: Greeks;
}

export interface StrategyLeg {
  action: "BUY" | "SELL" | "HOLD";
  type: "call" | "put" | "stock";
  strike: number;
  expiry: string;
  qty: number;
}

export interface Strategy {
  name: string;
  type: "buy_vol" | "sell_vol" | "directional" | "neutral";
  description: string;
  legs: StrategyLeg[];
  max_profit: number | null;
  max_loss: number | null;
  breakevens: number[];
  net_delta: number;
  net_theta: number;
  net_vega: number;
  prob_of_profit: number;
  capital_required: number;
  dte: number;
  expiry: string;
  score: number;
  natenberg_note: string;
}

export interface VolSummary {
  hv_20: number;
  hv_30: number;
  hv_60: number;
  atm_iv: number;
  iv_vs_hv_ratio: number | null;
  vol_regime: "overpriced" | "underpriced" | "fair";
  iv_rank: number | null;
  iv_percentile: number | null;
  iv_current: number;
  iv_52w_low: number;
  iv_52w_high: number;
}

export interface VolSurfacePoint {
  strike: number;
  expiry: string;
  call_iv?: number;
  put_iv?: number;
}

export interface StockQuote {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
}

export interface StreamPayload {
  timestamp: string;
  stock: StockQuote;
  chain: OptionContract[];
  vol_surface: VolSurfacePoint[];
  vol_summary: VolSummary;
  strategies: Strategy[];
}
