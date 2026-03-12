"""
GGAL market data:
- Stock price: yfinance (GGAL.BA, pesos) — always works
- Options chain: IOL REST API with session-based auth
"""
import os
import threading
import logging
import time
from typing import Optional

import requests
import urllib3
import yfinance as yf

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

TICKER_YF   = "GGAL.BA"
TICKER_IOL  = "GGAL"
MARKET      = "bCBA"
IOL_BASE    = "https://api.invertironline.com"
POLL_INTERVAL = 30

_lock        = threading.Lock()
_stop_event  = threading.Event()
_poll_thread: Optional[threading.Thread] = None

_stock_data:    dict      = {}
_options_chain: list[dict] = []

_session: Optional[requests.Session] = None


# ── Auth ────────────────────────────────────────────────────────────────────

def _iol_login(user: str, password: str) -> requests.Session:
    sess = requests.Session()
    resp = sess.post(
        f"{IOL_BASE}/token",
        data={"username": user, "password": password, "grant_type": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=False,
        timeout=15,
    )
    logger.info(f"IOL login status: {resp.status_code} | body: {resp.text[:300]}")
    resp.raise_for_status()
    token = resp.json().get("access_token")
    sess.headers.update({"Authorization": f"Bearer {token}"})
    return sess


# ── Data fetchers ────────────────────────────────────────────────────────────

def _fetch_stock() -> dict:
    t  = yf.Ticker(TICKER_YF)
    fi = t.fast_info
    return {
        "last":   float(getattr(fi, "last_price",     0) or 0),
        "bid":    0.0,
        "ask":    0.0,
        "volume": int(getattr(fi,   "last_volume",    0) or 0),
        "close":  float(getattr(fi, "previous_close", 0) or 0),
    }


def _fetch_options_iol(sess: requests.Session) -> list[dict]:
    # Try the two most likely IOL endpoint patterns
    urls = [
        f"{IOL_BASE}/api/v2/{MARKET}/Titulos/{TICKER_IOL}/Opciones",
        f"{IOL_BASE}/api/v2/cotizaciones/opciones/{MARKET}/{TICKER_IOL}",
    ]
    for url in urls:
        try:
            resp = sess.get(url, verify=False, timeout=15)
            logger.info(f"IOL options {url} → {resp.status_code} | {resp.text[:300]}")
            if resp.status_code != 200:
                continue
            raw   = resp.json()
            items = raw if isinstance(raw, list) else raw.get("opciones", raw.get("titulos", raw.get("data", [])))
            records = []
            for item in items:
                try:
                    tipo   = str(item.get("tipoOpcion") or item.get("tipo") or "").upper()
                    puntas = item.get("puntas") or []
                    records.append({
                        "symbol":        str(item.get("simbolo") or ""),
                        "strike":        float(item.get("ejercicio") or item.get("strike") or 0),
                        "expiry":        str(item.get("fechaVencimiento") or ""),
                        "type":          "call" if tipo in ("C", "CALL") else "put",
                        "bid":           float(puntas[0].get("precioCompra", 0) if puntas else 0),
                        "ask":           float(puntas[0].get("precioVenta",  0) if puntas else 0),
                        "last":          float(item.get("ultimoPrecio") or 0),
                        "volume":        int(item.get("cantidadNominal") or item.get("volumen") or 0),
                        "open_interest": int(item.get("openInterest") or 0),
                    })
                except Exception as e:
                    logger.debug(f"Skipping option item: {e}")
            if records:
                return records
        except Exception as e:
            logger.error(f"IOL options fetch error {url}: {e}")
    return []


# ── Poll loop ────────────────────────────────────────────────────────────────

def _poll_loop(user: str, password: str) -> None:
    global _stock_data, _options_chain, _session

    try:
        _session = _iol_login(user, password)
        logger.info("IOL session established.")
    except Exception as e:
        logger.error(f"IOL login failed: {e}")
        _session = None

    while not _stop_event.is_set():
        # Stock price via yfinance
        try:
            stock = _fetch_stock()
            with _lock:
                _stock_data = stock
            logger.info(f"Stock: GGAL.BA @ {stock['last']}")
        except Exception as e:
            logger.error(f"Stock fetch error: {e}")

        # Options via IOL
        if _session:
            try:
                chain = _fetch_options_iol(_session)
                with _lock:
                    _options_chain = chain
                logger.info(f"Options: {len(chain)} contracts")
            except Exception as e:
                logger.error(f"Options fetch error: {e}")

        _stop_event.wait(POLL_INTERVAL)


# ── Public interface ─────────────────────────────────────────────────────────

def connect() -> None:
    global _poll_thread
    user     = os.getenv("IOL_USER")
    password = os.getenv("IOL_PASS")
    if not user or not password:
        raise EnvironmentError("IOL_USER and IOL_PASS must be set.")
    _stop_event.clear()
    _poll_thread = threading.Thread(target=_poll_loop, args=(user, password), daemon=True)
    _poll_thread.start()
    logger.info("Polling started.")


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
