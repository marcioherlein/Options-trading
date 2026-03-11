"""
Black-Scholes pricing, Greeks, and implied volatility via py_vollib.
All calculations follow Natenberg's framework:
  - European-style options (GGAL options on BYMA are European)
  - flag: 'c' for call, 'p' for put
"""
import logging
import numpy as np
from py_vollib.black_scholes import black_scholes as bs_price
from py_vollib.black_scholes.implied_volatility import implied_volatility as bs_iv
from py_vollib.black_scholes.greeks.analytical import (
    delta, gamma, theta, vega, rho
)

logger = logging.getLogger(__name__)

TRADING_DAYS = 252


def _safe(fn, *args, default=None):
    try:
        result = fn(*args)
        return result if np.isfinite(result) else default
    except Exception:
        return default


def calc_price(flag: str, S: float, K: float, t: float, r: float, sigma: float) -> float:
    """Theoretical option price via Black-Scholes."""
    if t <= 0 or sigma <= 0:
        return max(0.0, (S - K) if flag == "c" else (K - S))
    return _safe(bs_price, flag, S, K, t, r, sigma, default=0.0)


def calc_iv(market_price: float, S: float, K: float, t: float, r: float, flag: str) -> float:
    """
    Implied Volatility via Newton-Raphson on Black-Scholes.
    Returns annualized IV or 0.0 if not computable.
    """
    if t <= 0 or market_price <= 0 or S <= 0 or K <= 0:
        return 0.0
    intrinsic = max(0.0, (S - K) if flag == "c" else (K - S))
    if market_price <= intrinsic:
        return 0.0
    return _safe(bs_iv, market_price, S, K, t, r, flag, default=0.0)


def calc_greeks(flag: str, S: float, K: float, t: float, r: float, sigma: float) -> dict:
    """Returns all first-order Greeks (and gamma/vega)."""
    if t <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    return {
        "delta": _safe(delta, flag, S, K, t, r, sigma, default=0.0),
        "gamma": _safe(gamma, flag, S, K, t, r, sigma, default=0.0),
        "theta": _safe(theta, flag, S, K, t, r, sigma, default=0.0),
        "vega":  _safe(vega,  flag, S, K, t, r, sigma, default=0.0),
        "rho":   _safe(rho,   flag, S, K, t, r, sigma, default=0.0),
    }


def enrich_option(option: dict, S: float, r: float) -> dict:
    """
    Takes a raw option dict from broker.py and adds:
    iv, theoretical_value, greeks, time_to_expiry_years, is_itm
    """
    from datetime import datetime
    flag = "c" if option["type"] == "call" else "p"
    K = option["strike"]
    # Parse expiry date string (expected format: YYYY-MM-DD or similar)
    try:
        expiry_dt = datetime.strptime(str(option["expiry"])[:10], "%Y-%m-%d")
        t = max((expiry_dt - datetime.utcnow()).days / TRADING_DAYS, 0.0)
    except Exception:
        t = 0.0

    # Use mid-price; fall back to last
    mid = (option["bid"] + option["ask"]) / 2 if option["bid"] and option["ask"] else option["last"]
    iv = calc_iv(mid, S, K, t, r, flag)
    theoretical = calc_price(flag, S, K, t, r, iv) if iv > 0 else 0.0
    greeks = calc_greeks(flag, S, K, t, r, iv) if iv > 0 else {}
    is_itm = (S > K) if flag == "c" else (S < K)

    return {
        **option,
        "mid": round(mid, 4),
        "iv": round(iv, 4),
        "theoretical_value": round(theoretical, 4),
        "time_to_expiry": round(t, 4),
        "is_itm": is_itm,
        "greeks": {k: round(v, 6) for k, v in greeks.items()},
    }
