"""Persistent paper-trading capture, model training, and next-day evaluation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from predictor import FEATURE_NAMES

CAPTURE_COLUMNS = list(dict.fromkeys([
    "timestamp",
    "symbol",
    "ltp",
    "signal",
    "prob_signal",
    "decision",
    "etq_5m",
    "etq_20m",
    "etq_60m",
    "ltq_2m",
    "ltq_5m",
    "avg20m",
    "avg60m",
    "bid_qty",
    "ask_qty",
    "bid_price",
    "ask_price",
    "explanation",
] + FEATURE_NAMES))


@dataclass
class PaperTrade:
    symbol: str
    side: str
    entry_time: str
    entry_price: float
    exit_time: str | None = None
    exit_price: float | None = None
    pnl: float | None = None
    status: str = "OPEN"
    reason: str = ""


class CaptureStore:
    """Append-only daily capture store. It never sends broker orders."""

    def __init__(self, root: str | Path = "data/captures"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, value: datetime | str | None = None) -> Path:
        if value is None:
            value = datetime.now(timezone.utc)
        if isinstance(value, str):
            date_part = value[:10]
        else:
            date_part = value.astimezone(timezone.utc).date().isoformat()
        return self.root / f"capture_{date_part}.csv"

    def append(self, rows: Iterable[dict], timestamp: datetime | None = None) -> Path:
        path = self.path_for(timestamp)
        normalized = []
        for row in rows:
            item = {key: row.get(key, "") for key in CAPTURE_COLUMNS}
            value = item["timestamp"] or timestamp or datetime.now(timezone.utc)
            if isinstance(value, datetime):
                value = value.astimezone(timezone.utc).isoformat()
            item["timestamp"] = value
            normalized.append(item)
        if not normalized:
            return path

        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CAPTURE_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerows(normalized)
        return path

    def load(self, value: datetime | str | Path) -> pd.DataFrame:
        path = Path(value) if isinstance(value, Path) else self.path_for(value)
        if not path.exists():
            return pd.DataFrame(columns=CAPTURE_COLUMNS)
        frame = pd.read_csv(path)
        for column in CAPTURE_COLUMNS:
            if column not in frame:
                frame[column] = np.nan
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        numeric = [column for column in CAPTURE_COLUMNS if column not in {"timestamp", "symbol", "signal", "explanation"}]
        for column in numeric:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame.dropna(subset=["timestamp", "symbol", "ltp"]).sort_values(["symbol", "timestamp"])


class PaperTradeBook:
    """Virtual trade ledger for signal-driven paper trading only."""

    def __init__(self):
        self.open_positions: dict[str, PaperTrade] = {}
        self.closed_trades: list[PaperTrade] = []

    def apply(self, symbol: str, signal: str, price: float, timestamp: datetime, reason: str = ""):
        if signal not in {"BUY", "SELL"}:
            return
        current = self.open_positions.get(symbol)
        if current and current.side == signal:
            return
        if current:
            self.close(symbol, price, timestamp, reason="Reverse signal")
        self.open_positions[symbol] = PaperTrade(
            symbol=symbol,
            side=signal,
            entry_time=timestamp.astimezone(timezone.utc).isoformat(),
            entry_price=float(price),
            reason=reason,
        )

    def close(self, symbol: str, price: float, timestamp: datetime, reason: str = ""):
        trade = self.open_positions.pop(symbol, None)
        if not trade:
            return
        trade.exit_time = timestamp.astimezone(timezone.utc).isoformat()
        trade.exit_price = float(price)
        trade.pnl = round(
            trade.exit_price - trade.entry_price
            if trade.side == "BUY"
            else trade.entry_price - trade.exit_price,
            4,
        )
        trade.status = "CLOSED"
        if reason:
            trade.reason = reason
        self.closed_trades.append(trade)

    def summary(self) -> dict:
        pnl = [trade.pnl for trade in self.closed_trades if trade.pnl is not None]
        profitable = sum(value > 0 for value in pnl)
        unsuccessful = sum(value <= 0 for value in pnl)
        total = len(pnl)
        return {
            "paper_trades": total,
            "profitable_trades": profitable,
            "profitable_pct": round(profitable / total * 100, 2) if total else 0.0,
            "unsuccessful_trades": unsuccessful,
            "unsuccessful_pct": round(unsuccessful / total * 100, 2) if total else 0.0,
            "overall_pnl": round(sum(pnl), 4),
            "open_positions": len(self.open_positions),
        }

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(trade) for trade in self.closed_trades])


def train_from_capture(capture: pd.DataFrame, model_path: str | Path, hold_minutes: int = 5) -> dict:
    """Train from captured intraday bars using forward returns as labels."""
    if capture.empty:
        raise ValueError("The capture is empty; collect a complete trading day first.")
    capture = capture.sort_values(["symbol", "timestamp"]).copy()
    rows = []
    labels = []
    for symbol, group in capture.groupby("symbol"):
        group = group.sort_values("timestamp").reset_index(drop=True)
        for index, row in group.iterrows():
            target_time = row["timestamp"] + pd.Timedelta(minutes=hold_minutes)
            future = group[group["timestamp"] >= target_time]
            if future.empty:
                continue
            future_price = float(future.iloc[0]["ltp"])
            feature_values = [pd.to_numeric(row.get(name), errors="coerce") for name in FEATURE_NAMES]
            if any(pd.isna(feature_values)):
                continue
            rows.append(feature_values)
            side_return = (future_price - float(row["ltp"])) / float(row["ltp"])
            labels.append(int(side_return >= 0.001))

    if len(rows) < 50 or len(set(labels)) < 2:
        raise ValueError(f"Need at least 50 labeled rows and both outcomes; found {len(rows)} rows.")
    classifier = RandomForestClassifier(n_estimators=250, random_state=42, class_weight="balanced_subsample")
    classifier.fit(np.asarray(rows), np.asarray(labels))
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, model_path)
    return {"training_rows": len(rows), "positive_labels": int(sum(labels)), "model_path": str(model_path)}


def evaluate_next_day(
    capture: pd.DataFrame,
    model_path: str | Path,
    min_confidence: float = 0.60,
    hold_minutes: int = 5,
) -> tuple[pd.DataFrame, dict]:
    """Evaluate next-day crossover signals using the prior day's trained model."""
    if capture.empty:
        return pd.DataFrame(), empty_evaluation()
    classifier = joblib.load(model_path)
    capture = capture.sort_values(["symbol", "timestamp"]).copy()
    evaluations = []

    for symbol, group in capture.groupby("symbol"):
        group = group.sort_values("timestamp").reset_index(drop=True)
        for index, row in group.iterrows():
            signal = str(row.get("signal", ""))
            if signal not in {"BUY", "SELL"}:
                continue
            future_time = row["timestamp"] + pd.Timedelta(minutes=hold_minutes)
            future = group[group["timestamp"] >= future_time]
            if future.empty:
                continue
            features = [pd.to_numeric(row.get(name), errors="coerce") for name in FEATURE_NAMES]
            if any(pd.isna(features)):
                continue
            probability = float(classifier.predict_proba(np.asarray(features).reshape(1, -1))[0, 1])
            accepted = probability >= min_confidence if signal == "BUY" else probability <= (1 - min_confidence)
            future_price = float(future.iloc[0]["ltp"])
            raw_return = (future_price - float(row["ltp"])) / float(row["ltp"])
            signed_return = raw_return if signal == "BUY" else -raw_return
            if accepted:
                reason = "Accepted: crossover plus model confidence passed threshold."
            elif probability < min_confidence and signal == "BUY":
                reason = "Avoided: BUY confidence below threshold."
            elif probability > (1 - min_confidence) and signal == "SELL":
                reason = "Avoided: SELL confidence below threshold."
            else:
                reason = "Avoided: model confidence did not support the crossover direction."
            evaluations.append({
                "timestamp": row["timestamp"].isoformat(),
                "symbol": symbol,
                "signal": signal,
                "entry_price": float(row["ltp"]),
                "exit_price": future_price,
                "model_confidence": round(probability, 4),
                "accepted": accepted,
                "outcome_pnl_pct": round(signed_return * 100, 4) if accepted else 0.0,
                "reason": reason,
            })

    result = pd.DataFrame(evaluations)
    if result.empty:
        return result, empty_evaluation()
    accepted = result[result["accepted"]]
    profitable = accepted[accepted["outcome_pnl_pct"] > 0]
    unsuccessful = accepted[accepted["outcome_pnl_pct"] <= 0]
    summary = {
        "crossover_signals": len(result),
        "accepted_signals": len(accepted),
        "avoided_signals": int((~result["accepted"]).sum()),
        "successful_trades": len(profitable),
        "unsuccessful_trades": len(unsuccessful),
        "success_pct": round(len(profitable) / len(accepted) * 100, 2) if len(accepted) else 0.0,
        "failure_pct": round(len(unsuccessful) / len(accepted) * 100, 2) if len(accepted) else 0.0,
        "avoided_pct": round((~result["accepted"]).mean() * 100, 2),
        "overall_pnl_pct": round(float(accepted["outcome_pnl_pct"].sum()), 4),
    }
    return result, summary


def empty_evaluation() -> dict:
    return {
        "crossover_signals": 0,
        "accepted_signals": 0,
        "avoided_signals": 0,
        "successful_trades": 0,
        "unsuccessful_trades": 0,
        "success_pct": 0.0,
        "failure_pct": 0.0,
        "avoided_pct": 0.0,
        "overall_pnl_pct": 0.0,
    }


def latest_capture(root: str | Path = "data/captures") -> Path | None:
    paths = sorted(Path(root).glob("capture_*.csv"))
    return paths[-1] if paths else None


def save_json(payload: dict, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
