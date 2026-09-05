"""
SoilSense AI — ML Prediction Service

Provides calibrated soil pH estimation with HONEST uncertainty using Split
Conformal Prediction intervals trained on real USDA NRCS SSURGO laboratory data.

Guiding Principles:
  - Point prediction comes from the validated regression model (Random Forest).
  - Prediction interval [lower_bound, upper_bound] uses calibrated conformal margins
    scaled by local ensemble variance and missing input penalties.
  - Confidence is returned as both a calibrated float (0–1) and a discrete level:
    'High' / 'Medium' / 'Low'.
  - Confidence STRICTLY decreases when inputs are missing, sparse, or ambiguous.
  - No artificial inflation: honest uncertainty calibrated on 6,000 real soil samples.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional, Any

import joblib
import numpy as np
import pandas as pd

from backend.ml.preprocessing import (
    features_to_dataframe,
    count_unknown_core_features,
    ALL_INPUT_COLS,
)
from backend.schemas.soil_schema import PHEstimate, SoilFeatures

logger = logging.getLogger("soilsense.predict")

MODEL_DIR = Path(__file__).parent / "model"
MODEL_PATH = MODEL_DIR / "soil_ph_model.joblib"
METADATA_PATH = MODEL_DIR / "training_metadata.json"

# Global model state
_pipeline = None
_conformal_q: float = 0.6644
_median_spread: float = 0.0655
_metadata: dict = {}


def load_model() -> bool:
    """
    Load the trained model pipeline bundle and conformal calibration params from disk.
    Returns True if successful.
    """
    global _pipeline, _conformal_q, _median_spread, _metadata

    if not MODEL_PATH.exists():
        logger.warning(
            "Model file not found at %s. Run 'python -m backend.ml.train' first.", MODEL_PATH
        )
        return False

    try:
        loaded = joblib.load(MODEL_PATH)
        if isinstance(loaded, dict) and "pipeline" in loaded:
            _pipeline = loaded["pipeline"]
            _conformal_q = float(loaded.get("conformal_q", 0.6644))
            _median_spread = float(loaded.get("median_tree_spread", 0.0655))
            logger.info(
                "Loaded ML pipeline bundle (%s) with conformal margin q=%.4f",
                loaded.get("model_name", "Unknown"), _conformal_q
            )
        else:
            _pipeline = loaded
            _conformal_q = 0.6644
            _median_spread = 0.0655
            logger.info("Loaded legacy ML model from %s", MODEL_PATH)
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
    return _pipeline is not None


def predict_ph(features: SoilFeatures) -> PHEstimate:
    """
    Predict soil pH from structured soil features.

    Returns a PHEstimate with:
      - estimated_ph / midpoint: point pH prediction
      - lower_bound / min: calibrated lower bound
      - upper_bound / max: calibrated upper bound
      - confidence: continuous confidence 0.10–0.92
      - confidence_level: 'High' / 'Medium' / 'Low'
    """
    global _pipeline, _conformal_q, _median_spread
    if _pipeline is None:
        load_model()

    if _pipeline is None:
        logger.warning("Model not loaded — returning fallback estimate")
        return _fallback_estimate(features)

    try:
        df_input = features_to_dataframe(features)
        n_unknowns = count_unknown_core_features(features)

        # 1. Point prediction
        point_pred = float(_pipeline.predict(df_input)[0])

        # 2. Ensemble spread
        reg = _pipeline.named_steps.get("reg")
        prep = _pipeline.named_steps.get("prep")

        if hasattr(reg, "estimators_") and prep is not None:
            X_trans = prep.transform(df_input)
            tree_preds = np.array([tree.predict(X_trans)[0] for tree in reg.estimators_])
            tree_spread = float(np.std(tree_preds))
        else:
            tree_spread = _median_spread

        # 3. Calibrated Conformal Margin with local variance & missingness scaling
        spread_ratio = tree_spread / max(0.01, _median_spread)
        # Bounded spread adjustment
        variance_factor = 0.80 + 0.20 * min(2.5, max(0.5, spread_ratio))
        missing_factor = 1.0 + (0.12 * n_unknowns)

        margin = _conformal_q * variance_factor * missing_factor
        margin = max(0.40, min(1.80, margin))

        # 4. Compute bounds clamped to realistic natural soil pH [3.5, 9.5]
        lower_bound = round(max(3.5, point_pred - margin), 1)
        upper_bound = round(min(9.5, point_pred + margin), 1)
        estimated_ph = round(max(3.5, min(9.5, point_pred)), 2)

        if lower_bound > upper_bound:
            lower_bound, upper_bound = upper_bound, lower_bound

        interval_width = round(upper_bound - lower_bound, 1)

        # 5. Continuous Confidence Score (Honest & Input-Penalized)
        base_confidence = max(0.15, 1.0 - (margin / 1.5))
        confidence_penalty = 0.12 * n_unknowns
        confidence = round(max(0.10, min(0.92, base_confidence - confidence_penalty)), 2)

        # 6. Qualitative Confidence Level
        if confidence >= 0.65 and n_unknowns <= 1 and interval_width <= 1.2:
            confidence_level = "High"
        elif confidence >= 0.40 and n_unknowns <= 2 and interval_width <= 1.7:
            confidence_level = "Medium"
        else:
            confidence_level = "Low"

        # 7. Informative warnings
        warning = None
        if confidence_level == "Low" or n_unknowns >= 3:
            warning = (
                "Low confidence: Several core soil characteristics (texture, drainage, color) "
                "were not detected. Providing more details will narrow the prediction interval."
            )
        elif confidence_level == "Medium" or n_unknowns > 0:
            warning = (
                "Moderate confidence: Some features were inferred. A physical soil test is "
                "strongly recommended before major soil amendments."
            )

        logger.info(
            "pH prediction: %.2f [%.1f–%.1f] (width=%.1f), confidence=%.2f (%s), unknowns=%d",
            estimated_ph, lower_bound, upper_bound, interval_width, confidence, confidence_level, n_unknowns
        )

        return PHEstimate(
            estimated_ph=estimated_ph,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence_level=confidence_level,
            min=lower_bound,
            max=upper_bound,
            midpoint=estimated_ph,
            confidence=confidence,
            low_confidence_warning=warning,
            method_note=(
                f"Trained on real USDA NRCS SSURGO laboratory measurements. Prediction interval "
                f"derived from Split Conformal Prediction (85% nominal coverage) scaled by "
                f"local ensemble spread and penalized for missing input features."
            ),
        )

    except Exception as exc:
        logger.error("Prediction failed: %s", exc, exc_info=True)
        return _fallback_estimate(features)


def _fallback_estimate(features: SoilFeatures) -> PHEstimate:
    """Rule-based fallback pH estimate when the ML model is unavailable."""
    base = 6.5
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

    low = round(max(3.5, base - 0.7), 1)
    high = round(min(9.5, base + 0.7), 1)
    est = round(base, 2)

    return PHEstimate(
        estimated_ph=est,
        lower_bound=low,
        upper_bound=high,
        confidence_level="Low",
        min=low,
        max=high,
        midpoint=est,
        confidence=0.30,
        low_confidence_warning=(
            "ML model is unavailable. This estimate uses simplified rule heuristics only. "
            "Run 'python -m backend.ml.train' to initialize the real USDA model."
        ),
        method_note="Rule-based fallback estimate (ML model not loaded).",
    )


def get_model_metadata() -> dict:
    return _metadata
