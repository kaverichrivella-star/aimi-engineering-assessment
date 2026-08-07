import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

FEATURE_NAMES = [
    'ltq_2m',
    'ltq_5m',
    'etq_5m',
    'etq_20m',
    'etq_60m',
    'imbalance',
    'spread',
    'momentum_5m',
    'volatility_20m',
    'smma_distance',
]


class SignalPredictor:
    """ML wrapper. Loads persisted model if available, otherwise trains a heuristic model.
    For real deployment, replace this with historical market data and labeled outcomes.
    """
    def __init__(self, model_path: str = None):
        self.model_path = model_path or os.path.join(os.getcwd(), 'models', 'model.joblib')
        self.clf = RandomForestClassifier(n_estimators=150, random_state=42)
        self.fitted = False
        if os.path.exists(self.model_path):
            try:
                self.clf = joblib.load(self.model_path)
                self.fitted = True
            except Exception:
                self.fitted = False

    def fit_on_synthetic(self, n_samples=3000):
        rng = np.random.RandomState(42)
        X = np.zeros((n_samples, len(FEATURE_NAMES)))
        y = np.zeros(n_samples)
        for i in range(n_samples):
            ltq_2m = abs(rng.normal(250000, 150000))
            ltq_5m = abs(rng.normal(600000, 250000))
            etq_5m = abs(rng.normal(1500000, 800000))
            etq_20m = abs(rng.normal(4500000, 1500000))
            etq_60m = abs(rng.normal(12000000, 4000000))
            imbalance = rng.uniform(-1, 1)
            spread = abs(rng.normal(0.1, 0.05))
            momentum_5m = rng.normal(0, 0.01)
            volatility_20m = abs(rng.normal(0.01, 0.005))
            smma_distance = rng.normal(0, 1)
            X[i] = [
                ltq_2m,
                ltq_5m,
                etq_5m,
                etq_20m,
                etq_60m,
                imbalance,
                spread,
                momentum_5m,
                volatility_20m,
                smma_distance,
            ]
            y[i] = 1 if (momentum_5m > 0.001 and etq_5m > 1000000 and imbalance > 0) else 0

        self.clf.fit(X, y)
        self.fitted = True
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.clf, self.model_path)
        except Exception:
            pass

    def predict_proba(self, features):
        if not self.fitted:
            self.fit_on_synthetic()
        X = np.array(features).reshape(1, -1)
        if X.shape[1] != len(FEATURE_NAMES):
            raise ValueError(f'Expected {len(FEATURE_NAMES)} features, got {X.shape[1]}')
        p = self.clf.predict_proba(X)[0, 1]
        return float(p)

    def explain(self, features, signal, prob):
        reasons = []
        values = dict(zip(FEATURE_NAMES, features))
        if values['ltq_2m'] > 300000:
            reasons.append('Strong LTQ (2m)')
        if values['ltq_5m'] > 600000:
            reasons.append('Strong LTQ (5m)')
        if values['imbalance'] > 0.2:
            reasons.append('Bid dominance')
        elif values['imbalance'] < -0.2:
            reasons.append('Ask dominance')
        if values['spread'] < 0.2:
            reasons.append('Tight spread')
        if values['momentum_5m'] > 0.002:
            reasons.append('Positive momentum')
        if values['momentum_5m'] < -0.002:
            reasons.append('Negative momentum')
        if values['smma_distance'] > 0:
            reasons.append('Bullish SMMA distance')
        if values['smma_distance'] < 0:
            reasons.append('Bearish SMMA distance')

        decision = 'Accept' if (signal == 'BUY' and prob >= 0.6) or (signal == 'SELL' and prob <= 0.4) else 'Reject'
        reasons.append(f'Confidence {round(prob*100, 1)}%')
        if signal == 'BUY':
            reasons.insert(0, 'Signal BUY')
        elif signal == 'SELL':
            reasons.insert(0, 'Signal SELL')
        else:
            reasons.insert(0, 'Signal HOLD')

        return ' | '.join(reasons)
