"""
SoilSense AI — ML Preprocessing Pipeline

Converts raw soil data and SoilFeatures (from natural language) into the
preprocessed feature matrix required by regression models.

Strict ML Standards:
  - ColumnTransformer combines One-Hot Encoding for categorical levels and
    standardized ordinal features.
  - Preprocessor is fitted strictly on training data to prevent data leakage.
  - Robust handling for missing values, unseen categories, and "unknown" inputs.
"""
from __future__ import annotations
from typing import Tuple, List, Dict, Any
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Canonical categorical feature names
CATEGORICAL_COLS = [
    "texture",
    "drainage",
    "moisture",
    "organic_matter",
    "soil_compaction",
    "water_retention",
    "soil_color",
]

# Core features for uncertainty / missingness assessment
CORE_FEATURES = [
    "texture",
    "drainage",
    "moisture",
    "organic_matter",
    "soil_color",
]

# Mappings from discrete text to ordinal / numeric values
TEXTURE_MAP: Dict[str, int] = {
    "sandy": 0,
    "sandy-loam": 1,
    "loamy": 2,
    "silty": 3,
    "clay-loam": 4,
    "clay": 5,
    "unknown": 2,
}

DRAINAGE_MAP: Dict[str, int] = {
    "good": 0,
    "moderate": 1,
    "poor": 2,
    "unknown": 1,
}

MOISTURE_MAP: Dict[str, int] = {
    "dry": 0,
    "moderate": 1,
    "wet": 2,
    "unknown": 1,
}

OM_MAP: Dict[str, int] = {
    "low": 0,
    "moderate": 1,
    "high": 2,
    "unknown": 1,
}

COMPACTION_MAP: Dict[str, int] = {
    "loose": 0,
    "moderate": 1,
    "compacted": 2,
    "unknown": 1,
}

RETENTION_MAP: Dict[str, int] = {
    "low": 0,
    "moderate": 1,
    "high": 2,
    "unknown": 1,
}

COLOR_MAP: Dict[str, int] = {
    "pale": 0, "white": 0, "pale/white": 0, "light": 0, "grey": 0, "gray": 0,
    "yellow": 1, "tan": 1, "yellow/tan": 1, "yellowish": 1,
    "brown": 2,
    "dark brown": 3, "dark": 3,
    "black": 4, "black/dark": 4, "very dark": 4,
    "red": 5, "reddish": 5, "orange": 5, "rust": 5,
    "unknown": 2,
}

ORDINAL_COLS = [c + "_ord" for c in CATEGORICAL_COLS]
ALL_INPUT_COLS = CATEGORICAL_COLS + ORDINAL_COLS


def color_to_code(color_str: Any) -> int:
    """Map a free-text colour string to a numeric code."""
    if not color_str or pd.isna(color_str):
        return COLOR_MAP["unknown"]
    color_lower = str(color_str).lower().strip()
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]
    for key, code in COLOR_MAP.items():
        if key in color_lower or color_lower in key:
            return code
    return COLOR_MAP["unknown"]


def prepare_feature_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure all categorical and ordinal columns are present, cleaned, and typed.
    Handles missing values and invalid strings safely.
    """
    out = pd.DataFrame(index=df.index)

    # 1. Clean categorical columns
    for col in CATEGORICAL_COLS:
        if col in df.columns:
            out[col] = df[col].fillna("unknown").astype(str).str.lower().str.strip()
        else:
            out[col] = "unknown"

    # 2. Add ordinal representations
    out["texture_ord"] = out["texture"].map(lambda v: TEXTURE_MAP.get(v, TEXTURE_MAP["unknown"]))
    out["drainage_ord"] = out["drainage"].map(lambda v: DRAINAGE_MAP.get(v, DRAINAGE_MAP["unknown"]))
    out["moisture_ord"] = out["moisture"].map(lambda v: MOISTURE_MAP.get(v, MOISTURE_MAP["unknown"]))
    out["organic_matter_ord"] = out["organic_matter"].map(lambda v: OM_MAP.get(v, OM_MAP["unknown"]))
    out["soil_compaction_ord"] = out["soil_compaction"].map(lambda v: COMPACTION_MAP.get(v, COMPACTION_MAP["unknown"]))
    out["water_retention_ord"] = out["water_retention"].map(lambda v: RETENTION_MAP.get(v, RETENTION_MAP["unknown"]))
    out["soil_color_ord"] = out["soil_color"].apply(color_to_code)

    return out[ALL_INPUT_COLS]


def build_preprocessor() -> ColumnTransformer:
    """
    Construct a scikit-learn ColumnTransformer that encodes:
      - Categorical features via OneHotEncoder (ignoring unseen categories)
      - Ordinal/numeric features via StandardScaler
    """
    return ColumnTransformer(
        transformers=[
            (
                "ohe",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_COLS,
            ),
            (
                "scale",
                StandardScaler(),
                ORDINAL_COLS,
            ),
        ],
        remainder="drop",
    )


def count_unknown_core_features(features: Any) -> int:
    """
    Count how many core features are 'unknown' or unobserved.
    Core features: texture, drainage, moisture, organic_matter, soil_color.
    """
    unknowns = 0
    if getattr(features, "texture", "unknown") in ("unknown", "", None):
        unknowns += 1
    if getattr(features, "drainage", "unknown") in ("unknown", "", None):
        unknowns += 1
    if getattr(features, "moisture", "unknown") in ("unknown", "", None):
        unknowns += 1
    if getattr(features, "organic_matter", "unknown") in ("unknown", "", None):
        unknowns += 1
    c = str(getattr(features, "soil_color", "unknown")).lower().strip()
    if c in ("unknown", "", "none"):
        unknowns += 1
    return unknowns


def features_to_dataframe(features: Any) -> pd.DataFrame:
    """Convert a SoilFeatures object to a single-row DataFrame ready for prediction."""
    raw_dict = {
        "texture": getattr(features, "texture", "unknown"),
        "drainage": getattr(features, "drainage", "unknown"),
        "moisture": getattr(features, "moisture", "unknown"),
        "organic_matter": getattr(features, "organic_matter", "unknown"),
        "soil_compaction": getattr(features, "soil_compaction", "unknown"),
        "water_retention": getattr(features, "water_retention", "unknown"),
        "soil_color": getattr(features, "soil_color", "unknown"),
    }
    df = pd.DataFrame([raw_dict])
    return prepare_feature_dataframe(df)


def features_to_vector(features: Any) -> Tuple[np.ndarray, bool]:
    """
    Backwards-compatible helper returning a numeric array and unknown flag.
    """
    df = features_to_dataframe(features)
    unknown_count = count_unknown_core_features(features)
    return df[ORDINAL_COLS].values[0], unknown_count > 0
