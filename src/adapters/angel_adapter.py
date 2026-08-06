import os
import requests
from typing import List, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class AngelAdapter:
    """Angel One adapter with configurable base and endpoints.

    Configure via `cfg` dict with keys:
      - api_key (or access token)
      - base (optional)
      - instrument_map_endpoint (optional)

    Adjust endpoint paths to match the broker docs.
    """

    def __init__(self, cfg: Dict[str, str]):
        self.client_id = cfg.get('client_id')
        self.api_key = cfg.get('api_key')
        self.base = cfg.get('base', 'https://api.angelone.in')
        self.instrument_map_endpoint = cfg.get('instrument_map_endpoint')
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def _auth_header(self) -> Dict[str, str]:
        if not self.api_key:
            raise RuntimeError('Angel One API key not configured')
        return {'Authorization': f'Bearer {self.api_key}'}

    def get_symbols(self) -> List[str]:
        if not self.instrument_map_endpoint:
            raise NotImplementedError('Provide instrument_map_endpoint in cfg to fetch symbol list')
        r = self.session.get(self.instrument_map_endpoint, headers=self._auth_header(), timeout=10)
        r.raise_for_status()
        data = r.json()
        syms = []
        for itm in data:
            sym = itm.get('symbol') or itm.get('tradingsymbol')
            if sym:
                syms.append(sym)
        return syms

    def get_latest(self, symbol: str) -> Dict[str, Any]:
        path = f"{self.base}/marketdata/quotes/{symbol}"
        r = self.session.get(path, headers=self._auth_header(), timeout=5)
        r.raise_for_status()
        j = r.json()
        ltp = j.get('ltp') or j.get('last_price') or j.get('lastTradedPrice')
        return {'symbol': symbol, 'ltp': float(ltp) if ltp is not None else None}

    def get_depth(self, symbol: str) -> Dict[str, Any]:
        path = f"{self.base}/marketdata/depth/{symbol}"
        r = self.session.get(path, headers=self._auth_header(), timeout=5)
        r.raise_for_status()
        j = r.json()
        bids = j.get('bids') or j.get('buy')
        asks = j.get('asks') or j.get('sell')
        bid_price = bids[0][0] if bids and isinstance(bids[0], (list, tuple)) else (bids[0].get('price') if bids else None)
        bid_qty = bids[0][1] if bids and isinstance(bids[0], (list, tuple)) else (bids[0].get('quantity') if bids else None)
        ask_price = asks[0][0] if asks and isinstance(asks[0], (list, tuple)) else (asks[0].get('price') if asks else None)
        ask_qty = asks[0][1] if asks and isinstance(asks[0], (list, tuple)) else (asks[0].get('quantity') if asks else None)
        return {'bid_price': bid_price, 'bid_qty': bid_qty, 'ask_price': ask_price, 'ask_qty': ask_qty}

    def get_history(self, symbol: str, minutes: int):
        path = f"{self.base}/marketdata/history/{symbol}?interval=1m&range={minutes}m"
        r = self.session.get(path, headers=self._auth_header(), timeout=10)
        r.raise_for_status()
        j = r.json()
        out = []
        for bar in j:
            t = bar.get('timestamp') or bar.get('time')
            price = bar.get('close') or bar.get('price')
            qty = bar.get('volume') or bar.get('quantity') or 0
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
