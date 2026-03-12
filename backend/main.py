"""
FastAPI application.
Provides:
  GET /health         — health check
  GET /stream         — Server-Sent Events: live options data + strategy rankings
  GET /history        — Historical price + IV vs HV chart data
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from data import broker
from data.historical import get_price_history_for_chart, get_all_hv
from pricing.blackscholes import enrich_option
from pricing.volatility import build_volatility_surface, persist_iv_snapshots, get_volatility_summary
from strategies.engine import run_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.40"))
STREAM_INTERVAL = 5  # seconds between SSE pushes


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to IOL broker...")
    try:
        broker.connect()
        logger.info("Broker connected.")
    except Exception as e:
        logger.error(f"Broker connection failed: {e}")
    yield
    broker.disconnect()


app = FastAPI(title="GGAL Options Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def build_payload() -> dict:
    """Pull latest data, run pricing + strategy engine, return full payload."""
    stock = broker.get_stock_price()
    S = float(stock.get("last", 0) or stock.get("close", 0) or 0)

    raw_chain = broker.get_options_chain()

    # Enrich each option with IV and Greeks
    enriched = []
    for opt in raw_chain:
        try:
            enriched.append(enrich_option(opt, S, RISK_FREE_RATE))
        except Exception as e:
            logger.debug(f"Could not enrich {opt.get('symbol')}: {e}")

    # Persist IV snapshots for IV rank tracking
    if enriched:
        persist_iv_snapshots(enriched)

    # Volatility summary
    vol_summary = get_volatility_summary(enriched, S) if S > 0 else {}

    # Volatility surface for smile chart
    surface = build_volatility_surface(enriched)

    # Strategy rankings
    strategies = run_engine(enriched, S, vol_summary) if S > 0 else []

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "stock": {
            "symbol": "GGAL",
            "price": round(S, 2),
            "bid": float(stock.get("bid", 0) or 0),
            "ask": float(stock.get("ask", 0) or 0),
            "volume": int(stock.get("volume", 0) or 0),
        },
        "chain": enriched,
        "vol_surface": surface,
        "vol_summary": vol_summary,
        "strategies": strategies,
    }


async def event_generator(request):
    while True:
        if await request.is_disconnected():
            break
        try:
            payload = build_payload()
            yield {"data": json.dumps(payload)}
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"data": json.dumps({"error": str(e), "timestamp": datetime.utcnow().isoformat()})}
        await asyncio.sleep(STREAM_INTERVAL)


@app.get("/stream")
async def stream(request: Request):
    return EventSourceResponse(event_generator(request))


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/history")
def history(days: int = 365):
    """Returns GGAL.BA historical price data for charts."""
    return {
        "prices": get_price_history_for_chart(days),
        "hv": get_all_hv(),
    }
