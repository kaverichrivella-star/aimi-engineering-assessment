import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os


class SignalPredictor:
    """ML wrapper. Loads persisted model if available, otherwise trains a synthetic model.
    For real deployment, replace synthetic training with historical labelled data training.
    """
    def __init__(self, model_path: str = None):
        self.model_path = model_path or os.path.join(os.getcwd(), 'models', 'model.joblib')
        self.clf = RandomForestClassifier(n_estimators=100, random_state=42)
        self.fitted = False
        if os.path.exists(self.model_path):
            try:
                self.clf = joblib.load(self.model_path)
                self.fitted = True
            except Exception:
                self.fitted = False

    def fit_on_synthetic(self, n_samples=2000):
        rng = np.random.RandomState(42)
        X = np.zeros((n_samples, 3))
        y = np.zeros(n_samples)
        for i in range(n_samples):
            mom = rng.normal(0, 1)
            vol = abs(rng.normal(0.5, 0.5))
            vol_change = rng.normal(0, 1)
            X[i] = [mom, vol, vol_change]
            y[i] = 1 if (mom > 0.5 and vol < 1.0) else 0

        self.clf.fit(X, y)
        self.fitted = True
        # persist model
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.clf, self.model_path)
        except Exception:
            pass

    def predict_proba(self, features):
        if not self.fitted:
            self.fit_on_synthetic()
        X = np.array(features).reshape(1, -1)
        p = self.clf.predict_proba(X)[0, 1]
        return float(p)
