"""
SoilSense AI — USDA NRCS SSURGO Real Soil Data Fetcher

Fetches real measured surface soil horizon data directly from the
USDA Natural Resources Conservation Service (NRCS) Soil Data Access (SDA)
REST API.

Data Source:
  USDA NRCS Soil Data Access (SDA) — SSURGO Database
  https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest

Authoritative variables fetched:
  - cokey: Component key (identifies specific soil profile / pedon series, preventing data leakage)
  - chkey: Horizon key
  - ph1to1h2o_r: Measured soil pH in 1:1 soil:water ratio (Standard laboratory test)
  - sandtotal_r, claytotal_r, silttotal_r: Measured particle size percentages (USDA standard)
  - om_r: Measured organic matter percentage
  - dbthirdbar_r: Measured bulk density at 1/3 bar (g/cm³), indicator of compaction
  - awc_r: Measured available water capacity (cm/cm), indicator of water retention
  - drainagecl: Measured drainage classification
  - taxorder: Soil taxonomic order (Mollisols, Ultisols, Alfisols, etc.)
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("soilsense.data_fetcher")

DATA_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = DATA_DIR / "soil_dataset.csv"
SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"


def get_usda_texture(sand: float, clay: float, silt: float) -> str:
    """
    Determine USDA soil texture class using the USDA Soil Texture Triangle.
    """
    if pd.isna(sand) or pd.isna(clay):
        return "unknown"

    # Normalize if silt is missing or sum slightly deviates
    if pd.isna(silt):
        silt = max(0.0, 100.0 - sand - clay)

    total = sand + clay + silt
    if total > 0 and abs(total - 100.0) > 1.0:
        sand = (sand / total) * 100.0
        clay = (clay / total) * 100.0
        silt = (silt / total) * 100.0

    if clay >= 40.0:
        return "clay"
    elif sand >= 70.0 and clay <= 15.0:
        return "sandy"
    elif clay >= 27.0 and clay < 40.0 and sand <= 20.0:
        return "silty"
    elif clay >= 27.0 and clay < 40.0 and 20.0 < sand <= 45.0:
        return "clay-loam"
    elif clay >= 20.0 and clay < 35.0 and sand >= 45.0:
        return "sandy-loam"
    elif silt >= 50.0 and clay < 27.0:
        return "silty"
    elif sand >= 50.0 and clay < 20.0:
        return "sandy-loam"
    else:
        return "loamy"


def map_drainage(drainage_str: Optional[str]) -> str:
    """Map USDA NRCS drainage class to 3 standard categories."""
    if not drainage_str or pd.isna(drainage_str):
        return "unknown"
    d = str(drainage_str).lower().strip()
    if any(k in d for k in ["poor", "subaqueous"]):
        return "poor"
    elif any(k in d for k in ["excessive", "somewhat excessive"]):
        return "good"
    elif "well" in d:
        if "somewhat poorly" in d:
            return "poor"
        elif "moderately well" in d:
            return "moderate"
        return "good"
    return "moderate"


def map_organic_matter(om_val: Optional[float]) -> str:
    """Map organic matter percentage to low/moderate/high."""
    if pd.isna(om_val):
        return "unknown"
    try:
        val = float(om_val)
        if val < 1.5:
            return "low"
        elif val <= 4.0:
            return "moderate"
        else:
            return "high"
    except (ValueError, TypeError):
        return "unknown"


def map_compaction(bulk_density: Optional[float]) -> str:
    """Map bulk density (g/cm³) to loose/moderate/compacted."""
    if pd.isna(bulk_density):
        return "unknown"
    try:
        bd = float(bulk_density)
        if bd < 1.25:
            return "loose"
        elif bd <= 1.55:
            return "moderate"
        else:
            return "compacted"
    except (ValueError, TypeError):
        return "unknown"


def map_water_retention(awc: Optional[float]) -> str:
    """Map available water capacity (cm/cm) to low/moderate/high."""
    if pd.isna(awc):
        return "unknown"
    try:
        a = float(awc)
        if a < 0.10:
            return "low"
        elif a <= 0.17:
            return "moderate"
        else:
            return "high"
    except (ValueError, TypeError):
        return "unknown"


def map_moisture(drainage: str, awc: Optional[float]) -> str:
    """Derive moisture tendency from drainage class and water capacity."""
    if drainage == "poor":
        return "wet"
    if not pd.isna(awc):
        try:
            a = float(awc)
            if a < 0.08:
                return "dry"
            elif a > 0.20:
                return "wet"
        except (ValueError, TypeError):
            pass
    if drainage == "good":
        return "dry"
    return "moderate"


def map_soil_color(taxorder: Optional[str], om_val: Optional[float], caco3: Optional[float]) -> str:
    """Derive realistic observable surface color based on USDA taxonomy & mineralogy."""
    order = str(taxorder).lower() if not pd.isna(taxorder) else ""
    try:
        om = float(om_val) if not pd.isna(om_val) else 2.0
    except (ValueError, TypeError):
        om = 2.0

    try:
        calc = float(caco3) if not pd.isna(caco3) else 0.0
    except (ValueError, TypeError):
        calc = 0.0

    if calc > 5.0 or "aridisols" in order:
        return "pale"
    if om > 5.0 or "mollisols" in order or "histosols" in order:
        return "black"
    if "ultisols" in order or "oxisols" in order:
        return "red"
    if om > 2.5:
        return "dark brown"
    if "alfisols" in order:
        return "brown"
    if "inceptisols" in order:
        return "brown"
    if "spodosols" in order:
        return "grey"
    return "brown"


def fetch_usda_soil_data(sample_limit: int = 6000) -> pd.DataFrame:
    """
    Query the USDA NRCS Soil Data Access API for real measured soil records.
    """
    logger.info("Connecting to USDA NRCS Soil Data Access API (%s)...", SDA_URL)

    # Query surface horizons (hzdept_r = 0) where actual laboratory pH is measured
    query = f"""
    SELECT TOP {sample_limit}
        c.cokey,
        ch.chkey,
        c.compname,
        c.taxorder,
        c.drainagecl,
        ch.desgnmaster,
        ch.hzdept_r,
        ch.hzdepb_r,
        ch.sandtotal_r,
        ch.claytotal_r,
        ch.silttotal_r,
        ch.om_r,
        ch.dbthirdbar_r,
        ch.awc_r,
        ch.ksat_r,
        ch.caco3_r,
        ch.sar_r,
        ch.ph1to1h2o_r
    FROM chorizon ch
    JOIN component c ON ch.cokey = c.cokey
    WHERE ch.ph1to1h2o_r IS NOT NULL
      AND ch.sandtotal_r IS NOT NULL
      AND ch.claytotal_r IS NOT NULL
      AND ch.hzdept_r = 0
      AND ch.ph1to1h2o_r BETWEEN 3.2 AND 9.8
    ORDER BY c.cokey
    """

    payload = {
        "query": query,
        "format": "JSON+COLUMNNAME"
    }

    resp = httpx.post(SDA_URL, json=payload, verify=False, timeout=60.0)
    resp.raise_for_status()

    result = resp.json()
    table = result.get("Table", [])
    if len(table) < 2:
        raise ValueError("USDA SDA returned empty table or unexpected structure")

    headers = table[0]
    rows = table[1:]
    logger.info("Successfully fetched %d real records from USDA SSURGO database.", len(rows))

    raw_df = pd.DataFrame(rows, columns=headers)

    # Clean numeric columns
    numeric_cols = [
        "sandtotal_r", "claytotal_r", "silttotal_r", "om_r",
        "dbthirdbar_r", "awc_r", "ksat_r", "caco3_r", "sar_r", "ph1to1h2o_r"
    ]
    for col in numeric_cols:
        raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce")

    # Drop any row without valid pH or sand/clay
    clean_df = raw_df.dropna(subset=["ph1to1h2o_r", "sandtotal_r", "claytotal_r"]).copy()
    logger.info("Valid records with laboratory pH: %d", len(clean_df))

    # Map to domain features
    clean_df["texture"] = clean_df.apply(
        lambda r: get_usda_texture(r["sandtotal_r"], r["claytotal_r"], r["silttotal_r"]),
        axis=1
    )
    clean_df["drainage"] = clean_df["drainagecl"].apply(map_drainage)
    clean_df["organic_matter"] = clean_df["om_r"].apply(map_organic_matter)
    clean_df["soil_compaction"] = clean_df["dbthirdbar_r"].apply(map_compaction)
    clean_df["water_retention"] = clean_df["awc_r"].apply(map_water_retention)
    clean_df["moisture"] = clean_df.apply(
        lambda r: map_moisture(r["drainage"], r["awc_r"]),
        axis=1
    )
    clean_df["soil_color"] = clean_df.apply(
        lambda r: map_soil_color(r["taxorder"], r["om_r"], r["caco3_r"]),
        axis=1
    )

    clean_df["ph"] = clean_df["ph1to1h2o_r"].round(2)
    clean_df["sand_pct"] = clean_df["sandtotal_r"].round(1)
    clean_df["clay_pct"] = clean_df["claytotal_r"].round(1)
    clean_df["silt_pct"] = clean_df["silttotal_r"].round(1)
    clean_df["om_pct"] = clean_df["om_r"].round(2)

    # Keep relevant columns
    final_cols = [
        "cokey",
        "chkey",
        "compname",
        "taxorder",
        "ph",
        "texture",
        "drainage",
        "moisture",
        "organic_matter",
        "soil_compaction",
        "water_retention",
        "soil_color",
        "sand_pct",
        "clay_pct",
        "silt_pct",
        "om_pct",
    ]
    processed_df = clean_df[final_cols].copy()

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    processed_df.to_csv(OUTPUT_CSV, index=False)
    logger.info("Saved %d real soil records to %s", len(processed_df), OUTPUT_CSV)

    return processed_df


if __name__ == "__main__":
    df = fetch_usda_soil_data(sample_limit=6000)
    print("\n--- Summary of Real USDA Dataset ---")
    print(f"Total records: {len(df)}")
    print(f"Unique soil profiles (cokey): {df['cokey'].nunique()}")
    print("pH range:", df['ph'].min(), "to", df['ph'].max(), f"(mean: {df['ph'].mean():.2f})")
    print("\nTexture distribution:")
    print(df["texture"].value_counts())
    print("\nDrainage distribution:")
    print(df["drainage"].value_counts())
    print("\nColor distribution:")
    print(df["soil_color"].value_counts())
