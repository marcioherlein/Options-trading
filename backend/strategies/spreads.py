"""
Spread strategies from Natenberg:
- Bull Call Spread (debit, directional bullish)
- Bear Put Spread (debit, directional bearish)
- Bull Put Spread (credit, sell vol + bullish)
- Bear Call Spread (credit, sell vol + bearish)
- Iron Condor (sell vol, high IV rank)
- Calendar Spread (time spread, long vol on back month)
- Diagonal Spread (directional + vol)
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


def evaluate_spreads(chain: list[dict], S: float, vol_summary: dict) -> list[dict]:
    strategies = []
    expiries = sorted(set(o["expiry"] for o in chain))

    for i, expiry in enumerate(expiries):
        exp_chain = [o for o in chain if o["expiry"] == expiry]
        dte = _dte(exp_chain[0]) if exp_chain else 0
        if dte == 0:
            continue

        # Find key strikes
        atm_call = _by_delta(exp_chain, 0.50, "call")
        atm_put  = _by_delta(exp_chain, 0.50, "put")
        otm_call = _by_delta(exp_chain, 0.30, "call")
        otm_put  = _by_delta(exp_chain, 0.30, "put")
        far_call = _by_delta(exp_chain, 0.15, "call")
        far_put  = _by_delta(exp_chain, 0.15, "put")

        # --- Bull Call Spread (debit) ---
        if atm_call and otm_call and atm_call["strike"] < otm_call["strike"]:
            cost = atm_call.get("mid", 0) - otm_call.get("mid", 0)
            width = otm_call["strike"] - atm_call["strike"]
            if cost > 0 and width > 0:
                strategies.append({
                    "name": "Bull Call Spread",
                    "type": "directional",
                    "description": "Buy lower-strike call, sell higher-strike call. Bullish, defined risk.",
                    "legs": [
                        {"action": "BUY",  "type": "call", "strike": atm_call["strike"], "expiry": expiry, "qty": 1},
                        {"action": "SELL", "type": "call", "strike": otm_call["strike"], "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": round(width - cost, 4),
                    "max_loss": round(cost, 4),
                    "breakevens": [round(atm_call["strike"] + cost, 2)],
                    "net_delta": round((atm_call.get("greeks", {}).get("delta", 0.5) -
                                        otm_call.get("greeks", {}).get("delta", 0.3)), 4),
                    "net_theta": round((atm_call.get("greeks", {}).get("theta", 0) -
                                        otm_call.get("greeks", {}).get("theta", 0)), 6),
                    "net_vega": round((atm_call.get("greeks", {}).get("vega", 0) -
                                       otm_call.get("greeks", {}).get("vega", 0)), 6),
                    "prob_of_profit": round(abs(otm_call.get("greeks", {}).get("delta", 0.3)) * 100, 1),
                    "capital_required": round(cost, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "Defined-risk bullish position. Lower cost than buying a naked call.",
                })

        # --- Bear Put Spread (debit) ---
        if atm_put and otm_put and atm_put["strike"] > otm_put["strike"]:
            cost = atm_put.get("mid", 0) - otm_put.get("mid", 0)
            width = atm_put["strike"] - otm_put["strike"]
            if cost > 0 and width > 0:
                strategies.append({
                    "name": "Bear Put Spread",
                    "type": "directional",
                    "description": "Buy higher-strike put, sell lower-strike put. Bearish, defined risk.",
                    "legs": [
                        {"action": "BUY",  "type": "put", "strike": atm_put["strike"],  "expiry": expiry, "qty": 1},
                        {"action": "SELL", "type": "put", "strike": otm_put["strike"],  "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": round(width - cost, 4),
                    "max_loss": round(cost, 4),
                    "breakevens": [round(atm_put["strike"] - cost, 2)],
                    "net_delta": round((atm_put.get("greeks", {}).get("delta", -0.5) -
                                        otm_put.get("greeks", {}).get("delta", -0.3)), 4),
                    "net_theta": round((atm_put.get("greeks", {}).get("theta", 0) -
                                        otm_put.get("greeks", {}).get("theta", 0)), 6),
                    "net_vega": round((atm_put.get("greeks", {}).get("vega", 0) -
                                       otm_put.get("greeks", {}).get("vega", 0)), 6),
                    "prob_of_profit": round(abs(otm_put.get("greeks", {}).get("delta", 0.3)) * 100, 1),
                    "capital_required": round(cost, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "Defined-risk bearish position. Lower cost than buying a naked put.",
                })

        # --- Iron Condor (sell vol) ---
        if all([otm_put, atm_put, atm_call, otm_call]):
            credit = (otm_put.get("mid", 0) + atm_put.get("mid", 0) +
                      atm_call.get("mid", 0) + otm_call.get("mid", 0))
            # Simplified: short strangle + wings
            if far_put and far_call and otm_put and otm_call:
                net_credit = otm_put.get("mid", 0) + otm_call.get("mid", 0) - far_put.get("mid", 0) - far_call.get("mid", 0)
                put_width = otm_put["strike"] - far_put["strike"]
                if net_credit > 0 and put_width > 0:
                    strategies.append({
                        "name": "Iron Condor",
                        "type": "sell_vol",
                        "description": "Sell OTM strangle, buy further OTM wings. High-prob range-bound trade.",
                        "legs": [
                            {"action": "BUY",  "type": "put",  "strike": far_put["strike"],  "expiry": expiry, "qty": 1},
                            {"action": "SELL", "type": "put",  "strike": otm_put["strike"],  "expiry": expiry, "qty": 1},
                            {"action": "SELL", "type": "call", "strike": otm_call["strike"], "expiry": expiry, "qty": 1},
                            {"action": "BUY",  "type": "call", "strike": far_call["strike"] if far_call else otm_call["strike"] + put_width, "expiry": expiry, "qty": 1},
                        ],
                        "max_profit": round(net_credit, 4),
                        "max_loss": round(put_width - net_credit, 4),
                        "breakevens": [
                            round(otm_put["strike"] - net_credit, 2),
                            round(otm_call["strike"] + net_credit, 2),
                        ],
                        "net_delta": 0.0,
                        "net_theta": round(-(otm_put.get("greeks", {}).get("theta", 0) +
                                             otm_call.get("greeks", {}).get("theta", 0)), 6),
                        "net_vega": round(-(otm_put.get("greeks", {}).get("vega", 0) +
                                            otm_call.get("greeks", {}).get("vega", 0)), 6),
                        "prob_of_profit": 68.0,
                        "capital_required": round(put_width - net_credit, 4),
                        "dte": dte,
                        "expiry": expiry,
                        "natenberg_note": "Best in high IV environments. Defined risk. Natenberg's premium selling workhorse.",
                    })

        # --- Calendar Spread (time spread) — only if next expiry exists ---
        if i + 1 < len(expiries):
            next_expiry = expiries[i + 1]
            next_chain = [o for o in chain if o["expiry"] == next_expiry]
            front_call = _by_delta(exp_chain, 0.50, "call")
            back_call  = _by_delta(next_chain, 0.50, "call")
            if front_call and back_call and front_call["strike"] == back_call["strike"]:
                cost = back_call.get("mid", 0) - front_call.get("mid", 0)
                if cost > 0:
                    strategies.append({
                        "name": "Calendar Spread",
                        "type": "sell_vol",
                        "description": "Sell front-month ATM call, buy back-month ATM call. Profits from time decay.",
                        "legs": [
                            {"action": "SELL", "type": "call", "strike": front_call["strike"], "expiry": expiry,      "qty": 1},
                            {"action": "BUY",  "type": "call", "strike": back_call["strike"],  "expiry": next_expiry, "qty": 1},
                        ],
                        "max_profit": round(cost * 0.5, 4),  # Approximate
                        "max_loss": round(cost, 4),
                        "breakevens": [
                            round(front_call["strike"] - cost, 2),
                            round(front_call["strike"] + cost, 2),
                        ],
                        "net_delta": 0.0,
                        "net_theta": round(-front_call.get("greeks", {}).get("theta", 0), 6),
                        "net_vega": round(back_call.get("greeks", {}).get("vega", 0) -
                                          front_call.get("greeks", {}).get("vega", 0), 6),
                        "prob_of_profit": 55.0,
                        "capital_required": round(cost, 4),
                        "dte": dte,
                        "expiry": expiry,
                        "natenberg_note": "Profits from front-month IV collapse relative to back month. Vega-positive.",
                    })

    return strategies
