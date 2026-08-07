import time
import random
from collections import deque, defaultdict
from datetime import datetime, timedelta

class BaseProvider:
    def get_symbols(self):
        raise NotImplementedError()

    def get_latest(self, symbol):
        raise NotImplementedError()

    def get_depth(self, symbol):
        raise NotImplementedError()

    def get_history(self, symbol, minutes):
        raise NotImplementedError()


class MockProvider(BaseProvider):
    """Simulates streaming market data for development and testing."""
    def __init__(self, symbols):
        self.symbols = symbols
        self.state = {}
        self.history = defaultdict(lambda: deque())
        now = datetime.utcnow()
        for s in symbols:
            price = random.uniform(50, 200)
            self.state[s] = {
                "price": price,
            }
            # seed 2 hours of 1-min bars
            for i in range(120):
                t = now - timedelta(minutes=120 - i)
                p = price + random.uniform(-1, 1)
                qty = random.randint(200000, 800000)
                self.history[s].append((t, p, qty))

    def step(self):
        now = datetime.utcnow()
        for s in self.symbols:
            last = self.state[s]["price"]
            newp = max(1.0, last * (1 + random.uniform(-0.002, 0.002)))
            self.state[s]["price"] = newp
            qty = random.randint(50000, 500000)
            self.history[s].append((now, newp, qty))
            # keep 24 hours of 1-min points
            while len(self.history[s]) > 60 * 24:
                self.history[s].popleft()

    def get_symbols(self):
        return list(self.symbols)

    def get_latest(self, symbol):
        p = self.state[symbol]["price"]
        return {"symbol": symbol, "ltp": p}

    def get_depth(self, symbol):
        p = self.state[symbol]["price"]
        spread = max(0.01, p * 0.0005)
        return {
            "bid_price": round(p - spread, 2),
            "bid_qty": random.randint(1000000, 2500000),
            "ask_price": round(p + spread, 2),
            "ask_qty": random.randint(1000000, 2500000),
        }

    def get_history(self, symbol, minutes):
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [(t, p, q) for (t, p, q) in self.history[symbol] if t >= cutoff]


class YFinanceProvider(BaseProvider):
    """Fallback live market provider using Yahoo Finance when broker endpoints are unavailable."""
    def __init__(self, symbols):
        self.raw_symbols = symbols
        self.symbols = [s if s.endswith('.NS') else f'{s}.NS' for s in symbols]

    def step(self):
        time.sleep(0)

    def get_symbols(self):
        return self.raw_symbols

    def _normalize_symbol(self, symbol):
        return symbol if symbol.endswith('.NS') else f'{symbol}.NS'

    def get_latest(self, symbol):
        try:
            import yfinance as yf
            sym = self._normalize_symbol(symbol)
            ticker = yf.Ticker(sym)
            hist = ticker.history(period='1d', interval='1m')
            if hist.empty:
                hist = ticker.history(period='5d', interval='1d')
            if hist.empty:
                return {'symbol': symbol, 'ltp': None}
            last_price = float(hist['Close'].iloc[-1])
            return {'symbol': symbol, 'ltp': last_price}
        except Exception:
            return {'symbol': symbol, 'ltp': None}

    def get_depth(self, symbol):
        latest = self.get_latest(symbol)
        p = latest.get('ltp') or 0.0
        spread = max(0.01, p * 0.001)
        return {
            'bid_price': round(p - spread, 2),
            'bid_qty': 1000000,
            'ask_price': round(p + spread, 2),
            'ask_qty': 1000000,
        }

    def get_history(self, symbol, minutes):
        try:
            import yfinance as yf
            sym = self._normalize_symbol(symbol)
            interval = '1m' if minutes <= 60 else '5m'
            period = '2d' if minutes <= 60 else '7d'
            hist = yf.Ticker(sym).history(period=period, interval=interval)
            if hist.empty:
                return []
            out = []
            for idx, row in hist.iterrows():
                out.append((idx.to_pydatetime(), float(row['Close']), int(row.get('Volume', 0))))
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            return [(t, p, q) for (t, p, q) in out if t >= cutoff]
        except Exception:
            return []


class FyersProvider(BaseProvider):
    """Placeholder for a Fyers API adapter.
    Implement authentication and fetches here.
    See README for notes on adding API keys.
    """
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token

    def get_symbols(self):
        raise NotImplementedError("Implement Fyers symbol list retrieval")

    def get_latest(self, symbol):
        raise NotImplementedError()

    def get_depth(self, symbol):
        raise NotImplementedError()

    def get_history(self, symbol, minutes):
        raise NotImplementedError()


class AngelProvider(BaseProvider):
    """Placeholder for an Angel One API adapter."""
    def __init__(self, client_id, api_key):
        self.client_id = client_id
        self.api_key = api_key

    def get_symbols(self):
        raise NotImplementedError()

    def get_latest(self, symbol):
        raise NotImplementedError()

    def get_depth(self, symbol):
        raise NotImplementedError()

    def get_history(self, symbol, minutes):
        raise NotImplementedError()
