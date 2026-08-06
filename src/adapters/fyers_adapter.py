import os
import requests
from typing import List, Dict, Any, Optional
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
        self.base = cfg.get('base', 'https://api.fyers.in')
        self.instrument_map_endpoint = cfg.get('instrument_map_endpoint')
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def _auth_header(self) -> Dict[str, str]:
        if not self.access_token:
            raise RuntimeError('FYERS access token not configured')
        return {'Authorization': f'Bearer {self.access_token}'}

    def get_symbols(self) -> List[str]:
        """Fetch list of NSE symbols. If an instrument map endpoint is provided, call it; otherwise raise.
        Returns a list of symbol strings compatible with the rest of the app.
        """
        if not self.instrument_map_endpoint:
            raise NotImplementedError('Provide instrument_map_endpoint in cfg to fetch symbol list')
        url = self.instrument_map_endpoint
        r = self.session.get(url, headers=self._auth_header(), timeout=10)
        r.raise_for_status()
        data = r.json()
        # Assume data is a list of objects with 'symbol' key
        symbols = []
        for itm in data:
            sym = itm.get('symbol') or itm.get('tradingsymbol')
            if sym:
                symbols.append(sym)
        return symbols

    def get_latest(self, symbol: str) -> Dict[str, Any]:
        """Get LTP/quote for a single symbol. Returns dict {symbol, ltp}.

        This method assumes a quote endpoint like /v2/quotations or similar.
        Adjust `path` as per actual API docs.
        """
        path = f"{self.base}/v2/quotes/{symbol}"
        r = self.session.get(path, headers=self._auth_header(), timeout=5)
        if r.status_code == 404:
            raise
        r.raise_for_status()
        j = r.json()
        # Attempt common response shapes
        ltp = None
        if isinstance(j, dict):
            ltp = j.get('ltp') or j.get('last_price') or j.get('lastTradedPrice')
        return {'symbol': symbol, 'ltp': float(ltp) if ltp is not None else None}

    def get_depth(self, symbol: str) -> Dict[str, Any]:
        """Fetch order-book / market depth for the symbol.
        Returns keys: bid_price, bid_qty, ask_price, ask_qty.
        """
        path = f"{self.base}/v2/depth/{symbol}"
        r = self.session.get(path, headers=self._auth_header(), timeout=5)
        r.raise_for_status()
        j = r.json()
        # parse common shapes
        bid_price = None
        bid_qty = None
        ask_price = None
        ask_qty = None
        if isinstance(j, dict):
            # try nested fields
            bids = j.get('bids') or j.get('buy')
            asks = j.get('asks') or j.get('sell')
            if bids and len(bids) > 0:
                bid_price = bids[0][0] if isinstance(bids[0], (list, tuple)) else bids[0].get('price')
                bid_qty = bids[0][1] if isinstance(bids[0], (list, tuple)) else bids[0].get('quantity')
            if asks and len(asks) > 0:
                ask_price = asks[0][0] if isinstance(asks[0], (list, tuple)) else asks[0].get('price')
                ask_qty = asks[0][1] if isinstance(asks[0], (list, tuple)) else asks[0].get('quantity')

        return {'bid_price': bid_price, 'bid_qty': bid_qty, 'ask_price': ask_price, 'ask_qty': ask_qty}

    def get_history(self, symbol: str, minutes: int):
        """Fetch minute-level historical bars/trades for the last `minutes` minutes.

        Returns a list of tuples (timestamp(datetime), price(float), qty(int)).
        The adapter will try to call a minute-history endpoint; if not available, raise NotImplementedError.
        """
        # Example placeholder path — adapt to broker docs
        path = f"{self.base}/v2/history/{symbol}?interval=1m&range={minutes}m"
        r = self.session.get(path, headers=self._auth_header(), timeout=10)
        r.raise_for_status()
        j = r.json()
        out = []
        # Expect j to be list of bars with time/close/volume
        for bar in j:
            t = bar.get('timestamp') or bar.get('time')
            price = bar.get('close') or bar.get('price')
            qty = bar.get('volume') or bar.get('quantity') or 0
            # normalize timestamp to python datetime if numeric
            try:
                import datetime as _dt
                if isinstance(t, (int, float)):
                    dt = _dt.datetime.utcfromtimestamp(t)
                else:
                    dt = _dt.datetime.fromisoformat(t)
            except Exception:
                dt = None
            out.append((dt, float(price) if price is not None else None, int(qty)))
        return out
