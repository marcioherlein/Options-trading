"""
IOL (Invertir Online) real-time data via pyhomebroker.
Fetches GGAL stock price and full options chain.
"""
import os
import threading
import logging
from datetime import datetime
from typing import Optional
import pandas as pd
from pyhomebroker import HomeBroker

logger = logging.getLogger(__name__)

TICKER = "GGAL"
BROKER_ID = 12  # IOL broker ID in pyhomebroker

_hb: Optional[HomeBroker] = None
_lock = threading.Lock()

# Latest data cache
_stock_data: dict = {}
_options_chain: list[dict] = []


def _on_quotes(online, quotes):
    global _stock_data
    try:
        row = quotes[quotes["symbol"] == TICKER]
        if not row.empty:
            _stock_data = row.iloc[0].to_dict()
    except Exception as e:
        logger.error(f"Error processing stock quote: {e}")


def _on_options(online, options):
    global _options_chain
    try:
        df = options[options["symbol"].str.startswith(TICKER, na=False)].copy()
        if df.empty:
            return
        records = []
        for _, row in df.iterrows():
            records.append({
                "symbol": row.get("symbol"),
                "strike": float(row.get("strike", 0)),
                "expiry": str(row.get("expiry", "")),
                "type": "call" if row.get("option_type", "").upper() == "C" else "put",
                "bid": float(row.get("bid", 0) or 0),
                "ask": float(row.get("ask", 0) or 0),
                "last": float(row.get("last", 0) or 0),
                "volume": int(row.get("volume", 0) or 0),
                "open_interest": int(row.get("open_interest", 0) or 0),
            })
        _options_chain = records
    except Exception as e:
        logger.error(f"Error processing options chain: {e}")


def _on_error(online, error, msg):
    logger.error(f"Broker error: {error} — {msg}")


def connect():
    """Initialize and connect pyhomebroker session with IOL credentials."""
    global _hb
    dni = os.getenv("IOL_DNI")
    user = os.getenv("IOL_USER")
    password = os.getenv("IOL_PASS")
    if not dni or not user or not password:
        raise EnvironmentError("IOL_DNI, IOL_USER and IOL_PASS environment variables must be set.")

    with _lock:
        if _hb is not None:
            return
        hb = HomeBroker(BROKER_ID)
        hb.auth.login(dni=dni, user=user, password=password)
        hb.online.connect()

        hb.online.subscribe_quotes(
            symbols=[TICKER],
            on_quotes=_on_quotes,
            on_error=_on_error,
        )
        hb.online.subscribe_options(
            symbols=[TICKER],
            on_options=_on_options,
            on_error=_on_error,
        )
        _hb = hb
        logger.info("Connected to IOL via pyhomebroker.")


def get_stock_price() -> dict:
    """Returns latest GGAL stock quote dict."""
    return _stock_data.copy()


def get_options_chain() -> list[dict]:
    """Returns latest GGAL options chain as list of dicts."""
    return list(_options_chain)


def disconnect():
    global _hb
    with _lock:
        if _hb:
            try:
                _hb.online.disconnect()
            except Exception:
                pass
            _hb = None
