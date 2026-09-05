"""
SoilSense AI — Backend & ML Test Suite

Tests cover:
  - Soil feature extraction (rule-based validation & mocked LLM)
  - Preprocessing & feature encoding (known, unknown, and partial values)
  - Real ML model prediction & Split Conformal Prediction intervals
  - Honest uncertainty degradation under missing/sparse inputs
  - Robust handling of invalid/out-of-distribution inputs
  - Group leakage prevention (zero overlap across train/test profiles)
  - Training metadata & artifact verification
  - Recommendation engine & action planning
  - Weather service & graceful network fallbacks
  - Full API integration & endpoints
"""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# ─────────────────────────────────────────────────────────────
# Preprocessing Tests
# ─────────────────────────────────────────────────────────────

def test_feature_encoding_known_values():
    """Known enum values should map to correct numeric codes."""
    from backend.ml.preprocessing import features_to_vector
    from backend.schemas.soil_schema import SoilFeatures

    features = SoilFeatures(
        texture="clay",
        drainage="poor",
        moisture="wet",
        organic_matter="high",
        soil_compaction="compacted",
        water_retention="high",
        soil_color="dark brown",
    )
    vector, has_unknowns = features_to_vector(features)
    assert len(vector) == 7
    assert vector[0] == 5  # clay
    assert vector[1] == 2  # poor drainage
    assert vector[2] == 2  # wet
    assert not has_unknowns


def test_feature_encoding_unknown_values():
    """Unknown enum values should default gracefully without raising errors."""
    from backend.ml.preprocessing import features_to_vector
    from backend.schemas.soil_schema import SoilFeatures

    features = SoilFeatures(
        texture="unknown",
        drainage="unknown",
        moisture="unknown",
    )
    vector, has_unknowns = features_to_vector(features)
    assert len(vector) == 7
    assert has_unknowns  # unknown fields present


def test_color_to_code_partial_match():
    """Partial colour string matching should work for common descriptions."""
    from backend.ml.preprocessing import color_to_code
    assert color_to_code("reddish-brown") in [2, 5]  # brown or red
    assert color_to_code("very dark") == 4            # black/dark


def test_preprocessing_dataframe_structure():
    """prepare_feature_dataframe should format columns for pipeline consumption."""
    from backend.ml.preprocessing import features_to_dataframe, ALL_INPUT_COLS
    from backend.schemas.soil_schema import SoilFeatures

    feat = SoilFeatures(texture="loamy", drainage="good")
    df = features_to_dataframe(feat)
    assert len(df) == 1
    for col in ALL_INPUT_COLS:
        assert col in df.columns


# ─────────────────────────────────────────────────────────────
# ML Prediction & Uncertainty Tests (Real Model)
# ─────────────────────────────────────────────────────────────

def test_real_model_prediction_and_conformal_interval():
    """Real ML model must produce valid calibrated bounds within natural soil pH."""
    from backend.ml.predict import predict_ph, load_model
    from backend.schemas.soil_schema import SoilFeatures

    assert load_model() is True
    features = SoilFeatures(
        texture="clay",
        drainage="poor",
        moisture="wet",
        organic_matter="high",
        soil_compaction="compacted",
        water_retention="high",
        soil_color="dark brown",
    )
    est = predict_ph(features)

    # Sanity bounds
    assert 3.5 <= est.lower_bound <= est.estimated_ph <= est.upper_bound <= 9.5
    assert est.min == est.lower_bound
    assert est.max == est.upper_bound
    assert est.midpoint == est.estimated_ph

    # Confidence must be valid
    assert 0.10 <= est.confidence <= 0.95
    assert est.confidence_level in ["High", "Medium", "Low"]
    assert "conformal" in est.method_note.lower() or "usda" in est.method_note.lower()


