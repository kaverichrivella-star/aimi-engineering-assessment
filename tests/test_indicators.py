import pandas as pd
from src.indicators import smma


def test_smma_basic():
    series = pd.Series([1,2,3,4,5,6,7,8,9,10])
    res = smma(series, 3)
    # Ensure same length
    assert len(res) == len(series)
    # First smma at index 2 should equal SMA of first 3
    assert abs(res.iat[2] - ((1+2+3)/3)) < 1e-6
