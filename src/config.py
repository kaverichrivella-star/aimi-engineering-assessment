import os
from typing import Dict

def load_config() -> Dict[str, str]:
    """Load configuration from environment variables. Optionally loads a .env file if python-dotenv is present."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    def _env(*names):
        for name in names:
            val = os.environ.get(name)
            if val:
                return val
        return None

    return {
        'api_key': _env('FYERS_API_KEY', 'FYERS_APIKEY', 'FYERS_KEY'),
        'access_token': _env('FYERS_ACCESS_TOKEN', 'FYERS_TOKEN', 'FYERS_ACCESS'),
        'FYERS_BASE_URL': _env('FYERS_BASE_URL') or 'https://api-t1.fyers.in',
        'instrument_map_endpoint': _env('FYERS_INSTRUMENT_MAP_ENDPOINT', 'FYERS_INSTRUMENT_MAP_URL'),
        'angel_instrument_map_endpoint': _env('ANGEL_INSTRUMENT_MAP_ENDPOINT', 'ANGEL_INSTRUMENT_MAP_URL'),
        'angel_client_id': _env('ANGEL_CLIENT_ID', 'ANGEL_CLIENTID'),
        'angel_api_key': _env('ANGEL_API_KEY', 'ANGEL_APIKEY'),
        'FYERS_API_KEY': os.environ.get('FYERS_API_KEY'),
        'FYERS_ACCESS_TOKEN': os.environ.get('FYERS_ACCESS_TOKEN'),
        'FYERS_INSTRUMENT_MAP_ENDPOINT': os.environ.get('FYERS_INSTRUMENT_MAP_ENDPOINT'),
        'ANGEL_CLIENT_ID': os.environ.get('ANGEL_CLIENT_ID'),
        'ANGEL_API_KEY': os.environ.get('ANGEL_API_KEY'),
        'ANGEL_INSTRUMENT_MAP_ENDPOINT': os.environ.get('ANGEL_INSTRUMENT_MAP_ENDPOINT'),
    }