def test_uncertainty_degrades_with_missing_inputs():
    """Confidence must strictly decrease and interval widen when features are missing."""
    from backend.ml.predict import predict_ph
    from backend.schemas.soil_schema import SoilFeatures

    rich_features = SoilFeatures(
        texture="clay",
        drainage="poor",
        moisture="wet",
        organic_matter="high",
        soil_compaction="compacted",
        water_retention="high",
        soil_color="dark brown",
    )
    sparse_features = SoilFeatures(
        texture="unknown",
        drainage="unknown",
        moisture="unknown",
        organic_matter="unknown",
        soil_color="unknown",
    )

    est_rich = predict_ph(rich_features)
    est_sparse = predict_ph(sparse_features)

    # 1. Confidence must strictly decrease
    assert est_sparse.confidence < est_rich.confidence
    # 2. Prediction interval must widen
    width_rich = est_rich.upper_bound - est_rich.lower_bound
    width_sparse = est_sparse.upper_bound - est_sparse.lower_bound
    assert width_sparse > width_rich
    # 3. Sparse features must trigger Low confidence rating
    assert est_sparse.confidence_level == "Low"
    assert est_sparse.low_confidence_warning is not None


def test_invalid_and_outlier_inputs_handled_gracefully():
    """Invalid or unexpected input values must not crash the prediction service."""
    from backend.ml.predict import predict_ph
    from backend.schemas.soil_schema import SoilFeatures

    # Create features with weird text and unusual attributes
    features = SoilFeatures(
        texture="unknown",
        drainage="unknown",
        soil_color="fluorescent neon purple with metallic sparkle",
        raw_description="Alien soil found on Mars",
    )
    est = predict_ph(features)

    assert 3.5 <= est.lower_bound <= est.estimated_ph <= est.upper_bound <= 9.5
    assert est.confidence_level == "Low"


def test_ph_midpoint_within_range():
    """Midpoint must always fall within min–max range."""
    from backend.ml.predict import _fallback_estimate
    from backend.schemas.soil_schema import SoilFeatures

    features = SoilFeatures(texture="loamy", drainage="moderate", moisture="moderate")
    est = _fallback_estimate(features)
    assert est.min <= est.midpoint <= est.max


# ─────────────────────────────────────────────────────────────
# Group Leakage & Training Pipeline Tests
# ─────────────────────────────────────────────────────────────

def test_group_leakage_prevention():
    """Data split must have zero overlap in soil profile IDs (cokey) across train/cal/test."""
    import pandas as pd
    from backend.ml.train import split_data_without_leakage

    dataset_path = Path(__file__).resolve().parents[2] / "data" / "soil_dataset.csv"
    assert dataset_path.exists(), "Real dataset must exist"
    df = pd.read_csv(dataset_path)

    X_train, y_train, X_cal, y_cal, X_test, y_test = split_data_without_leakage(df)

    cokeys_train = set(df.loc[X_train.index, "cokey"])
    cokeys_cal = set(df.loc[X_cal.index, "cokey"])
    cokeys_test = set(df.loc[X_test.index, "cokey"])

    # Strict zero-leakage assertions
    assert len(cokeys_train.intersection(cokeys_cal)) == 0
    assert len(cokeys_train.intersection(cokeys_test)) == 0
    assert len(cokeys_cal.intersection(cokeys_test)) == 0


def test_training_metadata_and_artifacts():
    """Metadata file must document real dataset source, CV scores, and conformal metrics."""
    metadata_path = Path(__file__).resolve().parents[1] / "ml" / "model" / "training_metadata.json"
    assert metadata_path.exists(), "training_metadata.json must exist"

    meta = json.loads(metadata_path.read_text())
    assert "USDA" in meta["dataset_source"]
    assert meta["dataset_rows"] >= 500
    assert "test_metrics" in meta
    assert meta["test_metrics"]["test_mae"] < 0.60
    assert meta["test_metrics"]["test_coverage"] >= 75.0
    assert "cross_validation" in meta


