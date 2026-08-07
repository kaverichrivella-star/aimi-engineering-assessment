import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pathlib import Path

from providers import MockProvider, YFinanceProvider, FyersProvider, AngelProvider
from config import load_config
from indicators import smma, detect_crossovers
from predictor import SignalPredictor

ROOT = Path(__file__).resolve().parents[1]
SYMBOL_FILE = ROOT / 'symbols.csv'


@st.cache_data
def load_symbols(filepath: Path = SYMBOL_FILE):
    try:
        symbols = (
            pd.read_csv(filepath, header=None, squeeze=True)
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .drop_duplicates()
            .tolist()
        )
        return [s for s in symbols if s]
    except Exception:
        return ["RELIANCE", "TCS", "INFY"]


@st.cache_resource
def get_provider(provider_name: str = 'Fyers', cfg: dict | None = None, symbols=None):
    cfg = cfg or {}
    symbols = symbols or load_symbols()
    provider_name = provider_name or 'Fyers'

    if provider_name.lower() == 'mock':
        return MockProvider(symbols), 'Mock provider active.'

    if provider_name.lower() == 'yahoo':
        return YFinanceProvider(symbols), None

    if provider_name.lower() == 'fyers':
        provider = FyersProvider(cfg, symbols)
        if not provider.use_live:
            return provider, 'FYERS credentials not configured. Using Yahoo fallback data instead.'
        return provider, None

    if provider_name.lower() in ('angel', 'angelone', 'angel_one'):
        provider = AngelProvider(cfg, symbols)
        if not provider.use_live:
            return provider, 'Angel One credentials not configured. Using Yahoo fallback data instead.'
        return provider, None

    return MockProvider(symbols), 'Unknown provider selected; using mock data.'


class TradeManager:
    def __init__(self):
        self.open_positions = {}
        self.trade_history = []

    def update(self, symbol, signal, decision, price, timestamp):
        pos = self.open_positions.get(symbol)
        if signal not in ('BUY', 'SELL') or decision != 'Accept':
            return

        if pos is None:
            self.open_positions[symbol] = {
                'symbol': symbol,
                'side': signal,
                'entry_price': price,
                'entry_time': timestamp,
            }
            return

        if pos['side'] != signal:
            self.close(symbol, price, timestamp)
            self.open_positions[symbol] = {
                'symbol': symbol,
                'side': signal,
                'entry_price': price,
                'entry_time': timestamp,
            }

    def close(self, symbol, exit_price, exit_time):
        pos = self.open_positions.pop(symbol, None)
        if not pos:
            return
        pl = exit_price - pos['entry_price'] if pos['side'] == 'BUY' else pos['entry_price'] - exit_price
        self.trade_history.append({
            'symbol': symbol,
            'side': pos['side'],
            'entry_price': round(pos['entry_price'], 2),
            'entry_time': pos['entry_time'].isoformat(),
            'exit_price': round(exit_price, 2),
            'exit_time': exit_time.isoformat(),
            'pnl': round(pl, 2),
            'duration_minutes': int((exit_time - pos['entry_time']).total_seconds() / 60),
        })

    def realized_pnl(self):
        return round(sum(t['pnl'] for t in self.trade_history), 2)

    def open_positions_list(self, latest_prices=None):
        latest_prices = latest_prices or {}
        rows = []
        for p in self.open_positions.values():
            current_price = latest_prices.get(p['symbol'])
            unrealized = None
            if current_price is not None:
                unrealized = current_price - p['entry_price'] if p['side'] == 'BUY' else p['entry_price'] - current_price
            rows.append({
                'symbol': p['symbol'],
                'side': p['side'],
                'entry_price': round(p['entry_price'], 2),
                'entry_time': p['entry_time'].isoformat() if hasattr(p['entry_time'], 'isoformat') else p['entry_time'],
                'current_price': round(current_price, 2) if current_price is not None else None,
                'unrealized_pnl': round(unrealized, 2) if unrealized is not None else None,
            })
        return rows

    def unrealized_pnl(self, latest_prices=None):
        latest_prices = latest_prices or {}
        total = 0.0
        for p in self.open_positions.values():
            current_price = latest_prices.get(p['symbol'])
            if current_price is None:
                continue
            total += current_price - p['entry_price'] if p['side'] == 'BUY' else p['entry_price'] - current_price
        return round(total, 2)


def aggregate_qty(history, minutes):
    if not history:
        return 0
    cutoff = datetime.utcnow() - pd.Timedelta(minutes=minutes)
    return sum(q for (t, p, q) in history if t >= cutoff)


