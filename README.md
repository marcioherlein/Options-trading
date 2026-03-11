# GGAL Options Trading Dashboard

Real-time options strategy dashboard for **GGAL (Grupo Financiero Galicia)** on BYMA, powered by Natenberg's *Option Volatility & Pricing* framework.

## Architecture

```
backend/   → Python FastAPI (Railway)
frontend/  → Next.js (Vercel)
```

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # Fill in IOL_USER, IOL_PASS
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local   # Set NEXT_PUBLIC_BACKEND_URL
npm run dev
```

## Deployment

### Backend → Railway
1. Connect GitHub repo in Railway
2. Set root directory to `backend/`
3. Set env vars: `IOL_USER`, `IOL_PASS`, `RISK_FREE_RATE`
4. Railway auto-detects `railway.toml`

### Frontend → Vercel
1. Import GitHub repo in Vercel
2. Set root directory to `frontend/`
3. Set env var: `NEXT_PUBLIC_BACKEND_URL` → your Railway URL
4. Deploy

## Strategy Model (Natenberg Framework)

| Vol Regime | Signal | Preferred Strategies |
|---|---|---|
| IV > HV | Overpriced | Short straddle, iron condor, credit spreads, covered calls |
| IV < HV | Underpriced | Long straddle, strangle, backspreads, debit spreads |
| IV ≈ HV | Fair | Directional spreads, income strategies |

## Data Sources
- **Real-time**: IOL (Invertir Online) via pyhomebroker
- **Historical**: GGAL.BA via yfinance (2 years)
- **IV History**: SQLite snapshots (builds over time for IV Rank)
