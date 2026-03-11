"""
Volatility analytics:
- IV surface (strike x expiry matrix)
- IV vs HV time-series for dashboard chart
- Per-option IV snapshot persistence
"""
import logging
from collections import defaultdict
from data.historical import save_iv_snapshot, get_all_hv, get_iv_rank

logger = logging.getLogger(__name__)


def build_volatility_surface(enriched_chain: list[dict]) -> list[dict]:
    """
    Builds the volatility smile / surface from enriched options chain.
    Returns list of {expiry, strike, call_iv, put_iv} for chart.
    """
    surface: dict[str, dict[float, dict]] = defaultdict(dict)
    for opt in enriched_chain:
        expiry = opt.get("expiry", "")
        strike = opt.get("strike", 0)
        iv = opt.get("iv", 0)
        if iv <= 0:
            continue
        entry = surface[expiry].setdefault(strike, {"strike": strike, "expiry": expiry})
        if opt["type"] == "call":
            entry["call_iv"] = round(iv * 100, 2)
        else:
            entry["put_iv"] = round(iv * 100, 2)

    result = []
    for expiry, strikes in sorted(surface.items()):
        for strike, data in sorted(strikes.items()):
            result.append(data)
    return result


def persist_iv_snapshots(enriched_chain: list[dict]):
    """Save current IV for each option to SQLite for IV Rank tracking."""
    for opt in enriched_chain:
        iv = opt.get("iv", 0)
        symbol = opt.get("symbol", "")
        if iv > 0 and symbol:
            try:
                save_iv_snapshot(symbol, iv)
            except Exception as e:
                logger.debug(f"Could not save IV snapshot for {symbol}: {e}")


def get_atm_iv(enriched_chain: list[dict], S: float) -> float:
    """Returns the average IV of the nearest ATM call and put (30-day expiry preferred)."""
    if not enriched_chain or S <= 0:
        return 0.0
    # Sort by distance to current price
    candidates = [o for o in enriched_chain if o.get("iv", 0) > 0]
    if not candidates:
        return 0.0
    candidates.sort(key=lambda o: abs(o["strike"] - S))
    atm = candidates[:4]
    return round(sum(o["iv"] for o in atm) / len(atm), 4)


def get_volatility_summary(enriched_chain: list[dict], S: float) -> dict:
    """
    Master volatility summary for the dashboard:
    - HV (20/30/60-day)
    - ATM IV
    - IV vs HV ratio (core Natenberg signal)
    - IV Rank/Percentile for ATM option symbol
    """
    hv = get_all_hv()
    atm_iv = get_atm_iv(enriched_chain, S)

    # Find the closest ATM option symbol for IV rank lookup
    atm_symbol = ""
    if enriched_chain and S > 0:
        candidates = sorted(enriched_chain, key=lambda o: abs(o["strike"] - S))
        if candidates:
            atm_symbol = candidates[0].get("symbol", "")

    iv_rank_data = get_iv_rank(atm_symbol) if atm_symbol else {}

    hv_30 = hv.get("hv_30", 0)
    iv_vs_hv = round(atm_iv / hv_30, 3) if hv_30 > 0 and atm_iv > 0 else None

    return {
        **hv,
        "atm_iv": atm_iv,
        "iv_vs_hv_ratio": iv_vs_hv,
        "vol_regime": (
            "overpriced" if iv_vs_hv and iv_vs_hv > 1.1 else
            "underpriced" if iv_vs_hv and iv_vs_hv < 0.9 else
            "fair"
        ),
        **iv_rank_data,
    }
