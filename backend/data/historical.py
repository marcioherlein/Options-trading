"""
Historical data layer:
- GGAL.BA OHLCV from yfinance (up to 2 years)
- HV calculation (20/30/60-day)
- IV snapshot store in SQLite for IV Rank and trend charts
"""
import logging
from datetime import datetime, timedelta, date
import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine, Column, Float, String, DateTime
from sqlalchemy.orm import declarative_base, Session

logger = logging.getLogger(__name__)

DB_PATH = "iv_snapshots.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()


class IVSnapshot(Base):
    __tablename__ = "iv_snapshots"
    id = Column(String, primary_key=True)  # f"{symbol}_{timestamp_iso}"
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    iv = Column(Float)


Base.metadata.create_all(engine)

# In-memory cache for historical prices
_price_history: pd.DataFrame = pd.DataFrame()
_last_fetch: datetime = datetime.min


def _refresh_price_history():
    global _price_history, _last_fetch
    # Re-fetch at most once per hour
    if (datetime.utcnow() - _last_fetch).seconds < 3600 and not _price_history.empty:
        return
    try:
        df = yf.download("GGAL.BA", period="2y", auto_adjust=True, progress=False)
        if df.empty:
            logger.warning("yfinance returned empty data for GGAL.BA")
            return
        _price_history = df[["Close"]].dropna()
        _last_fetch = datetime.utcnow()
        logger.info(f"Fetched {len(_price_history)} days of GGAL.BA history.")
    except Exception as e:
        logger.error(f"Error fetching price history: {e}")


def get_hv(window: int = 30) -> float:
    """
    Annualized historical volatility using close-to-close log returns.
    window: number of trading days (20, 30, or 60)
    """
    _refresh_price_history()
    if _price_history.empty or len(_price_history) < window + 1:
        return 0.0
    closes = _price_history["Close"].values
    log_returns = np.log(closes[1:] / closes[:-1])
    hv = float(np.std(log_returns[-window:]) * np.sqrt(252))
    return round(hv, 4)


def get_all_hv() -> dict:
    """Returns HV for 20, 30, and 60-day windows."""
    return {
        "hv_20": get_hv(20),
        "hv_30": get_hv(30),
        "hv_60": get_hv(60),
    }


def get_price_history_for_chart(days: int = 365) -> list[dict]:
    """Returns OHLCV history as list of dicts for the frontend chart."""
    _refresh_price_history()
    if _price_history.empty:
        return []
    df = _price_history.tail(days).reset_index()
    df.columns = [c.lower() for c in df.columns]
    df["date"] = df["date"].astype(str)
    return df.to_dict(orient="records")


def save_iv_snapshot(symbol: str, iv: float, timestamp: datetime = None):
    """Persist an IV data point for a given option symbol."""
    ts = timestamp or datetime.utcnow()
    snapshot_id = f"{symbol}_{ts.isoformat()}"
    with Session(engine) as session:
        snap = IVSnapshot(id=snapshot_id, symbol=symbol, timestamp=ts, iv=iv)
        session.merge(snap)
        session.commit()


def get_iv_history(symbol: str, days: int = 365) -> list[dict]:
    """Returns stored IV snapshots for a specific option symbol."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    with Session(engine) as session:
        rows = (
            session.query(IVSnapshot)
            .filter(IVSnapshot.symbol == symbol, IVSnapshot.timestamp >= cutoff)
            .order_by(IVSnapshot.timestamp)
            .all()
        )
        return [{"timestamp": r.timestamp.isoformat(), "iv": r.iv} for r in rows]


def get_iv_rank(symbol: str) -> dict:
    """
    IV Rank and IV Percentile for a given option symbol,
    computed from the last 52 weeks of stored IV snapshots.
    """
    history = get_iv_history(symbol, days=365)
    if len(history) < 2:
        return {"iv_rank": None, "iv_percentile": None}

    ivs = [h["iv"] for h in history]
    current_iv = ivs[-1]
    iv_low = min(ivs)
    iv_high = max(ivs)

    iv_rank = round((current_iv - iv_low) / (iv_high - iv_low) * 100, 1) if iv_high != iv_low else 50.0
    iv_percentile = round(sum(1 for v in ivs if v < current_iv) / len(ivs) * 100, 1)

    return {
        "iv_rank": iv_rank,
        "iv_percentile": iv_percentile,
        "iv_current": round(current_iv, 4),
        "iv_52w_low": round(iv_low, 4),
        "iv_52w_high": round(iv_high, 4),
    }
