"""
SoilSense AI — ML Training Script

Trains a Random Forest Regressor on the soil dataset and saves:
  - backend/ml/model/soil_ph_model.joblib  (trained model)
  - backend/ml/model/training_metadata.json (metrics + feature importances)

Usage:
  python -m backend.ml.train

Evaluation metrics reported:
  - MAE  (Mean Absolute Error)
  - RMSE (Root Mean Squared Error)
  - R²   (Coefficient of Determination)

NOTE: This script uses the synthetic dataset by default. Replace
data/soil_dataset.csv with a real dataset that has the same schema
to improve real-world accuracy.
"""
from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("soilsense.train")

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "soil_dataset.csv"
MODEL_DIR = Path(__file__).parent / "model"
MODEL_PATH = MODEL_DIR / "soil_ph_model.joblib"
METADATA_PATH = MODEL_DIR / "training_metadata.json"

FEATURE_COLS = [
    "texture_code",
    "drainage_code",
    "moisture_code",
    "om_code",
    "compaction_code",
    "retention_code",
    "color_code",
]
TARGET_COL = "ph"


def load_or_generate_data() -> pd.DataFrame:
    if DATA_PATH.exists():
        logger.info("Loading dataset from %s", DATA_PATH)
        return pd.read_csv(DATA_PATH)

    logger.warning(
        "Dataset not found at %s. Generating synthetic dataset…", DATA_PATH
    )
    # Generate on the fly
    sys.path.insert(0, str(ROOT))
    from data.generate_dataset import generate_dataset
    df = generate_dataset(2000)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    logger.info("Synthetic dataset generated and saved.")
    return df


def train() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = load_or_generate_data()
    logger.info("Dataset shape: %s", df.shape)

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # ── Candidate models ──────────────────────────────────────
    candidates = {
        "RandomForest": RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=5,
            random_state=42,
        ),
    }

    best_model = None
    best_name = ""
    best_mae = float("inf")
    model_metrics = {}

    for name, model in candidates.items():
        logger.info("Training %s…", name)
        cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="neg_mean_absolute_error")
        cv_mae = -cv_scores.mean()
        logger.info("  CV MAE: %.4f ± %.4f", cv_mae, cv_scores.std())

        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        r2 = r2_score(y_test, preds)

        logger.info("  Test MAE=%.4f  RMSE=%.4f  R²=%.4f", mae, rmse, r2)
        model_metrics[name] = {"mae": mae, "rmse": rmse, "r2": r2}

        if mae < best_mae:
            best_mae = mae
            best_model = model
            best_name = name

    logger.info("Best model: %s (MAE=%.4f)", best_name, best_mae)

    # ── Save model ────────────────────────────────────────────
    joblib.dump(best_model, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)

    # ── Feature importances ───────────────────────────────────
    if hasattr(best_model, "feature_importances_"):
        importances = dict(zip(FEATURE_COLS, best_model.feature_importances_.tolist()))
    else:
        importances = {}

    # ── Save metadata ─────────────────────────────────────────
    metadata = {
        "model_name": best_name,
        "feature_columns": FEATURE_COLS,
        "dataset_rows": len(df),
        "dataset_source": "Synthetic (agronomic rules). See data/generate_dataset.py for methodology.",
        "metrics": model_metrics,
        "best_model_metrics": model_metrics[best_name],
        "feature_importances": importances,
        "training_note": (
            "This model was trained on a synthetic dataset. Accuracy on real-world soils "
            "may differ. Replace data/soil_dataset.csv with measured field data for production use."
        ),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2))
    logger.info("Metadata saved to %s", METADATA_PATH)
    logger.info("Training complete.")


if __name__ == "__main__":
    train()