# ─────────────────────────────────────────────────────────────
# Feature Extraction Tests (mocked LLM)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_features_parses_valid_json():
    """Extractor should parse valid LLM JSON output into SoilFeatures."""
    mock_response = json.dumps({
        "soil_color": "dark brown",
        "texture": "clay",
        "drainage": "poor",
        "moisture": "wet",
        "organic_matter": "high",
        "soil_compaction": "moderate",
        "water_retention": "high",
        "surface_deposits": "none detected",
        "vegetation_observed": "earthworms",
        "location": "Pune, India",
        "target_crop": "tomato",
    })

    with patch("backend.agents.feature_extractor.chat_completion", new=AsyncMock(return_value=mock_response)):
        from backend.agents.feature_extractor import extract_soil_features
        features = await extract_soil_features(
            description="My soil is dark brown and sticky",
            location="Pune, India",
            target_crop="tomato",
        )

    assert features.texture == "clay"
    assert features.drainage == "poor"
    assert features.organic_matter == "high"
    assert features.location == "Pune, India"


@pytest.mark.asyncio
async def test_extract_features_handles_malformed_json():
    """Extractor should fall back to heuristic extraction on malformed LLM output."""
    with patch("backend.agents.feature_extractor.chat_completion", new=AsyncMock(return_value="NOT JSON {{")):
        from backend.agents.feature_extractor import extract_soil_features
        features = await extract_soil_features(description="Sticky red clay soil", location="unknown")

    # Should not raise; heuristic should extract clay and red
    assert features.texture == "clay"
    assert "red" in features.soil_color.lower()


@pytest.mark.asyncio
async def test_extract_features_handles_invalid_enum():
    """Extractor should coerce invalid enum values to 'unknown'."""
    mock_response = json.dumps({
        "texture": "marshy",  # invalid value
        "drainage": "ultra-fast",  # invalid
        "moisture": "moderate",
    })

    with patch("backend.agents.feature_extractor.chat_completion", new=AsyncMock(return_value=mock_response)):
        from backend.agents.feature_extractor import extract_soil_features
        features = await extract_soil_features(description="test")

    assert features.texture == "unknown"
    assert features.drainage == "unknown"
    assert features.moisture == "moderate"  # valid value preserved


# ─────────────────────────────────────────────────────────────
# Recommendation Engine Tests
# ─────────────────────────────────────────────────────────────

def test_recommendation_returns_crops():
    """Recommendation engine should return at least one suitable crop."""
    from backend.agents.recommendation_agent import recommend_crops
    from backend.schemas.soil_schema import SoilFeatures, PHEstimate, WeatherData

    features = SoilFeatures(texture="loamy", drainage="moderate", moisture="moderate")
    ph_est = PHEstimate(
        estimated_ph=6.5,
        lower_bound=6.0,
        upper_bound=7.0,
        confidence_level="High",
        confidence=0.75,
    )
    weather = WeatherData(location_name="Pune", error="No weather")

    result = recommend_crops(features, ph_est, weather, target_crop="tomato")
    assert len(result.suitable_crops) > 0


def test_recommendation_avoids_incompatible_crops():
    """Crops outside pH range should appear in crops_to_avoid, not suitable_crops."""
    from backend.agents.recommendation_agent import recommend_crops
    from backend.schemas.soil_schema import SoilFeatures, PHEstimate, WeatherData

    # Very acidic soil
    features = SoilFeatures(texture="sandy", drainage="good")
    ph_est = PHEstimate(
        estimated_ph=4.75,
        lower_bound=4.5,
        upper_bound=5.0,
        confidence_level="Medium",
        confidence=0.6,
    )
    weather = WeatherData(location_name="Test", error="N/A")

    result = recommend_crops(features, ph_est, weather)
    suitable_names = [c.crop_name for c in result.suitable_crops]
    assert "Spinach" not in suitable_names


