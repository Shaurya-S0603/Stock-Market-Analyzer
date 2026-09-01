from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import sqlite3
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    symbol: str
    model_name: str
    model_hash: str
    regime: str
    feature_columns: list[str]
    parameters: dict
    metrics: dict
    benchmark: dict
    feature_stats: dict


class ExperimentRegistry:
    """Persistent audit registry for research models and their validation evidence."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS experiments ("
                "experiment_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, model_name TEXT NOT NULL, "
                "model_hash TEXT NOT NULL, regime TEXT NOT NULL, feature_columns TEXT NOT NULL, "
                "parameters TEXT NOT NULL, metrics TEXT NOT NULL, benchmark TEXT NOT NULL, "
                "feature_stats TEXT NOT NULL DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(experiments)").fetchall()}
            if "feature_stats" not in columns:
                connection.execute("ALTER TABLE experiments ADD COLUMN feature_stats TEXT NOT NULL DEFAULT '{}'")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS model_drift_events ("
                "id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL, symbol TEXT NOT NULL, status TEXT NOT NULL, "
                "score REAL NOT NULL, details TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )

    @staticmethod
    def model_hash(model) -> str:
        digest = sha256()
        digest.update(np.asarray(model.coefficients, dtype=float).tobytes())
        digest.update(json.dumps(list(model.feature_columns), sort_keys=True).encode("utf-8"))
        digest.update(str(float(model.ridge_penalty)).encode("utf-8"))
        digest.update(str(float(model.momentum_weight)).encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _feature_stats(analysis) -> dict:
        stats: dict[str, dict[str, float]] = {}
        frame = analysis.training_features
        for column in analysis.model.feature_columns:
            if column not in frame.columns:
                continue
            values = frame[column].to_numpy(dtype=float)
            finite = values[np.isfinite(values)]
            if len(finite) == 0:
                continue
            stats[column] = {
                "mean": float(np.mean(finite)),
                "std": float(np.std(finite)),
                "p05": float(np.quantile(finite, 0.05)),
                "p95": float(np.quantile(finite, 0.95)),
            }
        return stats

    def record(self, analysis, request, benchmark: dict | None = None) -> ExperimentRecord:
        model_hash = self.model_hash(analysis.model)
        data_signature = f"{analysis.symbol}|{analysis.training_features.index.min()}|{analysis.training_features.index.max()}|{len(analysis.training_features)}"
        parameters = {
            "period": request.period,
            "interval": request.interval,
            "horizon": int(request.horizon),
            "context_period": getattr(request, "context_period", None),
            "context_interval": getattr(request, "context_interval", None),
            "benchmark_symbol": getattr(request, "benchmark_symbol", None),
            "buy_threshold": float(request.buy_threshold),
            "sell_threshold": float(request.sell_threshold),
            "round_trip_cost": float(request.round_trip_cost),
            "adaptive_buy_threshold": float(getattr(analysis, "adaptive_buy_threshold", request.buy_threshold)),
            "adaptive_sell_threshold": float(getattr(analysis, "adaptive_sell_threshold", request.sell_threshold)),
        }
        experiment_id = sha256(f"{data_signature}|{model_hash}|{json.dumps(parameters, sort_keys=True)}".encode("utf-8")).hexdigest()[:24]
        feature_stats = self._feature_stats(analysis)
        record = ExperimentRecord(
            experiment_id=experiment_id,
            symbol=str(analysis.symbol).upper(),
            model_name="ridge_momentum_context",
            model_hash=model_hash,
            regime=str(getattr(analysis, "regime", "unknown")),
            feature_columns=list(analysis.model.feature_columns),
            parameters=parameters,
            metrics={key: float(value) for key, value in analysis.model.metrics.items() if isinstance(value, (int, float, np.number))},
            benchmark=dict(benchmark or {}),
            feature_stats=feature_stats,
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO experiments(experiment_id, symbol, model_name, model_hash, regime, feature_columns, parameters, metrics, benchmark, feature_stats) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.experiment_id,
                    record.symbol,
                    record.model_name,
                    record.model_hash,
                    record.regime,
                    json.dumps(record.feature_columns),
                    json.dumps(record.parameters, sort_keys=True),
                    json.dumps(record.metrics, sort_keys=True),
                    json.dumps(record.benchmark, sort_keys=True),
                    json.dumps(record.feature_stats, sort_keys=True),
                ),
            )
        return record

    def recent(self, symbol: str | None = None, limit: int = 100) -> list[dict]:
        query = "SELECT * FROM experiments"
        params: list = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol.upper())
        query += " ORDER BY created_at DESC, experiment_id DESC LIMIT ?"
        params.append(int(limit))
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        output: list[dict] = []
        for row in rows:
            item = dict(row)
            for key in ("feature_columns", "parameters", "metrics", "benchmark", "feature_stats"):
                item[key] = json.loads(item[key])
            output.append(item)
        return output

    def record_drift(self, experiment_id: str, symbol: str, report) -> None:
        details = {
            "reasons": list(report.reasons),
            "max_feature_z": float(report.max_feature_z),
            "rmse_ratio": float(report.rmse_ratio),
            "directional_accuracy_drop": float(report.directional_accuracy_drop),
            "brier_delta": float(report.brier_delta),
        }
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO model_drift_events(experiment_id, symbol, status, score, details) VALUES (?, ?, ?, ?, ?)",
                (experiment_id, symbol.upper(), report.status, float(report.score), json.dumps(details, sort_keys=True)),
            )

    def drift_events(self, symbol: str | None = None, limit: int = 100) -> list[dict]:
        query = "SELECT * FROM model_drift_events"
        params: list = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol.upper())
        query += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item["details"])
            output.append(item)
        return output
