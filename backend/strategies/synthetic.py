"""
Synthetic and arbitrage strategies from Natenberg:
- Synthetic Long Stock (long call + short put at same strike)
- Synthetic Short Stock (short call + long put at same strike)
- Conversion (long stock + synthetic short)
- Reversal / Reverse Conversion (short stock + synthetic long)

Note: Conversions/reversals exploit put-call parity mispricings.
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


def _parity_mispricing(call: dict, put: dict, S: float, r: float, t: float) -> float:
    """
    Put-Call parity: C - P = S - K * e^(-rT)
    Returns mispricing (positive = call overpriced, negative = put overpriced)
    """
    import math
    if call["strike"] != put["strike"]:
        return 0.0
    K = call["strike"]
    theoretical_diff = S - K * math.exp(-r * t)
    actual_diff = call.get("mid", 0) - put.get("mid", 0)
    return round(actual_diff - theoretical_diff, 4)


def evaluate_synthetics(chain: list[dict], S: float, vol_summary: dict) -> list[dict]:
    strategies = []
    r = float(__import__("os").getenv("RISK_FREE_RATE", "0.40"))
    expiries = sorted(set(o["expiry"] for o in chain))

    for expiry in expiries:
        exp_chain = [o for o in chain if o["expiry"] == expiry]
        dte = _dte(exp_chain[0]) if exp_chain else 0
        if dte == 0:
            continue
        t = dte / 252.0

        # Find matched call/put pairs at same strike
        call = _by_delta(exp_chain, 0.50, "call")
        put  = _by_delta(exp_chain, 0.50, "put")
        if not call or not put:
            continue
        strike = call["strike"]

        # --- Synthetic Long Stock ---
        cost = call.get("mid", 0) - put.get("mid", 0)
        strategies.append({
            "name": "Synthetic Long Stock",
            "type": "directional",
            "description": "Buy ATM call + sell ATM put. Replicates stock ownership at lower capital.",
            "legs": [
                {"action": "BUY",  "type": "call", "strike": strike, "expiry": expiry, "qty": 1},
                {"action": "SELL", "type": "put",  "strike": strike, "expiry": expiry, "qty": 1},
            ],
            "max_profit": None,
            "max_loss": round(strike - cost, 4),  # Equivalent to stock going to zero
            "breakevens": [round(strike + cost, 2)],
            "net_delta": round(
                call.get("greeks", {}).get("delta", 0.5) +
                put.get("greeks", {}).get("delta", -0.5), 4
            ),
            "net_theta": round(
                call.get("greeks", {}).get("theta", 0) -
                put.get("greeks", {}).get("theta", 0), 6
            ),
            "net_vega": round(
                call.get("greeks", {}).get("vega", 0) -
                put.get("greeks", {}).get("vega", 0), 6
            ),
            "prob_of_profit": 50.0,
            "capital_required": round(abs(cost) + strike * 0.10, 4),
            "dte": dte,
            "expiry": expiry,
            "natenberg_note": "Equivalent to owning stock but with less capital. Watch put-call parity.",
        })

        # --- Synthetic Short Stock ---
        credit = put.get("mid", 0) - call.get("mid", 0)
        strategies.append({
            "name": "Synthetic Short Stock",
            "type": "directional",
            "description": "Sell ATM call + buy ATM put. Replicates short stock without borrowing shares.",
            "legs": [
                {"action": "SELL", "type": "call", "strike": strike, "expiry": expiry, "qty": 1},
                {"action": "BUY",  "type": "put",  "strike": strike, "expiry": expiry, "qty": 1},
            ],
            "max_profit": round(strike + credit, 4),  # Stock goes to zero
            "max_loss": None,
            "breakevens": [round(strike - credit, 2)],
            "net_delta": round(
                put.get("greeks", {}).get("delta", -0.5) -
                call.get("greeks", {}).get("delta", 0.5), 4
            ),
            "net_theta": round(
                put.get("greeks", {}).get("theta", 0) -
                call.get("greeks", {}).get("theta", 0), 6
            ),
            "net_vega": round(
                put.get("greeks", {}).get("vega", 0) -
                call.get("greeks", {}).get("vega", 0), 6
            ),
            "prob_of_profit": 50.0,
            "capital_required": round(strike * 0.15, 4),
            "dte": dte,
            "expiry": expiry,
            "natenberg_note": "Short exposure without borrowing shares. Useful for hedging GGAL holdings.",
        })

        # --- Conversion / Reversal (arbitrage) ---
        mispricing = _parity_mispricing(call, put, S, r, t)
        if abs(mispricing) > 0.005:  # Only flag if meaningful mispricing
            if mispricing > 0:
                # Call overpriced vs put → Conversion: short call, long put, long stock
                strategies.append({
                    "name": "Conversion",
                    "type": "neutral",
                    "description": "Put-call parity arbitrage: short call + long put + long stock.",
                    "legs": [
                        {"action": "SELL", "type": "call",  "strike": strike, "expiry": expiry, "qty": 1},
                        {"action": "BUY",  "type": "put",   "strike": strike, "expiry": expiry, "qty": 1},
                        {"action": "BUY",  "type": "stock",  "strike": S,     "expiry": "-",    "qty": 100},
                    ],
                    "max_profit": round(mispricing, 4),
                    "max_loss": 0.0,
                    "breakevens": [S],
                    "net_delta": 0.0,
                    "net_theta": 0.0,
                    "net_vega": 0.0,
                    "prob_of_profit": 95.0,
                    "capital_required": round(S, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": f"Put-call parity mispricing of {mispricing:.4f}. Lock in riskless profit.",
                })
            else:
                # Put overpriced → Reversal: long call, short put, short stock
                strategies.append({
                    "name": "Reversal",
                    "type": "neutral",
                    "description": "Put-call parity arbitrage: long call + short put + short stock.",
                    "legs": [
                        {"action": "BUY",  "type": "call",  "strike": strike, "expiry": expiry, "qty": 1},
                        {"action": "SELL", "type": "put",   "strike": strike, "expiry": expiry, "qty": 1},
                        {"action": "SELL", "type": "stock",  "strike": S,     "expiry": "-",    "qty": 100},
                    ],
                    "max_profit": round(abs(mispricing), 4),
                    "max_loss": 0.0,
                    "breakevens": [S],
                    "net_delta": 0.0,
                    "net_theta": 0.0,
                    "net_vega": 0.0,
                    "prob_of_profit": 95.0,
                    "capital_required": round(S * 0.15, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": f"Put-call parity mispricing of {abs(mispricing):.4f}. Lock in riskless profit.",
                })

    return strategies
