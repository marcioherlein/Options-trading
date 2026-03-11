"""
Volatility strategies from Natenberg:
- Long Straddle (buy vol, low IV rank)
- Short Straddle (sell vol, high IV rank)
- Long Strangle (buy vol, cheaper than straddle)
- Short Strangle (sell vol, wider breakevens)
- Call Backspread (buy vol + directional)
- Put Backspread (buy vol + directional)
"""
import math


def _find_atm_pair(chain: list[dict], S: float) -> tuple[dict | None, dict | None]:
    """Find nearest ATM call and put for a given expiry."""
    calls = sorted([o for o in chain if o["type"] == "call"], key=lambda o: abs(o["strike"] - S))
    puts  = sorted([o for o in chain if o["type"] == "put"],  key=lambda o: abs(o["strike"] - S))
    return (calls[0] if calls else None, puts[0] if puts else None)


def _find_options_by_delta(chain: list[dict], target_delta: float, opt_type: str) -> dict | None:
    """Find the option closest to a target delta for a given type."""
    candidates = [
        o for o in chain
        if o["type"] == opt_type and o.get("greeks", {}).get("delta") is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda o: abs(abs(o["greeks"]["delta"]) - target_delta))


def _dte_from_option(opt: dict) -> int:
    from datetime import datetime
    try:
        exp = datetime.strptime(str(opt["expiry"])[:10], "%Y-%m-%d")
        return max((exp - datetime.utcnow()).days, 0)
    except Exception:
        return 0


