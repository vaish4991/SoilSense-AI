"""
SoilSense AI — ML Training & Model Selection Pipeline

Upgrades the pH estimation model using real-world USDA NRCS SSURGO laboratory
measurements with rigorous standards:
  1. Authoritative real-world soil dataset with actual measured pH.
  2. Prevention of data leakage via Group-based splitting on soil profile ID (`cokey`).
  3. Preprocessing with ColumnTransformer (OneHotEncoder + StandardScaler).
  4. Multi-model evaluation (Random Forest, Gradient Boosting, Extra Trees, Ridge).
  5. Automatic selection of the best model based on 5-fold GroupKFold cross-validation.
  6. Fixed random seeds for complete reproducibility.
  7. Split Conformal Prediction for calibrated prediction intervals and honest uncertainty.
  8. Saving of trained pipeline bundle and comprehensive training metadata.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    RandomForestRegressor,
    GradientBoostingRegressor,
    ExtraTreesRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_validate
from sklearn.pipeline import Pipeline

from backend.ml.preprocessing import (
    CATEGORICAL_COLS,
    ALL_INPUT_COLS,
    build_preprocessor,
    prepare_feature_dataframe,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("soilsense.train")

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "soil_dataset.csv"
MODEL_DIR = Path(__file__).parent / "model"
MODEL_PATH = MODEL_DIR / "soil_ph_model.joblib"
METADATA_PATH = MODEL_DIR / "training_metadata.json"

RANDOM_SEED = 42
TARGET_COL = "ph"
GROUP_COL = "cokey"
CONFORMAL_CONFIDENCE_LEVEL = 0.85  # 85% nominal coverage


def load_dataset() -> pd.DataFrame:
    """Load the real USDA soil dataset, fetching it if not present."""
    if DATA_PATH.exists():
        logger.info("Loading real soil dataset from %s", DATA_PATH)
        df = pd.read_csv(DATA_PATH)
        if len(df) >= 500 and "cokey" in df.columns and "ph" in df.columns:
            return df
        logger.warning("Existing dataset file incomplete or invalid schema. Re-fetching real USDA data...")

    logger.info("Fetching real measured soil data from USDA NRCS Soil Data Access API...")
    from data.fetch_usda_data import fetch_usda_soil_data
    return fetch_usda_soil_data(sample_limit=6000)


def split_data_without_leakage(
    df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Split data into Train (70%), Calibration (15%), and Test (15%)
    strictly grouped by `cokey` to guarantee zero data leakage between
    soil profiles across splits.
    """
    X_raw = prepare_feature_dataframe(df)
    y = df[TARGET_COL].astype(float)
    groups = df[GROUP_COL].astype(str)

    # 1. Train (70%) vs Temp (30%)
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=RANDOM_SEED)
    train_idx, temp_idx = next(gss1.split(X_raw, y, groups=groups))

    X_train = X_raw.iloc[train_idx].copy()
    y_train = y.iloc[train_idx].copy()

    X_temp = X_raw.iloc[temp_idx].copy()
    y_temp = y.iloc[temp_idx].copy()
    groups_temp = groups.iloc[temp_idx].copy()

    # 2. Calibration (15%) vs Test (15%)
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=RANDOM_SEED)
    cal_idx, test_idx = next(gss2.split(X_temp, y_temp, groups=groups_temp))

    X_cal = X_temp.iloc[cal_idx].copy()
    y_cal = y_temp.iloc[cal_idx].copy()

    X_test = X_temp.iloc[test_idx].copy()
    y_test = y_temp.iloc[test_idx].copy()

    # Assert zero group leakage
    train_groups = set(groups.iloc[train_idx])
    cal_groups = set(groups_temp.iloc[cal_idx])
    test_groups = set(groups_temp.iloc[test_idx])

    assert len(train_groups & cal_groups) == 0, "Data leakage detected between Train and Calibration!"
    assert len(train_groups & test_groups) == 0, "Data leakage detected between Train and Test!"
    assert len(cal_groups & test_groups) == 0, "Data leakage detected between Calibration and Test!"

    logger.info(
        "Data split (zero leakage): Train=%d, Calibration=%d, Test=%d (Unique Profiles: %d)",
        len(X_train), len(X_cal), len(X_test), len(set(groups))
    )
    return X_train, y_train, X_cal, y_cal, X_test, y_test


