"""
GGAL market data:
- Stock price: yfinance (GGAL.BA, pesos)
- Options chain: BYMA open data API (free, no auth, ~20min delay)
"""
import threading
import logging
import time
from typing import Optional

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

TICKER_YF = "GGAL.BA"
TICKER_BYMA = "GGAL"
POLL_INTERVAL = 30

BYMA_OPTIONS_URL = (
    "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/bnown/seriesOpciones"
)

_lock = threading.Lock()
_stop_event = threading.Event()
_poll_thread: Optional[threading.Thread] = None

_stock_data: dict = {}
_options_chain: list[dict] = []


def _fetch_stock() -> dict:
    t = yf.Ticker(TICKER_YF)
    fi = t.fast_info
    return {
        "last": float(getattr(fi, "last_price", 0) or 0),
        "bid": 0.0,
        "ask": 0.0,
        "volume": int(getattr(fi, "last_volume", 0) or 0),
        "close": float(getattr(fi, "previous_close", 0) or 0),
    }


def _parse_byma_option(item: dict) -> Optional[dict]:
    try:
        symbol = item.get("simbolo") or item.get("symbol") or ""
        # BYMA option type: look for 'C' (call) or 'V'/'P' (put) in descripcion or tipoOpcion
        desc = str(item.get("descripcionEspecie") or item.get("descripcion") or symbol).upper()
        tipo = str(item.get("tipoOpcion") or "").upper()
        if tipo == "C" or " C " in desc or desc.endswith("C"):
            opt_type = "call"
        else:
            opt_type = "put"

        return {
            "symbol": symbol,
            "strike": float(item.get("ejercicio") or item.get("precioEjercicio") or item.get("strike") or 0),
            "expiry": str(item.get("fechaVencimiento") or item.get("vencimiento") or ""),
            "type": opt_type,
            "bid": float(item.get("precioCompra") or item.get("bid") or 0),
            "ask": float(item.get("precioVenta") or item.get("ask") or 0),
            "last": float(item.get("ultimoPrecio") or item.get("ultimo") or item.get("last") or 0),
            "volume": int(item.get("cantidadNominal") or item.get("volumen") or item.get("volume") or 0),
            "open_interest": int(item.get("openInterest") or 0),
        }
    except Exception as e:
        logger.debug(f"Could not parse option item: {e}")
        return None


def _fetch_options() -> list[dict]:
    try:
        resp = requests.post(
            BYMA_OPTIONS_URL,
            json={"subyacente": TICKER_BYMA},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
        items = raw if isinstance(raw, list) else raw.get("data", raw.get("opciones", raw.get("titulos", [])))
        records = [r for item in items if (r := _parse_byma_option(item)) is not None]
        logger.info(f"BYMA returned {len(items)} items, parsed {len(records)} options")
        return records
    except Exception as e:
        logger.error(f"BYMA options fetch error: {e}")
        return []


def _poll_loop() -> None:
    global _stock_data, _options_chain
    while not _stop_event.is_set():
        try:
            stock = _fetch_stock()
            with _lock:
                _stock_data = stock
            logger.info(f"Stock updated: GGAL.BA @ {stock['last']}")
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
    logger.info("BYMA+yfinance polling started.")


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
    logger.info("Polling stopped.")
