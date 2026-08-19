import os
import requests
from typing import List, Dict, Any
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class FyersAdapter:
    """Fyers adapter implementation with configurable endpoints.

    This implementation uses simple REST polling. Configure via `cfg` dict:
      - api_key
      - access_token
      - base (optional)
      - instrument_map_endpoint (optional)

    The exact endpoint paths may need adjustment to match the broker docs.
    """

    def __init__(self, cfg: Dict[str, str]):
        self.api_key = cfg.get('api_key') or cfg.get('FYERS_API_KEY')
        self.access_token = cfg.get('access_token') or cfg.get('FYERS_ACCESS_TOKEN')
        self.base = cfg.get('base') or cfg.get('FYERS_BASE_URL', 'https://api-t1.fyers.in')
        self.instrument_map_endpoint = cfg.get('instrument_map_endpoint') or cfg.get('FYERS_INSTRUMENT_MAP_ENDPOINT')
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def _auth_header(self) -> Dict[str, str]:
        if not self.access_token:
            raise RuntimeError('FYERS access token not configured')
        if not self.api_key:
            raise RuntimeError('FYERS API key not configured')
        return {'Authorization': f'{self.api_key}:{self.access_token}'}

    @staticmethod
    def _symbol(symbol: str) -> str:
        if ':' in symbol:
            return symbol
        if symbol.endswith('-EQ'):
            return f'NSE:{symbol}'
        return f'NSE:{symbol}-EQ'

    def get_symbols(self) -> List[str]:
        """Fetch list of NSE symbols. If an instrument map endpoint is provided, call it; otherwise raise.
        Returns a list of symbol strings compatible with the rest of the app.
        """
        if not self.instrument_map_endpoint:
            raise NotImplementedError('Provide instrument_map_endpoint in cfg to fetch symbol list')
        url = self.instrument_map_endpoint
        r = self.session.get(url, headers=self._auth_header(), timeout=10)
        r.raise_for_status()
        payload = r.json()
        data = payload.get('d', payload) if isinstance(payload, dict) else payload
        if isinstance(data, dict):
            data = data.get('data', data.get('symbols', []))
        symbols = []
        for itm in data:
            if isinstance(itm, str):
                sym = itm
            else:
                sym = itm.get('symbol') or itm.get('tradingsymbol')
            if sym:
                symbols.append(str(sym).replace('NSE:', '').replace('-EQ', ''))
        return symbols

    def get_latest(self, symbol: str) -> Dict[str, Any]:
        """Get LTP/quote for a single symbol. Returns dict {symbol, ltp}.

        This method assumes a quote endpoint like /v2/quotations or similar.
        Adjust `path` as per actual API docs.
        """
        path = f"{self.base}/data/quotes"
        r = self.session.post(
            path,
            headers=self._auth_header(),
            json={'symbols': self._symbol(symbol)},
            timeout=5,
        )
        r.raise_for_status()
        payload = r.json()
        data = payload.get('d', []) if isinstance(payload, dict) else []
        quote = data[0].get('v', {}) if data else {}
        ltp = quote.get('lp') or quote.get('last_price') or quote.get('lastTradedPrice')
        return {'symbol': symbol, 'ltp': float(ltp) if ltp is not None else None}

    def get_depth(self, symbol: str) -> Dict[str, Any]:
        """Fetch order-book / market depth for the symbol.
        Returns keys: bid_price, bid_qty, ask_price, ask_qty.
        """
        path = f"{self.base}/data/depth"
        r = self.session.post(
            path,
            headers=self._auth_header(),
            json={'symbol': self._symbol(symbol), 'ohlcv_flag': '1'},
            timeout=5,
        )
        r.raise_for_status()
        payload = r.json()
        data = payload.get('d', {}) if isinstance(payload, dict) else {}
        bids = data.get('bids', []) if isinstance(data, dict) else []
        asks = data.get('ask', data.get('asks', [])) if isinstance(data, dict) else []

        def level(values):
            if not values:
                return None, None
            first = values[0]
            if isinstance(first, (list, tuple)):
                return first[0], first[1]
            return first.get('price'), first.get('volume', first.get('quantity'))

        bid_price, bid_qty = level(bids)
        ask_price, ask_qty = level(asks)

        return {'bid_price': bid_price, 'bid_qty': bid_qty, 'ask_price': ask_price, 'ask_qty': ask_qty}

    def get_history(self, symbol: str, minutes: int):
        """Fetch minute-level historical bars/trades for the last `minutes` minutes.

        Returns a list of tuples (timestamp(datetime), price(float), qty(int)).
        The adapter will try to call a minute-history endpoint; if not available, raise NotImplementedError.
        """
        now = int(time.time())
        start = now - (int(minutes) * 60)
        path = f"{self.base}/data/history"
        params = {
            'symbol': self._symbol(symbol),
            'resolution': '1',
            'date_format': '0',
            'range_from': start,
            'range_to': now,
            'cont_flag': '1',
        }
        r = self.session.get(path, headers=self._auth_header(), params=params, timeout=10)
        r.raise_for_status()
        payload = r.json()
        candles = payload.get('candles', []) if isinstance(payload, dict) else []
        out = []
        for candle in candles:
            if len(candle) < 6:
                continue
            t, _open, _high, _low, price, qty = candle[:6]
            try:
                import datetime as _dt
                dt = _dt.datetime.fromtimestamp(float(t), tz=_dt.timezone.utc)
            except Exception:
                continue
            out.append((dt, float(price), int(qty or 0)))
        return out
