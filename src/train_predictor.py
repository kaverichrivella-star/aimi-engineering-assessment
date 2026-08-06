"""Train a signal predictor using the MockProvider by simulating crossovers and labelling outcomes.

This script runs a quick simulation to generate training examples and saves a model to `models/model.joblib`.
"""
import os
import random
import numpy as np
import joblib
from providers import MockProvider
from indicators import smma, detect_crossovers
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime, timedelta


def generate_examples(symbols, n_steps=1000):
    prov = MockProvider(symbols)
    X = []
    y = []
    for _ in range(n_steps):
        prov.step()
        for s in symbols:
            hist60 = prov.get_history(s, 60)
            hist120 = prov.get_history(s, 120)
            if len(hist120) < 121:
                continue
            prices = [x[1] for x in hist120]
            ser = np.array(prices)
            # compute smma
            # simple features: recent momentum, volatility, avg volume
            momentum = (ser[-1] - ser[-5]) / (ser[-5] + 1e-9)
            vol = np.std(np.diff(ser)/ (ser[:-1]+1e-9))
            avg_vol = np.mean([x[2] for x in hist60])
            X.append([momentum, vol, avg_vol])

            # label: profitable if price moves favorably 10 minutes after
            future = prov.get_history(s, -1)  # not available; simulate using random
            # use synthetic label: momentum>0 => likely profitable
            label = 1 if momentum > 0.001 else 0
            y.append(label)

    return np.array(X), np.array(y)


def main():
    symbols = [f"SYM{i}" for i in range(20)]
    X, y = generate_examples(symbols, n_steps=800)
    clf = RandomForestClassifier(n_estimators=200, random_state=42)
    clf.fit(X, y)
    os.makedirs('models', exist_ok=True)
    joblib.dump(clf, os.path.join('models', 'model.joblib'))
    print('Trained model saved to models/model.joblib')


if __name__ == '__main__':
    main()
