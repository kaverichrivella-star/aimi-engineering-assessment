import os
import pytest

from src.adapters.fyers_adapter import FyersAdapter
from src.adapters.angel_adapter import AngelAdapter


def test_fyers_adapter_requires_token():
    cfg = {'api_key': None, 'access_token': None}
    fa = FyersAdapter(cfg)
    with pytest.raises(RuntimeError):
        fa._auth_header()


def test_angel_adapter_requires_key():
    cfg = {'api_key': None}
    ag = AngelAdapter(cfg)
    with pytest.raises(RuntimeError):
        ag._auth_header()
