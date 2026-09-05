"""
SoilSense AI — ML preprocessing utilities.

Converts SoilFeatures (with string enum values) into the numeric feature
vector expected by the trained ML model.
"""
from __future__ import annotations
import numpy as np
from typing import Tuple

# ─────────────────────────────────────────────────────────────
# Encoding maps (must match data/generate_dataset.py)
# ─────────────────────────────────────────────────────────────

TEXTURE_MAP = {
    "sandy": 0,
    "sandy-loam": 1,
    "loamy": 2,
    "silty": 3,
    "clay-loam": 4,
    "clay": 5,
    "unknown": 2,  # default to loamy (middle ground)
}

DRAINAGE_MAP = {"good": 0, "moderate": 1, "poor": 2, "unknown": 1}
MOISTURE_MAP = {"dry": 0, "moderate": 1, "wet": 2, "unknown": 1}
OM_MAP = {"low": 0, "moderate": 1, "high": 2, "unknown": 1}
COMPACTION_MAP = {"loose": 0, "moderate": 1, "compacted": 2, "unknown": 1}
RETENTION_MAP = {"low": 0, "moderate": 1, "high": 2, "unknown": 1}

COLOR_MAP = {
    "pale": 0, "white": 0, "pale/white": 0, "light": 0, "grey": 0, "gray": 0,
    "yellow": 1, "tan": 1, "yellow/tan": 1, "yellowish": 1,
    "brown": 2,
    "dark brown": 3, "dark": 3,
    "black": 4, "black/dark": 4, "very dark": 4,
    "red": 5, "reddish": 5, "orange": 5, "rust": 5,
    "unknown": 2,  # default brown
}

FEATURE_NAMES = [
    "texture_code",
    "drainage_code",
    "moisture_code",
    "om_code",
    "compaction_code",
    "retention_code",
    "color_code",
]


def color_to_code(color_str: str) -> int:
    """Map a free-text colour string to a numeric code."""
    color_lower = color_str.lower().strip()
    # Exact match first
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]
    # Partial match
    for key, code in COLOR_MAP.items():
        if key in color_lower or color_lower in key:
            return code
    return COLOR_MAP["unknown"]


def features_to_vector(features) -> Tuple[np.ndarray, bool]:
    """
    Convert a SoilFeatures object to a numpy feature vector.

    Returns:
        (feature_vector, has_unknowns) — has_unknowns=True if any core
        field defaulted, which should reduce confidence.
    """
    texture_code = TEXTURE_MAP.get(features.texture, TEXTURE_MAP["unknown"])
    drainage_code = DRAINAGE_MAP.get(features.drainage, DRAINAGE_MAP["unknown"])
    moisture_code = MOISTURE_MAP.get(features.moisture, MOISTURE_MAP["unknown"])
    om_code = OM_MAP.get(features.organic_matter, OM_MAP["unknown"])
    compaction_code = COMPACTION_MAP.get(features.soil_compaction, COMPACTION_MAP["unknown"])
    retention_code = RETENTION_MAP.get(features.water_retention, RETENTION_MAP["unknown"])
    color_code = color_to_code(features.soil_color)

    vector = np.array([
        texture_code,
        drainage_code,
        moisture_code,
        om_code,
        compaction_code,
        retention_code,
        color_code,
    ], dtype=float)

    # Count unknowns in core prediction-relevant fields
    core_unknowns = sum(1 for v in [
        features.texture, features.drainage, features.moisture
    ] if v == "unknown")

    return vector, core_unknowns > 0
