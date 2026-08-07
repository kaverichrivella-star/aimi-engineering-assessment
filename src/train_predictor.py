"""Train the signal predictor using live historical market data from Yahoo Finance.

This script downloads historical NSE data for selected sample tickers, constructs market microstructure features,
trains a RandomForest classifier, and saves the model to `models/model.joblib`.
"""
import os
from predictor import SignalPredictor


def main():
    symbols = [
        'RELIANCE.NS',
        'TCS.NS',
        'INFY.NS',
        'HDFC.NS',
        'ICICIBANK.NS',
        'AXISBANK.NS',
        'HINDUNILVR.NS',
        'ITC.NS',
        'LT.NS',
        'SBIN.NS',
    ]
    predictor = SignalPredictor()
    predictor.fit_on_historical(symbols=symbols, period='9mo')
    print('Historical model trained and saved to', predictor.model_path)


if __name__ == '__main__':
    main()