def test_action_plan_has_high_priority_soil_test():
    """Action plan must always include the soil test confirmation step as high priority."""
    from backend.agents.recommendation_agent import recommend_crops
    from backend.schemas.soil_schema import SoilFeatures, PHEstimate, WeatherData

    features = SoilFeatures()
    ph_est = PHEstimate(
        estimated_ph=6.25,
        lower_bound=5.5,
        upper_bound=7.0,
        confidence_level="Medium",
        confidence=0.5,
    )
    weather = WeatherData(location_name="Test", error="N/A")

    result = recommend_crops(features, ph_est, weather)
    high_priority = [s for s in result.action_plan if s.priority == "high"]
    soil_test_steps = [s for s in high_priority if "soil test" in s.action.lower() or "confirm" in s.action.lower()]
    assert len(soil_test_steps) > 0


# ─────────────────────────────────────────────────────────────
# Weather Service Tests (mocked HTTP)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_weather_unknown_location():
    """Empty / unknown location should return WeatherData with error, not raise."""
    from backend.weather.weather_service import get_weather
    result = await get_weather("unknown")
    assert result.error is not None


@pytest.mark.asyncio
async def test_weather_network_failure_graceful():
    """Network failure should return WeatherData with error field set."""
    import httpx
    from backend.weather.weather_service import get_weather

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
        result = await get_weather("Pune, India")

    assert result.error is not None
    assert "unavailable" in result.error.lower() or "could not" in result.error.lower()


# ─────────────────────────────────────────────────────────────
# API Endpoint Tests
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Create a TestClient with the FastAPI app."""
    from backend.main import app
    return TestClient(app)


def test_health_endpoint(client):
    """Health endpoint should return 200 with status=ok and ml_model_loaded=true."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ml_model_loaded"] is True


def test_analyze_soil_missing_description(client):
    """Request with empty description should return 422 validation error."""
    response = client.post("/api/analyze-soil", json={"description": "", "location": "Pune"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_soil_end_to_end():
    """Full pipeline integration test with real ML model and mocked LLM/weather."""
    mock_features_json = json.dumps({
        "soil_color": "dark brown",
        "texture": "clay",
        "drainage": "poor",
        "moisture": "wet",
        "organic_matter": "high",
        "soil_compaction": "moderate",
        "water_retention": "high",
        "surface_deposits": "none detected",
        "vegetation_observed": "earthworms",
        "location": "Pune, India",
        "target_crop": "tomato",
    })

    from backend.schemas.soil_schema import WeatherData as WD
    mock_weather = WD(
        location_name="Pune, India",
        temperature_celsius=28.0,
        humidity_percent=70.0,
        precipitation_mm=2.5,
        precipitation_probability=40.0,
        weather_description="Partly cloudy",
        forecast_summary="Moderate rainfall expected.",
        weather_impact_note="Conditions are favourable.",
        error=None,
    )

    with (
        patch("backend.agents.feature_extractor.chat_completion", new=AsyncMock(return_value=mock_features_json)),
        patch("backend.agents.soil_agent.get_weather", new=AsyncMock(return_value=mock_weather)),
        patch("backend.agents.soil_agent.chat_completion", new=AsyncMock(return_value="Soil analysis explanation.")),
    ):
        from backend.agents.soil_agent import run_soil_analysis
        from backend.schemas.soil_schema import AnalyzeSoilRequest

        request = AnalyzeSoilRequest(
            description="My soil is dark brown, sticky when wet, drains slowly. I want to grow tomatoes.",
            location="Pune, India",
            target_crop="tomato",
        )
        result = await run_soil_analysis(request)

    assert result.soil_profile.texture == "clay"
    assert 3.5 <= result.estimated_ph.lower_bound <= result.estimated_ph.upper_bound <= 9.5
    assert result.estimated_ph.confidence_level in ["High", "Medium", "Low"]
    assert len(result.recommendations.suitable_crops) > 0
    assert result.safety_disclaimer is not None
    assert result.demo_data_used is False
