"""
IOL (Invertir Online) REST API integration.
Polls GGAL stock price and full options chain every POLL_INTERVAL seconds.
"""
import os
import threading
import logging
import time
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TICKER = "GGAL"
MARKET = "bCBA"
IOL_BASE = "https://api.invertironline.com"
POLL_INTERVAL = 5  # seconds

_lock = threading.Lock()
_stop_event = threading.Event()
_poll_thread: Optional[threading.Thread] = None

_token: Optional[str] = None
_token_expiry: float = 0.0
_refresh_token: Optional[str] = None

_stock_data: dict = {}
_options_chain: list[dict] = []


def _login(user: str, password: str) -> None:
    global _token, _token_expiry, _refresh_token
    resp = requests.post(
        f"{IOL_BASE}/token",
        data={"username": user, "password": password, "grant_type": "password"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token = data["access_token"]
    _refresh_token = data.get("refresh_token")
    expires_in = int(data.get("expires_in", 3600))
    _token_expiry = time.time() + expires_in - 60  # refresh 60s early
    logger.info("IOL login successful.")


def _refresh_auth() -> None:
    global _token, _token_expiry, _refresh_token
    try:
        resp = requests.post(
            f"{IOL_BASE}/token",
            data={"refresh_token": _refresh_token, "grant_type": "refresh_token"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token = data["access_token"]
        _refresh_token = data.get("refresh_token", _refresh_token)
        expires_in = int(data.get("expires_in", 3600))
        _token_expiry = time.time() + expires_in - 60
    except Exception as e:
        logger.warning(f"Token refresh failed, will re-login: {e}")
        _token_expiry = 0.0


def _headers() -> dict:
    if time.time() >= _token_expiry:
        _refresh_auth()
    return {"Authorization": f"Bearer {_token}"}


def _fetch_stock() -> dict:
    url = f"{IOL_BASE}/api/v2/{MARKET}/Titulos/{TICKER}/Cotizacion"
    resp = requests.get(url, headers=_headers(), timeout=10)
    resp.raise_for_status()
    d = resp.json()
    return {
        "last": float(d.get("ultimoPrecio") or d.get("last") or 0),
        "bid": float(d.get("puntas", [{}])[0].get("precioCompra", 0) if d.get("puntas") else 0),
        "ask": float(d.get("puntas", [{}])[0].get("precioVenta", 0) if d.get("puntas") else 0),
        "volume": int(d.get("volumen") or d.get("volume") or 0),
        "close": float(d.get("cierreAnterior") or 0),
    }


def _fetch_options() -> list[dict]:
    url = f"{IOL_BASE}/api/v2/{MARKET}/Titulos/{TICKER}/Opciones"
    resp = requests.get(url, headers=_headers(), timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    records = []
    items = raw if isinstance(raw, list) else raw.get("opciones", raw.get("titulos", []))
    for item in items:
        try:
            symbol = item.get("simbolo") or item.get("symbol") or ""
            tipo = str(item.get("tipoOpcion") or item.get("tipo") or "").upper()
            opt_type = "call" if tipo in ("C", "CALL") else "put"
            puntas = item.get("puntas") or []
            bid = float(puntas[0].get("precioCompra", 0)) if puntas else 0.0
            ask = float(puntas[0].get("precioVenta", 0)) if puntas else 0.0
            records.append({
                "symbol": symbol,
                "strike": float(item.get("ejercicio") or item.get("strike") or 0),
                "expiry": str(item.get("fechaVencimiento") or item.get("expiry") or ""),
                "type": opt_type,
                "bid": bid,
                "ask": ask,
                "last": float(item.get("ultimoPrecio") or item.get("last") or 0),
                "volume": int(item.get("volumen") or item.get("volume") or 0),
                "open_interest": int(item.get("openInterest") or 0),
            })
        except Exception as e:
            logger.debug(f"Skipping option item: {e}")
    return records


def _poll_loop(user: str, password: str) -> None:
    global _stock_data, _options_chain
    # Initial login
    try:
        _login(user, password)
    except Exception as e:
        logger.error(f"IOL initial login failed: {e}")
        return

    while not _stop_event.is_set():
        try:
            stock = _fetch_stock()
            with _lock:
                _stock_data = stock
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
    user = os.getenv("IOL_USER")
    password = os.getenv("IOL_PASS")
    if not user or not password:
        raise EnvironmentError("IOL_USER and IOL_PASS environment variables must be set.")

    _stop_event.clear()
    _poll_thread = threading.Thread(target=_poll_loop, args=(user, password), daemon=True)
    _poll_thread.start()
    logger.info("IOL polling thread started.")


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
    logger.info("IOL polling stopped.")