def average_ltq(history, minutes):
    if not history:
        return 0
    cutoff = datetime.utcnow() - pd.Timedelta(minutes=minutes)
    qtys = [q for (t, p, q) in history if t >= cutoff]
    return sum(qtys) / len(qtys) if qtys else 0


def avg_price(history, minutes):
    if not history:
        return 0
    cutoff = datetime.utcnow() - pd.Timedelta(minutes=minutes)
    prices = [p for (t, p, q) in history if t >= cutoff]
    return sum(prices) / len(prices) if prices else 0


def build_feature_vector(hist5, hist20, hist60, hist120, depth):
    ltq_2m = average_ltq(hist5, 2)
    ltq_5m = average_ltq(hist5, 5)
    etq_5m = aggregate_qty(hist5, 5)
    etq_20m = aggregate_qty(hist20, 20)
    etq_60m = aggregate_qty(hist60, 60)
    bid_qty = depth.get('bid_qty', 0)
    ask_qty = depth.get('ask_qty', 0)
    imbalance = (bid_qty - ask_qty) / (bid_qty + ask_qty) if bid_qty + ask_qty else 0
    spread = (depth.get('ask_price', 0) - depth.get('bid_price', 0)) if depth else 0
    prices_5m = [x[1] for x in hist5]
    momentum_5m = (prices_5m[-1] - prices_5m[0]) / (prices_5m[0] + 1e-9) if len(prices_5m) >= 2 else 0
    prices_20m = [x[1] for x in hist20]
    volatility_20m = pd.Series(prices_20m).pct_change().std() if prices_20m else 0
    smma_distance = 0
    if len(hist120) >= 120:
        prices_120 = pd.Series([x[1] for x in hist120])
        sm20 = smma(prices_120, 20).dropna().iat[-1]
        sm120 = smma(prices_120, 120).dropna().iat[-1]
        smma_distance = float(sm20 - sm120)

    return [
        ltq_2m,
        ltq_5m,
        etq_5m,
        etq_20m,
        etq_60m,
        imbalance,
        spread,
        momentum_5m,
        float(volatility_20m) if volatility_20m == volatility_20m else 0,
        smma_distance,
    ]


def decision_from_signal(signal, prob):
    if signal == 'BUY':
        return 'Accept' if prob >= 0.6 else 'Reject'
    if signal == 'SELL':
        return 'Accept' if prob <= 0.4 else 'Reject'
    return 'Hold'


