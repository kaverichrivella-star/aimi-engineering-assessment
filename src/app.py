import streamlit as st
import pandas as pd
import time
from datetime import datetime

from providers import MockProvider
from adapters.fyers_adapter import FyersAdapter
from adapters.angel_adapter import AngelAdapter
from config import load_config
from indicators import smma, detect_crossovers
from predictor import SignalPredictor

SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFC",
    "ICICI",
    "BHARTIARTL",
    "LT",
    "SBIN",
    "HINDUNILVR",
    "KOTAKBANK",
]


@st.cache_resource
def get_provider(provider_name: str = 'Mock', cfg: dict | None = None):
    # Returns an object that matches the MockProvider interface used by the app
    cfg = cfg or {}
    provider_name = provider_name or 'Mock'

    if provider_name.lower() == 'mock':
        return MockProvider(SYMBOLS), None

    if provider_name.lower() == 'fyers':
        if not (cfg.get('access_token') or cfg.get('FYERS_ACCESS_TOKEN')):
            return MockProvider(SYMBOLS), 'Fyers access token not configured. Running mock demo instead.'
        adapter = FyersAdapter(cfg)
        return AdapterProvider(adapter, SYMBOLS), None

    if provider_name.lower() in ('angel', 'angelone', 'angel_one'):
        if not (cfg.get('angel_api_key') or cfg.get('ANGEL_API_KEY')):
            return MockProvider(SYMBOLS), 'Angel One API key not configured. Running mock demo instead.'
        adapter = AngelAdapter(cfg)
        return AdapterProvider(adapter, SYMBOLS), None

    return MockProvider(SYMBOLS), None


class AdapterProvider:
    """Wraps a broker adapter to present the same methods used by the demo app.

    Adapter must expose: get_symbols(), get_latest(symbol), get_depth(symbol), get_history(symbol, minutes)
    """
    def __init__(self, adapter, symbols=None):
        self.adapter = adapter
        self._symbols = symbols or []

    def step(self):
        # No streaming step for REST adapters; noop
        time.sleep(0)

    def get_symbols(self):
        try:
            return self.adapter.get_symbols()
        except Exception:
            return self._symbols

    def get_latest(self, symbol):
        return self.adapter.get_latest(symbol)

    def get_depth(self, symbol):
        return self.adapter.get_depth(symbol)

    def get_history(self, symbol, minutes):
        return self.adapter.get_history(symbol, minutes)


def aggregate_qty(history, minutes):
    if not history:
        return 0
    cutoff = datetime.utcnow() - pd.Timedelta(minutes=minutes)
    return sum(q for (t,p,q) in history if t >= cutoff)


def avg_price(history, minutes):
    if not history:
        return None
    cutoff = datetime.utcnow() - pd.Timedelta(minutes=minutes)
    prices = [p for (t,p,q) in history if t >= cutoff]
    return sum(prices)/len(prices) if prices else None


