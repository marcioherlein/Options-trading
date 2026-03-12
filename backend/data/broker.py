"""
GGAL market data via yfinance.
Polls stock price and options chain every POLL_INTERVAL seconds.
GGAL trades on NASDAQ — yfinance provides full options chain with Greeks.
"""
import threading
import logging
import time
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

TICKER = "GGAL.BA"
POLL_INTERVAL = 30  # yfinance rate limits — poll every 30s

_lock = threading.Lock()
_stop_event = threading.Event()
_poll_thread: Optional[threading.Thread] = None

_stock_data: dict = {}
_options_chain: list[dict] = []


def _fetch_stock() -> dict:
    t = yf.Ticker(TICKER)
    fi = t.fast_info
    return {
        "last": float(getattr(fi, "last_price", 0) or 0),
        "bid": float(getattr(fi, "bid", 0) or 0),
        "ask": float(getattr(fi, "ask", 0) or 0),
        "volume": int(getattr(fi, "last_volume", 0) or 0),
        "close": float(getattr(fi, "previous_close", 0) or 0),
    }


def _fetch_options() -> list[dict]:
    t = yf.Ticker(TICKER)
    records = []
    try:
        expirations = t.options
    except Exception:
        return records

    for expiry in expirations[:4]:  # limit to next 4 expiries
        try:
            chain = t.option_chain(expiry)
            for df, opt_type in [(chain.calls, "call"), (chain.puts, "put")]:
                for _, row in df.iterrows():
                    records.append({
                        "symbol": str(row.get("contractSymbol", "")),
                        "strike": float(row.get("strike", 0)),
                        "expiry": expiry,
                        "type": opt_type,
                        "bid": float(row.get("bid", 0) or 0),
                        "ask": float(row.get("ask", 0) or 0),
                        "last": float(row.get("lastPrice", 0) or 0),
                        "volume": int(row.get("volume", 0) or 0),
                        "open_interest": int(row.get("openInterest", 0) or 0),
                    })
        except Exception as e:
            logger.debug(f"Skipping expiry {expiry}: {e}")

    return records


def _poll_loop() -> None:
    global _stock_data, _options_chain
    while not _stop_event.is_set():
        try:
            stock = _fetch_stock()
            with _lock:
                _stock_data = stock
            logger.info(f"Stock updated: GGAL @ {stock['last']}")
        except Exception as e:
            logger.error(f"Stock fetch error: {e}")

        try:
            chain = _fetch_options()
            with _lock:
                _options_chain = chain
            logger.info(f"Options chain updated: {len(chain)} contracts")
        except Exception as e:
            logger.error(f"Options fetch error: {e}")

        _stop_event.wait(POLL_INTERVAL)


def connect() -> None:
    global _poll_thread
    _stop_event.clear()
    _poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    _poll_thread.start()
    logger.info("yfinance polling started.")


def get_stock_price() -> dict:
    with _lock:
        return dict(_stock_data)


def get_options_chain() -> list[dict]:
    with _lock:
        return list(_options_chain)


def disconnect() -> None:
    _stop_event.set()
    if _poll_thread:
        _poll_thread.join(timeout=5)
    logger.info("yfinance polling stopped.")
