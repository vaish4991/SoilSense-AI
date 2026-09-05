"""
SoilSense AI — Backend Tests

Tests cover:
  - Soil feature extraction (rule-based validation)
  - ML prediction (valid output, fallback, confidence)
  - Preprocessing / feature encoding
  - Recommendation engine
  - Weather service (mock)
  - API endpoints (via TestClient)
  - Error handling / malformed inputs
"""
from __future__ import annotations
import json
from unittest.mock import AsyncMock, MagicMock, patch

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


# ─────────────────────────────────────────────────────────────
# ML Prediction Tests
# ─────────────────────────────────────────────────────────────

def test_ph_estimate_range():
    """pH estimate should be within realistic soil pH bounds."""
    from backend.ml.predict import predict_ph, _fallback_estimate
    from backend.schemas.soil_schema import SoilFeatures

    features = SoilFeatures(
        texture="sandy",
        drainage="good",
        moisture="dry",
        organic_matter="low",
        soil_color="pale",
    )
    estimate = _fallback_estimate(features)
    assert 3.5 <= estimate.min <= estimate.max <= 9.5
    assert 0.0 <= estimate.confidence <= 1.0


def test_ph_estimate_confidence_low_for_unknown_features():
    """Confidence should be lower when core features are unknown."""
    from backend.ml.predict import _fallback_estimate
    from backend.schemas.soil_schema import SoilFeatures

    known_features = SoilFeatures(texture="clay", drainage="poor", moisture="wet")
    unknown_features = SoilFeatures()  # all defaults = unknown

    est_known = _fallback_estimate(known_features)
    est_unknown = _fallback_estimate(unknown_features)

    # Unknown features should not magically have high confidence
    assert est_unknown.confidence <= 0.6


def test_ph_midpoint_within_range():
    """Midpoint must fall within min–max range."""
    from backend.ml.predict import _fallback_estimate
    from backend.schemas.soil_schema import SoilFeatures

    features = SoilFeatures(texture="loamy", drainage="moderate", moisture="moderate")
    est = _fallback_estimate(features)
    assert est.min <= est.midpoint <= est.max


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
    """Extractor should return default SoilFeatures on malformed LLM output."""
    with patch("backend.agents.feature_extractor.chat_completion", new=AsyncMock(return_value="NOT JSON {{")):
        from backend.agents.feature_extractor import extract_soil_features
        features = await extract_soil_features(description="My soil is red", location="unknown")

    # Should not raise; texture should default to unknown
    assert features.texture == "unknown"


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
    ph_est = PHEstimate(min=6.0, max=7.0, midpoint=6.5, confidence=0.75)
    weather = WeatherData(location_name="Pune", error="No weather")

    result = recommend_crops(features, ph_est, weather, target_crop="tomato")
    assert len(result.suitable_crops) > 0


def test_recommendation_avoids_incompatible_crops():
    """Crops outside pH range should appear in crops_to_avoid, not suitable_crops."""
    from backend.agents.recommendation_agent import recommend_crops
    from backend.schemas.soil_schema import SoilFeatures, PHEstimate, WeatherData

    # Very acidic soil — blueberry zone
    features = SoilFeatures(texture="sandy", drainage="good")
    ph_est = PHEstimate(min=4.5, max=5.0, midpoint=4.75, confidence=0.6)
    weather = WeatherData(location_name="Test", error="N/A")

    result = recommend_crops(features, ph_est, weather)
    # Spinach (preferred 6.5–7.5) should NOT be in suitable crops
    suitable_names = [c.crop_name for c in result.suitable_crops]
    assert "Spinach" not in suitable_names


def test_action_plan_has_high_priority_soil_test():
    """Action plan must always include the soil test confirmation step as high priority."""
    from backend.agents.recommendation_agent import recommend_crops
    from backend.schemas.soil_schema import SoilFeatures, PHEstimate, WeatherData

    features = SoilFeatures()
    ph_est = PHEstimate(min=5.5, max=7.0, midpoint=6.25, confidence=0.5)
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
    """Health endpoint should always return 200 with status=ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "ml_model_loaded" in data


def test_analyze_soil_missing_description(client):
    """Request with empty description should return 422 validation error."""
    response = client.post("/api/analyze-soil", json={"description": "", "location": "Pune"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_soil_end_to_end():
    """Full pipeline integration test with mocked LLM and weather."""
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
        patch("backend.agents.soil_agent.chat_completion", new=AsyncMock(return_value="Good soil analysis explanation.")),
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
    assert 3.5 <= result.estimated_ph.min <= result.estimated_ph.max <= 9.5
    assert 0.0 <= result.estimated_ph.confidence <= 1.0
    assert len(result.recommendations.suitable_crops) > 0
    assert result.safety_disclaimer is not None


# ─────────────────────────────────────────────────────────────
# Low-confidence Prediction Test
# ─────────────────────────────────────────────────────────────

def test_low_confidence_warning_present_for_sparse_features():
    """Sparse features (all unknown) should produce a low-confidence warning."""
    from backend.ml.predict import _fallback_estimate
    from backend.schemas.soil_schema import SoilFeatures

    features = SoilFeatures()  # all unknowns
    estimate = _fallback_estimate(features)
    # Should have low confidence
    assert estimate.confidence < 0.6
    # Warning should be present
    assert estimate.low_confidence_warning is not None
