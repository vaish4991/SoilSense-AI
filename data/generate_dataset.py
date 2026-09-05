"""
SoilSense AI — Synthetic Soil Dataset Generator

IMPORTANT NOTE ON DATA:
This dataset is SYNTHETIC, procedurally generated using agronomic rules
from published soil science literature. It is NOT measured field data.

References:
  - Brady & Weil, "The Nature and Properties of Soils", 15th ed.
  - FAO Soil Portal: https://www.fao.org/soils-portal
  - USDA NRCS Web Soil Survey: https://websoilsurvey.nrcs.usda.gov

The dataset is designed for demonstration purposes in the SoilSense AI MVP.
Replace this with a real dataset (e.g., USDA NRCS, ISCN, SoilGrids) before
making production agricultural decisions.

Schema:
  texture_code, drainage_code, moisture_code, organic_matter_code,
  compaction_code, water_retention_code, color_darkness, ph
"""
import numpy as np
import pandas as pd
from pathlib import Path

# Seed for reproducibility
RNG = np.random.default_rng(42)

# Encoding maps (feature → numeric code)
TEXTURE_MAP = {
    "sandy": 0,
    "sandy-loam": 1,
    "loamy": 2,
    "silty": 3,
    "clay-loam": 4,
    "clay": 5,
}
DRAINAGE_MAP = {"good": 0, "moderate": 1, "poor": 2}
MOISTURE_MAP = {"dry": 0, "moderate": 1, "wet": 2}
OM_MAP = {"low": 0, "moderate": 1, "high": 2}
COMPACTION_MAP = {"loose": 0, "moderate": 1, "compacted": 2}
RETENTION_MAP = {"low": 0, "moderate": 1, "high": 2}
COLOR_MAP = {"pale/white": 0, "yellow/tan": 1, "brown": 2, "dark brown": 3, "black/dark": 4, "red": 5}


def generate_dataset(n_samples: int = 2000) -> pd.DataFrame:
    """
    Generate a synthetic soil dataset with agronomically-grounded pH values.

    pH determination logic (simplified from soil science principles):
      - Sandy soils: tend toward lower pH (acidic leaching)
      - Clay soils: variable, often neutral to slightly alkaline
      - Dark/organic soils: slightly acidic to neutral
      - Poor drainage: can indicate water-logging → slightly acidic
      - White surface deposits: often alkaline soils (calcium carbonate)
    """
    records = []

    textures = list(TEXTURE_MAP.keys())
    drainages = list(DRAINAGE_MAP.keys())
    moistures = list(MOISTURE_MAP.keys())
    om_levels = list(OM_MAP.keys())
    compactions = list(COMPACTION_MAP.keys())
    retentions = list(RETENTION_MAP.keys())
    colors = list(COLOR_MAP.keys())

    # pH base values by texture (from literature)
    texture_ph_base = {
        "sandy": 6.0,
        "sandy-loam": 6.2,
        "loamy": 6.5,
        "silty": 6.6,
        "clay-loam": 6.7,
        "clay": 7.0,
    }

    for _ in range(n_samples):
        texture = RNG.choice(textures)
        drainage = RNG.choice(drainages)
        moisture = RNG.choice(moistures)
        om = RNG.choice(om_levels)
        compaction = RNG.choice(compactions)
        retention = RNG.choice(retentions)
        color = RNG.choice(colors)

        # Start with texture-based pH
        ph = texture_ph_base[texture]

        # Drainage effects
        if drainage == "poor":
            ph -= RNG.uniform(0.1, 0.4)  # waterlogging → slightly acidic
        elif drainage == "good":
            ph += RNG.uniform(0.0, 0.2)

        # Organic matter effects
        if om == "high":
            ph -= RNG.uniform(0.1, 0.3)  # decomposing OM releases acids
        elif om == "low":
            ph += RNG.uniform(0.0, 0.2)

        # Color as proxy for organic matter / mineral content
        if color in ["black/dark", "dark brown"]:
            ph -= RNG.uniform(0.1, 0.25)
        elif color in ["pale/white"]:
            ph += RNG.uniform(0.2, 0.5)  # calcareous soils
        elif color == "red":
            ph -= RNG.uniform(0.1, 0.4)  # iron oxide soils, often acidic

        # Moisture effects
        if moisture == "wet":
            ph -= RNG.uniform(0.0, 0.15)

        # Add realistic noise
        ph += RNG.normal(0, 0.25)

        # Clamp to realistic range
        ph = float(np.clip(ph, 4.0, 9.0))

        records.append({
            "texture": texture,
            "drainage": drainage,
            "moisture": moisture,
            "organic_matter": om,
            "compaction": compaction,
            "water_retention": retention,
            "color": color,
            "texture_code": TEXTURE_MAP[texture],
            "drainage_code": DRAINAGE_MAP[drainage],
            "moisture_code": MOISTURE_MAP[moisture],
            "om_code": OM_MAP[om],
            "compaction_code": COMPACTION_MAP[compaction],
            "retention_code": RETENTION_MAP[retention],
            "color_code": COLOR_MAP[color],
            "ph": round(ph, 2),
        })

    df = pd.DataFrame(records)
    return df


if __name__ == "__main__":
    out_path = Path(__file__).parent.parent / "data" / "soil_dataset.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = generate_dataset(2000)
    df.to_csv(out_path, index=False)
    print(f"Dataset saved: {out_path}")
    print(df.describe())
    print("\nClass distribution (texture):")
    print(df["texture"].value_counts())
    print("\npH distribution:")
    print(df["ph"].describe())