def main():
    st.title("AI/ML Stock Screener — Demo")
    cfg = load_config()
    provider_name = st.sidebar.selectbox("Provider", ["Mock", "Fyers", "Angel"], index=0)
    provider, provider_warning = get_provider(provider_name, cfg)
    predictor = SignalPredictor()

    if provider_warning:
        st.warning(provider_warning)

    # Sidebar controls
    st.sidebar.header("Filters & Settings")
    price_min = st.sidebar.number_input("Min LTP (₹)", value=30.0, step=1.0)
    price_max = st.sidebar.number_input("Max LTP (₹)", value=500.0, step=1.0)
    min_avg_qty = st.sidebar.number_input("Min avg qty (20m)", value=100.0, step=50.0)
    refresh_sec = st.sidebar.number_input("Refresh (s)", value=1, min_value=1, max_value=10, step=1)
    show_depth = st.sidebar.checkbox("Show Market Depth", value=True)

    if 'run_demo' not in st.session_state:
        st.session_state.run_demo = False

    if st.button("Start Live Demo", key="start_live_demo"):
        st.session_state.run_demo = True
    if st.button("Stop Live Demo", key="stop_live_demo"):
        st.session_state.run_demo = False

    placeholder = st.empty()

    if st.session_state.run_demo:
        provider.step()
        rows = []
        for s in provider.get_symbols():
            hist5 = provider.get_history(s, 5)
            hist20 = provider.get_history(s, 20)
            hist60 = provider.get_history(s, 60)
            hist120 = provider.get_history(s, 120)

            l = provider.get_latest(s)
            p = l["ltp"]

            # Price filter
            if p < price_min or p > price_max:
                continue

            # Build a series from the longest available history
            prices_for_smma = pd.Series([x[1] for x in hist120])
            prices_for_smma.index = pd.RangeIndex(len(prices_for_smma))

            sm20 = None
            sm120 = None
            if len(prices_for_smma) >= 20:
                sm_series_20 = smma(prices_for_smma, 20)
                sm20 = float(sm_series_20.dropna().iat[-1]) if not sm_series_20.dropna().empty else None
            if len(prices_for_smma) >= 120:
                sm_series_120 = smma(prices_for_smma, 120)
                sm120 = float(sm_series_120.dropna().iat[-1]) if not sm_series_120.dropna().empty else None

            avg_qty_20m = sum(x[2] for x in hist20)/len(hist20) if hist20 else 0
            if sm20 is None or sm120 is None or avg_qty_20m < min_avg_qty:
                continue

            crossover = ""
            if sm20 is not None and sm120 is not None:
                if sm20 > sm120:
                    crossover = "BUY"
                elif sm20 < sm120:
                    crossover = "SELL"

            prob = None
            explanation = ""
            if crossover:
                momentum = pd.Series([x[1] for x in hist60]).diff().fillna(0).tail(5).mean() if hist60 else 0
                vol = pd.Series([x[1] for x in hist60]).pct_change().std() if hist60 else 0
                vol_change = (sum(x[2] for x in hist20)/len(hist20)) if hist20 else 0
                prob = predictor.predict_proba([momentum, vol, vol_change])
                explanation = "Avoid: low predicted success probability" if prob < 0.5 else "Accept: predicted favorable"

            depth = provider.get_depth(s) if show_depth else {}

            row = {
                "symbol": s,
                "ltp": round(p,2),
                "smma20": round(sm20,2) if sm20 else None,
                "smma120": round(sm120,2) if sm120 else None,
                "crossover": crossover,
                "qty5m": aggregate_qty(hist5, 5),
                "qty20m": aggregate_qty(hist20, 20),
                "qty60m": aggregate_qty(hist60, 60),
                "avg20m": round(avg_price(hist20,20),2) if avg_price(hist20,20) else None,
                "avg60m": round(avg_price(hist60,60),2) if avg_price(hist60,60) else None,
                "avg_qty_20m": round(avg_qty_20m,2),
                "bid_price": depth.get('bid_price'),
                "bid_qty": depth.get('bid_qty'),
                "ask_price": depth.get('ask_price'),
                "ask_qty": depth.get('ask_qty'),
                "prob_signal": round(prob,2) if prob is not None else None,
                "explanation": explanation,
            }
            rows.append(row)

        if rows:
            df = pd.DataFrame(rows).set_index("symbol")
        else:
            df = pd.DataFrame(columns=["ltp"])
        placeholder.dataframe(df)

        try:
            csv = df.to_csv()
        except Exception:
            csv = ""

        if csv:
            st.download_button("Download CSV", csv, file_name=f"screener_snapshot_{int(time.time())}.csv", mime="text/csv", key="download_csv")
            if st.button("Save Snapshot", key="save_snapshot"):
                import os
                os.makedirs('snapshots', exist_ok=True)
                path = f"snapshots/snapshot_{int(time.time())}.csv"
                with open(path, 'w', encoding='utf8') as f:
                    f.write(csv)
                st.success(f"Saved snapshot to {path}")

        # Pause before rerunning the page so the mock demo refreshes periodically.
        time.sleep(refresh_sec)
        st.rerun()


if __name__ == '__main__':
    main()
