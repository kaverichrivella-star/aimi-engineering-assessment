# AI/ML Stock Screener (Streamlit)

A live-capable stock screening dashboard built for the Assignment 1 assessment.
It combines market data adapters, liquidity filters, ETQ/LTP analytics, AI signal scoring,
trade lifecycle tracking, and a retrainable ML predictor.

## Features

- Live provider selection: `Yahoo`, `Fyers`, `Angel`, `Mock`
- Broker wrapper support for Fyers and Angel One with Yahoo fallback
- Liquidity filters: bid/ask quantity, ETQ over 5/20/60 minutes
- Short-term average price: 20-minute and 60-minute average LTP
- SMMA-based signal generation with BUY/SELL crossover logic
- AI confidence score and explanation text per signal
- Trade manager for open positions, realized/unrealized P&L, and trade history
- Historical model training from real market data via `yfinance`
- One-click `.exe` build support using `pyinstaller`

## Setup

```powershell
cd /workspace/stock_screener
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the app

```powershell
streamlit run src/app.py
```

## Data providers

- `Yahoo`: live price and historic bars from Yahoo Finance
- `Fyers`: live broker integration via `src/adapters/fyers_adapter.py`
- `Angel`: live broker integration via `src/adapters/angel_adapter.py`
- `Mock`: synthetic local market data for development

The app will use the selected provider and fall back to Yahoo data when broker credentials or endpoints are unavailable.

## Configuration

Create a `.env` file from `.env.example` and fill values for the providers you want to use.

Required keys for Fyers:

- `FYERS_API_KEY`
- `FYERS_ACCESS_TOKEN`
- `FYERS_INSTRUMENT_MAP_ENDPOINT` (optional, recommended)

Required keys for Angel One:

- `ANGEL_API_KEY`
- `ANGEL_CLIENT_ID`
- `ANGEL_INSTRUMENT_MAP_ENDPOINT` (optional)

The app reads environment variables through `src/config.py` using `python-dotenv`.

## Using live broker adapters

1. Copy `.env.example` to `.env`.
2. Fill broker credentials and instrument map endpoints.
3. Start the app and choose `Fyers` or `Angel` in the sidebar.
4. Verify the provider returns symbol, quote, depth, and history data.

If the adapter cannot retrieve live data, the app falls back to Yahoo Finance for pricing and history.

## Filters and dashboard

Use the sidebar to tune:

- minimum and maximum LTP
- minimum bid and ask liquidity
- minimum ETQ thresholds for 5m, 20m, and 60m
- market-depth display
- AI reasoning visibility
- refresh interval

The app displays:

- screened symbols and signal decisions
- trade summary metrics
- open positions with unrealized P/L
- realized trade history
- downloadable results snapshot

## Train the ML predictor

Save a trained model with:

```powershell
python src/train_predictor.py
```

This downloads live historical data, computes ETQ/LTQ, momentum and SMMA features,
trains a `RandomForestClassifier`, and saves `models/model.joblib`.

The app can also retrain the model from the sidebar.

## Tests

Run:

```powershell
python -m pytest -q
```

## Build executable

Create a Windows `.exe` with:

```powershell
.\build_exe.ps1
```

## Demo recording

Use a screen recorder such as `ffmpeg`:

```powershell
ffmpeg -f gdigrab -framerate 15 -offset_x 0 -offset_y 0 -video_size 1920x1080 -i desktop -codec:v libx264 -preset ultrafast demo.mp4
```

> Keep API keys and `.env` contents private when recording or sharing demo videos.
