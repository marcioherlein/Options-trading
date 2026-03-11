"""
Income-generating strategies from Natenberg:
- Covered Call (hold stock + sell OTM call)
- Cash-Secured Put (sell OTM put, ready to buy stock)
- Bull Put Spread (credit spread, income + defined risk)
- Bear Call Spread (credit spread, income + defined risk)
"""
from datetime import datetime


def _dte(opt: dict) -> int:
    try:
        exp = datetime.strptime(str(opt["expiry"])[:10], "%Y-%m-%d")
        return max((exp - datetime.utcnow()).days, 0)
    except Exception:
        return 0


def _by_delta(chain: list[dict], target: float, opt_type: str) -> dict | None:
    candidates = [o for o in chain if o["type"] == opt_type and o.get("greeks", {}).get("delta") is not None]
    return min(candidates, key=lambda o: abs(abs(o["greeks"]["delta"]) - target)) if candidates else None


def evaluate_income_strategies(chain: list[dict], S: float, vol_summary: dict) -> list[dict]:
    strategies = []
    expiries = sorted(set(o["expiry"] for o in chain))

    for expiry in expiries:
        exp_chain = [o for o in chain if o["expiry"] == expiry]
        dte = _dte(exp_chain[0]) if exp_chain else 0
        if dte == 0:
            continue

        otm_call = _by_delta(exp_chain, 0.30, "call")
        otm_put  = _by_delta(exp_chain, 0.30, "put")
        far_put  = _by_delta(exp_chain, 0.15, "put")
        far_call = _by_delta(exp_chain, 0.15, "call")

        # --- Covered Call ---
        if otm_call:
            premium = otm_call.get("mid", 0)
            if premium > 0:
                strategies.append({
                    "name": "Covered Call",
                    "type": "sell_vol",
                    "description": "Hold GGAL shares, sell OTM call. Generate income; cap upside.",
                    "legs": [
                        {"action": "HOLD", "type": "stock", "strike": S,                     "expiry": "-",    "qty": 100},
                        {"action": "SELL", "type": "call",  "strike": otm_call["strike"],     "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": round(otm_call["strike"] - S + premium, 4),
                    "max_loss": round(S - premium, 4),  # Stock goes to zero
                    "breakevens": [round(S - premium, 2)],
                    "net_delta": round(1 - abs(otm_call.get("greeks", {}).get("delta", 0.3)), 4),
                    "net_theta": round(-otm_call.get("greeks", {}).get("theta", 0), 6),
                    "net_vega": round(-otm_call.get("greeks", {}).get("vega", 0), 6),
                    "prob_of_profit": round((1 - abs(otm_call.get("greeks", {}).get("delta", 0.3))) * 100, 1),
                    "capital_required": round(S, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "Classic income trade. Most effective when IV > HV — premium is rich.",
                })

        # --- Cash-Secured Put ---
        if otm_put:
            premium = otm_put.get("mid", 0)
            if premium > 0:
                strategies.append({
                    "name": "Cash-Secured Put",
                    "type": "sell_vol",
                    "description": "Sell OTM put. Collect premium; obligated to buy GGAL if assigned.",
                    "legs": [
                        {"action": "SELL", "type": "put", "strike": otm_put["strike"], "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": round(premium, 4),
                    "max_loss": round(otm_put["strike"] - premium, 4),
                    "breakevens": [round(otm_put["strike"] - premium, 2)],
                    "net_delta": round(otm_put.get("greeks", {}).get("delta", -0.3), 4),
                    "net_theta": round(-otm_put.get("greeks", {}).get("theta", 0), 6),
                    "net_vega": round(-otm_put.get("greeks", {}).get("vega", 0), 6),
                    "prob_of_profit": round((1 - abs(otm_put.get("greeks", {}).get("delta", 0.3))) * 100, 1),
                    "capital_required": round(otm_put["strike"], 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "Sell rich premium. If assigned, you acquire GGAL at a discount.",
                })

        # --- Bull Put Spread (credit) ---
        if otm_put and far_put and otm_put["strike"] > far_put["strike"]:
            net_credit = otm_put.get("mid", 0) - far_put.get("mid", 0)
            width = otm_put["strike"] - far_put["strike"]
            if net_credit > 0 and width > 0:
                strategies.append({
                    "name": "Bull Put Spread",
                    "type": "sell_vol",
                    "description": "Sell higher-strike put, buy lower-strike put. Bullish credit spread.",
                    "legs": [
                        {"action": "SELL", "type": "put", "strike": otm_put["strike"],  "expiry": expiry, "qty": 1},
                        {"action": "BUY",  "type": "put", "strike": far_put["strike"],  "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": round(net_credit, 4),
                    "max_loss": round(width - net_credit, 4),
                    "breakevens": [round(otm_put["strike"] - net_credit, 2)],
                    "net_delta": round((otm_put.get("greeks", {}).get("delta", -0.3) -
                                        far_put.get("greeks", {}).get("delta", -0.15)), 4),
                    "net_theta": round(-(otm_put.get("greeks", {}).get("theta", 0) -
                                         far_put.get("greeks", {}).get("theta", 0)), 6),
                    "net_vega": round(-(otm_put.get("greeks", {}).get("vega", 0) -
                                        far_put.get("greeks", {}).get("vega", 0)), 6),
                    "prob_of_profit": round((1 - abs(otm_put.get("greeks", {}).get("delta", 0.3))) * 100, 1),
                    "capital_required": round(width - net_credit, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "Defined-risk credit spread. Profit if GGAL stays above short put strike.",
                })

        # --- Bear Call Spread (credit) ---
        if otm_call and far_call and far_call["strike"] > otm_call["strike"]:
            net_credit = otm_call.get("mid", 0) - far_call.get("mid", 0)
            width = far_call["strike"] - otm_call["strike"]
            if net_credit > 0 and width > 0:
                strategies.append({
                    "name": "Bear Call Spread",
                    "type": "sell_vol",
                    "description": "Sell lower-strike call, buy higher-strike call. Bearish credit spread.",
                    "legs": [
                        {"action": "SELL", "type": "call", "strike": otm_call["strike"], "expiry": expiry, "qty": 1},
                        {"action": "BUY",  "type": "call", "strike": far_call["strike"], "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": round(net_credit, 4),
                    "max_loss": round(width - net_credit, 4),
                    "breakevens": [round(otm_call["strike"] + net_credit, 2)],
                    "net_delta": round((otm_call.get("greeks", {}).get("delta", 0.3) -
                                        far_call.get("greeks", {}).get("delta", 0.15)), 4),
                    "net_theta": round(-(otm_call.get("greeks", {}).get("theta", 0) -
                                         far_call.get("greeks", {}).get("theta", 0)), 6),
                    "net_vega": round(-(otm_call.get("greeks", {}).get("vega", 0) -
                                        far_call.get("greeks", {}).get("vega", 0)), 6),
                    "prob_of_profit": round((1 - abs(otm_call.get("greeks", {}).get("delta", 0.3))) * 100, 1),
                    "capital_required": round(width - net_credit, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "Defined-risk credit spread. Profit if GGAL stays below short call strike.",
                })

    return strategies