def evaluate_volatility_plays(chain: list[dict], S: float, vol_summary: dict) -> list[dict]:
    strategies = []
    iv_rank = vol_summary.get("iv_rank") or 50.0

    # Group by expiry
    expiries = sorted(set(o["expiry"] for o in chain))

    for expiry in expiries:
        exp_chain = [o for o in chain if o["expiry"] == expiry]
        call, put = _find_atm_pair(exp_chain, S)
        if not call or not put:
            continue

        call_mid = call.get("mid", 0)
        put_mid  = put.get("mid", 0)
        strike   = call["strike"]
        dte      = _dte_from_option(call)
        if dte == 0:
            continue

        # --- Long Straddle ---
        cost = call_mid + put_mid
        if cost > 0:
            strategies.append({
                "name": "Long Straddle",
                "type": "buy_vol",
                "description": "Buy ATM call + put. Profit from large move in either direction.",
                "legs": [
                    {"action": "BUY", "type": "call", "strike": strike, "expiry": expiry, "qty": 1},
                    {"action": "BUY", "type": "put",  "strike": strike, "expiry": expiry, "qty": 1},
                ],
                "max_profit": None,  # Unlimited
                "max_loss": round(cost, 4),
                "breakevens": [round(strike - cost, 2), round(strike + cost, 2)],
                "net_delta": round((call.get("greeks", {}).get("delta", 0.5) +
                                    put.get("greeks", {}).get("delta", -0.5)), 4),
                "net_theta": round((call.get("greeks", {}).get("theta", 0) +
                                    put.get("greeks", {}).get("theta", 0)), 6),
                "net_vega":  round((call.get("greeks", {}).get("vega", 0) +
                                    put.get("greeks", {}).get("vega", 0)), 6),
                "prob_of_profit": 45.0,
                "capital_required": round(cost, 4),
                "dte": dte,
                "expiry": expiry,
                "natenberg_note": "Use when IV < HV (options underpriced). Profits from realized vol > IV.",
            })

        # --- Short Straddle ---
        if call_mid > 0 and put_mid > 0:
            credit = call_mid + put_mid
            strategies.append({
                "name": "Short Straddle",
                "type": "sell_vol",
                "description": "Sell ATM call + put. Collect premium; profit if stock stays near strike.",
                "legs": [
                    {"action": "SELL", "type": "call", "strike": strike, "expiry": expiry, "qty": 1},
                    {"action": "SELL", "type": "put",  "strike": strike, "expiry": expiry, "qty": 1},
                ],
                "max_profit": round(credit, 4),
                "max_loss": None,  # Unlimited
                "breakevens": [round(strike - credit, 2), round(strike + credit, 2)],
                "net_delta": 0.0,
                "net_theta": round(-(call.get("greeks", {}).get("theta", 0) +
                                     put.get("greeks", {}).get("theta", 0)), 6),
                "net_vega":  round(-(call.get("greeks", {}).get("vega", 0) +
                                     put.get("greeks", {}).get("vega", 0)), 6),
                "prob_of_profit": 68.0,
                "capital_required": round(strike * 0.20, 4),  # Approx margin
                "dte": dte,
                "expiry": expiry,
                "natenberg_note": "Use when IV > HV (options overpriced). Time decay works in your favor.",
            })

        # --- Long Strangle (10-delta options) ---
        otm_call = _find_options_by_delta(exp_chain, 0.20, "call")
        otm_put  = _find_options_by_delta(exp_chain, 0.20, "put")
        if otm_call and otm_put:
            strangle_cost = otm_call.get("mid", 0) + otm_put.get("mid", 0)
            if strangle_cost > 0:
                strategies.append({
                    "name": "Long Strangle",
                    "type": "buy_vol",
                    "description": "Buy OTM call + put. Cheaper than straddle; needs larger move.",
                    "legs": [
                        {"action": "BUY", "type": "call", "strike": otm_call["strike"], "expiry": expiry, "qty": 1},
                        {"action": "BUY", "type": "put",  "strike": otm_put["strike"],  "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": None,
                    "max_loss": round(strangle_cost, 4),
                    "breakevens": [
                        round(otm_put["strike"] - strangle_cost, 2),
                        round(otm_call["strike"] + strangle_cost, 2),
                    ],
                    "net_delta": round((otm_call.get("greeks", {}).get("delta", 0.2) +
                                        otm_put.get("greeks", {}).get("delta", -0.2)), 4),
                    "net_theta": round((otm_call.get("greeks", {}).get("theta", 0) +
                                        otm_put.get("greeks", {}).get("theta", 0)), 6),
                    "net_vega":  round((otm_call.get("greeks", {}).get("vega", 0) +
                                        otm_put.get("greeks", {}).get("vega", 0)), 6),
                    "prob_of_profit": 35.0,
                    "capital_required": round(strangle_cost, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "Cheaper volatility play than straddle. Lower cost, wider breakevens.",
                })

        # --- Short Strangle ---
        if otm_call and otm_put:
            strangle_credit = otm_call.get("mid", 0) + otm_put.get("mid", 0)
            if strangle_credit > 0:
                strategies.append({
                    "name": "Short Strangle",
                    "type": "sell_vol",
                    "description": "Sell OTM call + put. Higher PoP than short straddle, less premium.",
                    "legs": [
                        {"action": "SELL", "type": "call", "strike": otm_call["strike"], "expiry": expiry, "qty": 1},
                        {"action": "SELL", "type": "put",  "strike": otm_put["strike"],  "expiry": expiry, "qty": 1},
                    ],
                    "max_profit": round(strangle_credit, 4),
                    "max_loss": None,
                    "breakevens": [
                        round(otm_put["strike"] - strangle_credit, 2),
                        round(otm_call["strike"] + strangle_credit, 2),
                    ],
                    "net_delta": 0.0,
                    "net_theta": round(-(otm_call.get("greeks", {}).get("theta", 0) +
                                         otm_put.get("greeks", {}).get("theta", 0)), 6),
                    "net_vega": round(-(otm_call.get("greeks", {}).get("vega", 0) +
                                        otm_put.get("greeks", {}).get("vega", 0)), 6),
                    "prob_of_profit": 75.0,
                    "capital_required": round(otm_call["strike"] * 0.15, 4),
                    "dte": dte,
                    "expiry": expiry,
                    "natenberg_note": "High-probability sell-vol trade. Wide range of profitability.",
                })

    return strategies