def main():
    st.title("AI/ML Stock Screener — Demo")
    cfg = load_config()
    symbols = load_symbols()
    provider_name = st.sidebar.selectbox("Provider", ["Yahoo", "Fyers", "Angel", "Mock"], index=1)
    provider, provider_warning = get_provider(provider_name, cfg, symbols)
    predictor = SignalPredictor()

    if provider_warning:
        st.warning(provider_warning)

    # Sidebar controls
    st.sidebar.header("Filters & Settings")
    price_min = st.sidebar.number_input("Min LTP (₹)", value=30.0, step=1.0)
    price_max = st.sidebar.number_input("Max LTP (₹)", value=500.0, step=1.0)
    min_bid_qty = st.sidebar.number_input("Min Bid Qty", value=1000000, step=100000)
    min_ask_qty = st.sidebar.number_input("Min Ask Qty", value=1000000, step=100000)
    min_etq_5m = st.sidebar.number_input("Min ETQ (5m)", value=1000000, step=100000)
    min_etq_20m = st.sidebar.number_input("Min ETQ (20m)", value=2000000, step=100000)
    min_etq_60m = st.sidebar.number_input("Min ETQ (60m)", value=5000000, step=100000)
    refresh_sec = st.sidebar.number_input("Refresh (s)", value=5, min_value=1, max_value=30, step=1)
    show_depth = st.sidebar.checkbox("Show Market Depth", value=True)
    show_explanation = st.sidebar.checkbox("Show reasoning", value=True)
    retrain_model = st.sidebar.button("Retrain model from historical data")

    if 'run_demo' not in st.session_state:
        st.session_state.run_demo = False
    if 'trade_manager' not in st.session_state:
        st.session_state.trade_manager = TradeManager()

    if st.button("Start Live Demo", key="start_live_demo"):
        st.session_state.run_demo = True
    if st.button("Stop Live Demo", key="stop_live_demo"):
        st.session_state.run_demo = False
    if retrain_model:
        with st.spinner("Retraining model on historical data..."):
            predictor.fit_on_historical(symbols=symbols, period='6mo')
        st.success("Historical model retrained and saved.")
    placeholder = st.empty()

    if st.session_state.run_demo:
        provider.step()
        rows = []
        latest_prices = {}
        filtered = 0
        for s in provider.get_symbols():
            hist5 = provider.get_history(s, 5)
            hist20 = provider.get_history(s, 20)
            hist60 = provider.get_history(s, 60)
            hist120 = provider.get_history(s, 120)

            l = provider.get_latest(s)
            p = l.get("ltp")
            if p is None:
                continue

            # Price filter
            if p < price_min or p > price_max:
                continue

            depth = provider.get_depth(s) if show_depth else {}
            bid_qty = depth.get('bid_qty', 0)
            ask_qty = depth.get('ask_qty', 0)
            if bid_qty < min_bid_qty or ask_qty < min_ask_qty:
                continue

            qty5 = aggregate_qty(hist5, 5)
            qty20 = aggregate_qty(hist20, 20)
            qty60 = aggregate_qty(hist60, 60)
            if qty5 < min_etq_5m or qty20 < min_etq_20m or qty60 < min_etq_60m:
                continue

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

            signal = ""
            if sm20 is not None and sm120 is not None:
                if sm20 > sm120:
                    signal = "BUY"
                elif sm20 < sm120:
                    signal = "SELL"

            features = build_feature_vector(hist5, hist20, hist60, hist120, depth)
            prob = predictor.predict_proba(features)
            decision = decision_from_signal(signal, prob)
            explanation = predictor.explain(features, signal, prob) if show_explanation else ''

            row = {
                "symbol": s,
                "ltp": round(p, 2),
                "smma20": round(sm20, 2) if sm20 else None,
                "smma120": round(sm120, 2) if sm120 else None,
                "signal": signal,
                "decision": decision,
                "etq_5m": qty5,
                "etq_20m": qty20,
                "etq_60m": qty60,
                "ltq_2m": round(average_ltq(hist5, 2), 2),
                "ltq_5m": round(average_ltq(hist5, 5), 2),
                "avg20m": round(avg_price(hist20, 20), 2) if avg_price(hist20, 20) else None,
                "avg60m": round(avg_price(hist60, 60), 2) if avg_price(hist60, 60) else None,
                "bid_price": depth.get('bid_price'),
                "bid_qty": bid_qty,
                "ask_price": depth.get('ask_price'),
                "ask_qty": ask_qty,
                "prob_signal": round(prob, 2),
                "explanation": explanation,
            }
            rows.append(row)
            latest_prices[s] = p
            filtered += 1
            st.session_state.trade_manager.update(s, signal, decision, p, datetime.utcnow())

        if filtered == 0 and provider.get_symbols():
            st.info("No symbols passed the current filters. Loosen liquidity or price filters to see more signals.")

        if rows:
            df = pd.DataFrame(rows).set_index("symbol")
        else:
            df = pd.DataFrame(columns=["ltp"])

        placeholder.dataframe(df)

        open_unrealized = st.session_state.trade_manager.unrealized_pnl(latest_prices)
        st.subheader("Portfolio Summary")
        cols = st.columns(4)
        cols[0].metric("Filtered Symbols", len(rows))
        cols[1].metric("Open Positions", len(st.session_state.trade_manager.open_positions))
        cols[2].metric("Realized P/L", f"₹{st.session_state.trade_manager.realized_pnl()}")
        cols[3].metric("Unrealized P/L", f"₹{open_unrealized}")

        if st.session_state.trade_manager.open_positions:
            st.markdown("**Open Positions**")
            open_df = pd.DataFrame(st.session_state.trade_manager.open_positions_list(latest_prices)).set_index('symbol')
            st.dataframe(open_df)

        if rows:
            csv = df.to_csv()
            st.download_button("Download CSV", csv, file_name=f"screener_snapshot_{int(time.time())}.csv", mime="text/csv", key="download_csv")
            if st.button("Save Snapshot", key="save_snapshot"):
                import os
                os.makedirs('snapshots', exist_ok=True)
                path = f"snapshots/snapshot_{int(time.time())}.csv"
                with open(path, 'w', encoding='utf8') as f:
                    f.write(csv)
                st.success(f"Saved snapshot to {path}")

        if st.session_state.trade_manager.trade_history:
            st.subheader("Trade History")
            trade_df = pd.DataFrame(st.session_state.trade_manager.trade_history)
            st.dataframe(trade_df)

        time.sleep(refresh_sec)
        st.experimental_rerun()


if __name__ == '__main__':
    main()
