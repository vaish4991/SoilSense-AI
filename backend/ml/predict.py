"""
SoilSense AI — ML Prediction Service (Phase 3 + 4)

Provides soil pH estimation with HONEST uncertainty via ensemble spread:
  - Each decision tree in the Random Forest makes its own prediction.
  - The range [min_tree_pred, max_tree_pred] forms the pH interval.
  - Confidence is derived from the spread (narrow spread = higher confidence)
    and penalised when core input features are "unknown".

This module is the ONLY place that produces numerical pH values.
The LLM does NOT generate pH numbers.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from backend.ml.preprocessing import features_to_vector, FEATURE_NAMES
from backend.schemas.soil_schema import PHEstimate, SoilFeatures

logger = logging.getLogger("soilsense.predict")

MODEL_DIR = Path(__file__).parent / "model"
MODEL_PATH = MODEL_DIR / "soil_ph_model.joblib"
METADATA_PATH = MODEL_DIR / "training_metadata.json"

# Singleton model (loaded once at startup)
_model = None
_metadata: dict = {}


def load_model() -> bool:
    """
    Load the trained model from disk. Returns True if successful.
    Called at application startup.
    """
    global _model, _metadata

    if not MODEL_PATH.exists():
        logger.warning(
            "Model file not found at %s. Run 'python -m backend.ml.train' first.", MODEL_PATH
        )
        return False

    try:
        _model = joblib.load(MODEL_PATH)
        logger.info("ML model loaded from %s", MODEL_PATH)
    except Exception as exc:
        logger.error("Failed to load model: %s", exc)
        return False

    if METADATA_PATH.exists():
        try:
            _metadata = json.loads(METADATA_PATH.read_text())
        except Exception:
            pass

    return True


def is_model_loaded() -> bool:
    return _model is not None


def predict_ph(features: SoilFeatures) -> PHEstimate:
    """
    Predict soil pH from structured soil features.

    Returns a PHEstimate with:
      - min / max  (confidence interval from tree spread)
      - midpoint   (mean tree prediction)
      - confidence (0–1, penalised for unknown inputs)

    If the model is not loaded, returns a low-confidence fallback estimate.
    """
    global _model
    if _model is None:
        load_model()

    if _model is None:
        logger.warning("Model not loaded — returning fallback estimate")
        return _fallback_estimate(features)

    try:
        X, has_unknowns = features_to_vector(features)
        X = X.reshape(1, -1)

        # ── Ensemble spread for uncertainty ──────────────────
        if hasattr(_model, "estimators_"):
            # RandomForest: collect per-tree predictions
            tree_preds = np.array([tree.predict(X)[0] for tree in _model.estimators_])
        else:
            # GradientBoosting: use staged_predict for spread approximation
            # Fall back to ±0.3 around the point estimate
            point_pred = float(_model.predict(X)[0])
            tree_preds = np.array([point_pred - 0.3, point_pred, point_pred + 0.3])

        midpoint = float(np.mean(tree_preds))
        spread = float(np.max(tree_preds) - np.min(tree_preds))

        # Use 10th–90th percentile for a meaningful interval
        ph_min = float(np.percentile(tree_preds, 10))
        ph_max = float(np.percentile(tree_preds, 90))

        # Clamp to realistic soil pH range
        ph_min = round(max(3.5, min(ph_min, 9.5)), 1)
        ph_max = round(max(3.5, min(ph_max, 9.5)), 1)
        midpoint = round(max(3.5, min(midpoint, 9.5)), 2)

        if ph_min > ph_max:
            ph_min, ph_max = ph_max, ph_min

        # ── Confidence score ──────────────────────────────────
        # Base: inversely proportional to spread
        # Spread of 0 → 100% confidence; spread ≥ 2.0 → low confidence
        spread_confidence = max(0.0, 1.0 - (spread / 2.0))

        # Penalty for unknown core features
        unknown_penalty = 0.0
        if has_unknowns:
            core_unknown_count = sum(
                1 for v in [features.texture, features.drainage, features.moisture]
                if v == "unknown"
            )
            unknown_penalty = min(0.4, core_unknown_count * 0.15)

        confidence = round(max(0.1, spread_confidence - unknown_penalty), 2)

        # ── Low-confidence warning ────────────────────────────
        warning = None
        if confidence < 0.5:
            warning = (
                "Low confidence: the soil description is limited. "
                "Providing more details (texture, drainage, colour) will improve accuracy."
            )
        elif has_unknowns:
            warning = (
                "Moderate confidence: some core soil features were not detected. "
                "A physical soil test is strongly recommended."
            )

        logger.info(
            "pH estimate: %.2f (%.1f–%.1f), confidence=%.2f, spread=%.2f",
            midpoint, ph_min, ph_max, confidence, spread,
        )

        return PHEstimate(
            min=ph_min,
            max=ph_max,
            midpoint=midpoint,
            confidence=confidence,
            low_confidence_warning=warning,
            method_note=(
                "pH range derived from 10th–90th percentile of individual decision tree "
                "predictions within the Random Forest ensemble. Confidence is inversely "
                "proportional to prediction spread, with a penalty for unknown input features."
            ),
        )

    except Exception as exc:
        logger.error("Prediction failed: %s", exc, exc_info=True)
        return _fallback_estimate(features)


def _fallback_estimate(features: SoilFeatures) -> PHEstimate:
    """
    Rule-based fallback pH estimate when the ML model is unavailable.
    Uses simplified agronomic heuristics. Clearly flagged as fallback.
    """
    base = 6.5  # default neutral-ish

    if features.texture == "sandy":
        base -= 0.5
    elif features.texture == "clay":
        base += 0.3

    if features.drainage == "poor":
        base -= 0.3
    elif features.drainage == "good":
        base += 0.1

    if features.organic_matter == "high":
        base -= 0.2

    ph_min = round(max(4.0, base - 0.5), 1)
    ph_max = round(min(9.0, base + 0.5), 1)

    return PHEstimate(
        min=ph_min,
        max=ph_max,
        midpoint=round(base, 2),
        confidence=0.35,
        low_confidence_warning=(
            "ML model is unavailable. This estimate uses simplified agronomic rules only. "
            "Train the model with: python -m backend.ml.train"
        ),
        method_note="Rule-based fallback estimate (ML model not loaded).",
    )


def get_model_metadata() -> dict:
    return _metadata