def evaluate_candidate_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups_train: pd.Series,
) -> Tuple[str, Any, Dict[str, Dict[str, float]]]:
    """
    Compare multiple regression models using 5-Fold GroupKFold cross-validation.
    Returns (best_model_name, best_model_instance, cv_results_dict).
    """
    candidates = {
        "RandomForest": RandomForestRegressor(
            n_estimators=150,
            max_depth=10,
            min_samples_leaf=4,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=4,
            random_state=RANDOM_SEED,
        ),
        "ExtraTrees": ExtraTreesRegressor(
            n_estimators=150,
            max_depth=10,
            min_samples_leaf=4,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "Ridge": Ridge(
            alpha=1.0,
            random_state=RANDOM_SEED,
        ),
    }

    gkf = GroupKFold(n_splits=5)
    cv_summary: Dict[str, Dict[str, float]] = {}
    best_name = ""
    best_mae = float("inf")
    best_model = None

    logger.info("--- Starting 5-Fold Group Cross-Validation on Candidate Models ---")

    for name, regressor in candidates.items():
        pipe = Pipeline([
            ("prep", build_preprocessor()),
            ("reg", regressor),
        ])

        cv_res = cross_validate(
            pipe,
            X_train,
            y_train,
            groups=groups_train,
            cv=gkf,
            scoring=["neg_mean_absolute_error", "neg_root_mean_squared_error", "r2"],
            n_jobs=-1,
        )

        mae_scores = -cv_res["test_neg_mean_absolute_error"]
        rmse_scores = -cv_res["test_neg_root_mean_squared_error"]
        r2_scores = cv_res["test_r2"]

        cv_summary[name] = {
            "cv_mae_mean": round(float(mae_scores.mean()), 4),
            "cv_mae_std": round(float(mae_scores.std()), 4),
            "cv_rmse_mean": round(float(rmse_scores.mean()), 4),
            "cv_rmse_std": round(float(rmse_scores.std()), 4),
            "cv_r2_mean": round(float(r2_scores.mean()), 4),
            "cv_r2_std": round(float(r2_scores.std()), 4),
        }

        logger.info(
            "[%s] CV MAE: %.4f ± %.4f | RMSE: %.4f ± %.4f | R²: %.4f ± %.4f",
            name,
            cv_summary[name]["cv_mae_mean"], cv_summary[name]["cv_mae_std"],
            cv_summary[name]["cv_rmse_mean"], cv_summary[name]["cv_rmse_std"],
            cv_summary[name]["cv_r2_mean"], cv_summary[name]["cv_r2_std"],
        )

        if cv_summary[name]["cv_mae_mean"] < best_mae:
            best_mae = cv_summary[name]["cv_mae_mean"]
            best_name = name
            best_model = regressor

    logger.info("Best model selected: %s (CV MAE: %.4f)", best_name, best_mae)
    return best_name, best_model, cv_summary


def calibrate_conformal_interval(
    pipeline: Pipeline,
    X_cal: pd.DataFrame,
    y_cal: pd.Series,
    alpha: float = 1.0 - CONFORMAL_CONFIDENCE_LEVEL,
) -> Tuple[float, float]:
    """
    Perform Split Conformal Prediction calibration on held-out calibration set.
    Returns:
      (conformal_q, median_tree_spread)
    """
    cal_preds = pipeline.predict(X_cal)
    residuals = np.abs(y_cal.values - cal_preds)

    n_cal = len(residuals)
    # Finite sample correction quantile level
    q_level = min(1.0, np.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal)
    conformal_q = float(np.quantile(residuals, q_level))

    # Calculate median ensemble tree spread if available
    reg = pipeline.named_steps["reg"]
    if hasattr(reg, "estimators_"):
        X_trans = pipeline.named_steps["prep"].transform(X_cal)
        tree_preds = np.array([tree.predict(X_trans) for tree in reg.estimators_])
        spreads = np.std(tree_preds, axis=0)
        median_spread = float(np.median(spreads))
    else:
        median_spread = 0.25

    logger.info(
        "Conformal calibration: margin q_hat=%.4f (target coverage=%.1f%%, n_cal=%d, median_spread=%.4f)",
        conformal_q, (1.0 - alpha) * 100, n_cal, median_spread
    )
    return round(conformal_q, 4), round(median_spread, 4)


def evaluate_on_test_set(
    pipeline: Pipeline,
    conformal_q: float,
    median_spread: float,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Dict[str, float]:
    """Evaluate point accuracy and conformal coverage on independent test set."""
    test_preds = pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, test_preds)
    rmse = np.sqrt(mean_squared_error(y_test, test_preds))
    r2 = r2_score(y_test, test_preds)

    lower_bounds = test_preds - conformal_q
    upper_bounds = test_preds + conformal_q
    coverage = np.mean((y_test.values >= lower_bounds) & (y_test.values <= upper_bounds))
    avg_width = float(np.mean(upper_bounds - lower_bounds))

    test_metrics = {
        "test_mae": round(float(mae), 4),
        "test_rmse": round(float(rmse), 4),
        "test_r2": round(float(r2), 4),
        "test_coverage": round(float(coverage * 100), 2),
        "avg_interval_width": round(avg_width, 2),
    }

    logger.info(
        "Test Set Evaluation | MAE: %.4f | RMSE: %.4f | R²: %.4f | Empirical Coverage: %.2f%% | Avg Width: %.2f",
        test_metrics["test_mae"], test_metrics["test_rmse"], test_metrics["test_r2"],
        test_metrics["test_coverage"], test_metrics["avg_interval_width"]
    )
    return test_metrics


def train() -> Dict[str, Any]:
    """Execute the full ML pipeline and persist artifacts."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = load_dataset()
    logger.info("Loaded real soil dataset with %d samples and %d unique soil profiles.", len(df), df["cokey"].nunique())

    X_train, y_train, X_cal, y_cal, X_test, y_test = split_data_without_leakage(df)
    groups_train = df.loc[X_train.index, GROUP_COL]

    # Model comparison & selection
    best_name, best_regressor, cv_summary = evaluate_candidate_models(X_train, y_train, groups_train)

    # Fit final pipeline on training set
    preprocessor = build_preprocessor()
    final_pipeline = Pipeline([
        ("prep", preprocessor),
        ("reg", best_regressor),
    ])
    final_pipeline.fit(X_train, y_train)

    # Conformal calibration
    conformal_q, median_spread = calibrate_conformal_interval(final_pipeline, X_cal, y_cal)

    # Test set evaluation
    test_metrics = evaluate_on_test_set(final_pipeline, conformal_q, median_spread, X_test, y_test)

    # Extract feature importances if tree model
    reg = final_pipeline.named_steps["reg"]
    if hasattr(reg, "feature_importances_"):
        ohe_cols = list(final_pipeline.named_steps["prep"].named_transformers_["ohe"].get_feature_names_out(CATEGORICAL_COLS))
        ord_cols = [c + "_ord" for c in CATEGORICAL_COLS]
        all_trans_cols = ohe_cols + ord_cols
        raw_importances = reg.feature_importances_.tolist()
        importances = dict(zip(all_trans_cols, [round(float(v), 5) for v in raw_importances]))
        # Top 10 features
        top_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True)[:10])
    else:
        top_importances = {}

    # Save model pipeline bundle
    bundle = {
        "pipeline": final_pipeline,
        "model_name": best_name,
        "conformal_q": conformal_q,
        "median_tree_spread": median_spread,
        "nominal_coverage": CONFORMAL_CONFIDENCE_LEVEL,
        "feature_columns": ALL_INPUT_COLS,
        "dataset_rows": len(df),
        "unique_profiles": int(df["cokey"].nunique()),
    }
    joblib.dump(bundle, MODEL_PATH)
    logger.info("Saved trained ML bundle to %s", MODEL_PATH)

    # Save comprehensive training metadata
    metadata = {
        "model_name": best_name,
        "dataset_source": "USDA NRCS Soil Data Access (SSURGO Database)",
        "dataset_rows": len(df),
        "unique_profiles": int(df["cokey"].nunique()),
        "target_variable": "ph1to1h2o_r (standard measured 1:1 soil:water pH)",
        "split_method": "GroupShuffleSplit on cokey (zero profile/location leakage)",
        "train_samples": len(X_train),
        "calibration_samples": len(X_cal),
        "test_samples": len(X_test),
        "cross_validation": {
            "folds": 5,
            "method": "GroupKFold on cokey",
            "results_by_model": cv_summary,
        },
        "best_model_metrics": cv_summary[best_name],
        "test_metrics": test_metrics,
        "uncertainty_method": "Split Conformal Prediction (inductive nonconformity quantiles)",
        "conformal_q": conformal_q,
        "nominal_coverage": CONFORMAL_CONFIDENCE_LEVEL,
        "top_feature_importances": top_importances,
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2))
    logger.info("Saved metadata to %s", METADATA_PATH)

    return metadata


if __name__ == "__main__":
    train()
