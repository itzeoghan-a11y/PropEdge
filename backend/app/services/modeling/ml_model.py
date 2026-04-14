"""
Machine Learning Model — XGBoost gradient boosting.

The model is trained offline (or during a scheduled job) and persisted
to disk.  At inference time the model is loaded and used to predict
P(stat > line).

Features used (order must match training):
  [0]  rolling_avg_5
  [1]  rolling_avg_10
  [2]  rolling_avg_season
  [3]  rolling_median_10
  [4]  rolling_std_10
  [5]  weighted_avg_5
  [6]  hit_rate_line         — empirical hit rate vs current line
  [7]  minutes_avg_5
  [8]  usage_avg_5
  [9]  days_rest
  [10] is_home
  [11] opp_def_rank_pct
  [12] sharp_implied_prob
  [13] soft_avg_implied_prob
  [14] sharp_soft_deviation
  [15] line_vs_rolling_avg
  [16] odds_dispersion
  [17] sample_size
  [18] line
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import joblib
import numpy as np

if TYPE_CHECKING:
    from app.services.features.engineer import PropFeatures

log = logging.getLogger(__name__)

MODEL_DIR = Path(os.getenv("MODEL_CACHE_DIR", "model_cache"))
MODEL_PATH = MODEL_DIR / "xgb_prop_model.joblib"
CALIBRATOR_PATH = MODEL_DIR / "calibrator.joblib"

FEATURE_NAMES = [
    "rolling_avg_5",
    "rolling_avg_10",
    "rolling_avg_season",
    "rolling_median_10",
    "rolling_std_10",
    "weighted_avg_5",
    "hit_rate_line",
    "minutes_avg_5",
    "usage_avg_5",
    "days_rest",
    "is_home",
    "opp_def_rank_pct",
    "sharp_implied_prob",
    "soft_avg_implied_prob",
    "sharp_soft_deviation",
    "line_vs_rolling_avg",
    "odds_dispersion",
    "sample_size",
    "line",
]


class MLModel:
    def __init__(self) -> None:
        self._model = None
        self._calibrator = None
        self._loaded = False

    def load(self) -> bool:
        """Load trained model from disk. Returns True on success."""
        if not MODEL_PATH.exists():
            log.info("ML model not found at %s — will use other models only", MODEL_PATH)
            return False
        try:
            self._model = joblib.load(MODEL_PATH)
            if CALIBRATOR_PATH.exists():
                self._calibrator = joblib.load(CALIBRATOR_PATH)
            self._loaded = True
            log.info("ML model loaded from %s", MODEL_PATH)
            return True
        except Exception as exc:
            log.error("Failed to load ML model: %s", exc)
            return False

    def predict_prob_over(self, features: "PropFeatures") -> float | None:
        """Return P(stat > line) or None if the model is not loaded."""
        if not self._loaded or self._model is None:
            return None

        try:
            x = features.to_model_array(sharp_books=[]).reshape(1, -1)
            raw_prob = float(self._model.predict_proba(x)[0, 1])
            if self._calibrator is not None:
                raw_prob = float(self._calibrator.predict_proba(
                    np.array([[raw_prob]])
                )[0, 1])
            return float(np.clip(raw_prob, 0.01, 0.99))
        except Exception as exc:
            log.warning("ML model inference failed: %s", exc)
            return None

    # ── Training (run via CLI / Celery task) ──────────────────────────────────

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        n_estimators: int = 500,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        eval_fraction: float = 0.15,
    ) -> dict[str, float]:
        """
        Train XGBoost model + Platt calibration.

        Parameters
        ----------
        X : (n_samples, n_features) float array
        y : (n_samples,) binary (1 = stat went over line, 0 = under)

        Returns metrics dict.
        """
        try:
            from xgboost import XGBClassifier
            from sklearn.calibration import CalibratedClassifierCV
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
        except ImportError as exc:
            raise RuntimeError("ML dependencies not installed") from exc

        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        X_train, X_eval, y_train, y_eval = train_test_split(
            X, y, test_size=eval_fraction, shuffle=True, stratify=y
        )

        base = XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            use_label_encoder=False,
            eval_metric="logloss",
            early_stopping_rounds=40,
            random_state=42,
            n_jobs=-1,
        )
        base.fit(
            X_train, y_train,
            eval_set=[(X_eval, y_eval)],
            verbose=False,
        )

        # Isotonic calibration on eval set
        calibrator = CalibratedClassifierCV(base, method="isotonic", cv="prefit")
        calibrator.fit(X_eval, y_eval)

        preds = calibrator.predict_proba(X_eval)[:, 1]
        metrics = {
            "auc":          float(roc_auc_score(y_eval, preds)),
            "brier":        float(brier_score_loss(y_eval, preds)),
            "log_loss":     float(log_loss(y_eval, preds)),
            "n_train":      len(X_train),
            "n_eval":       len(X_eval),
            "best_iteration": int(base.best_iteration),
        }

        joblib.dump(base, MODEL_PATH)
        joblib.dump(calibrator, CALIBRATOR_PATH)
        self._model = base
        self._calibrator = calibrator
        self._loaded = True

        log.info("ML model trained: AUC=%.4f  Brier=%.4f", metrics["auc"], metrics["brier"])
        return metrics


# Global singleton — loaded once at app startup
_ml_model: MLModel | None = None


def get_ml_model() -> MLModel:
    global _ml_model
    if _ml_model is None:
        _ml_model = MLModel()
        _ml_model.load()
    return _ml_model
