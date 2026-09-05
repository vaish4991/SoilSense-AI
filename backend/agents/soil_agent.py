"""
SoilSense AI — Main Soil Agent

Orchestrates the full analysis pipeline:
  1. Extract soil features from natural language (LLM)
  2. Check if more information is needed → follow-up questions
  3. Predict pH using ML model (NOT the LLM)
  4. Fetch weather data
  5. Generate crop recommendations
  6. Generate LLM explanation (explain ML output in plain language)

The LLM is responsible for language understanding and explanation.
The ML model is responsible for numerical pH prediction.
"""
from __future__ import annotations
import logging
from typing import List, Optional

from backend.agents.feature_extractor import extract_soil_features, check_for_missing_info
from backend.agents.llm_client import chat_completion
from backend.agents.recommendation_agent import recommend_crops
from backend.ml.predict import predict_ph
from backend.schemas.soil_schema import (
    AnalyzeSoilRequest,
    SoilAnalysisResponse,
    SoilFeatures,
    PHEstimate,
    WeatherData,
    RecommendationResult,
    FollowUpResult,
)
from backend.weather.weather_service import get_weather

logger = logging.getLogger("soilsense.agent")

EXPLANATION_SYSTEM_PROMPT = """
You are SoilSense AI, an intelligent soil analysis assistant.
Your job is to explain a soil analysis report to a non-expert farmer or gardener.

You will receive:
- Extracted soil features
- An ML-predicted pH range with confidence
- Weather data
- Crop recommendations

Write a clear, warm, 3–5 paragraph explanation covering:
1. What the soil description tells us about soil health
2. Why the ML model predicted this pH range (which features were most influential)
3. How the current weather affects the recommendations
4. Key action items the user should take

IMPORTANT RULES:
- NEVER state the pH as a precise measurement. Always present it as an estimate.
- ALWAYS remind the user to confirm pH with a physical soil test before major amendments.
- Do NOT recommend exact fertilizer quantities or chemical dosages.
- Speak directly to the user in a helpful, accessible tone.
- Keep it under 300 words.
""".strip()


async def run_soil_analysis(request: AnalyzeSoilRequest) -> SoilAnalysisResponse:
    """
    Run the full soil analysis pipeline.

    Args:
        request: User's soil description, location, and optional target crop.

    Returns:
        Complete SoilAnalysisResponse with all analysis sections.
    """
    logger.info(
        "Starting soil analysis | location=%s crop=%s desc_len=%d",
        request.location, request.target_crop, len(request.description),
    )

    # ── Step 1: Extract soil features ────────────────────────
    features = await extract_soil_features(
        description=request.description,
        location=request.location,
        target_crop=request.target_crop,
        conversation_history=request.conversation_history,
    )
    logger.info("Features extracted: %s", features.model_dump())

    # ── Step 2: ML pH prediction ──────────────────────────────
    ph_estimate = predict_ph(features)
    logger.info(
        "pH estimate: %.2f (%.1f–%.1f) confidence=%.2f",
        ph_estimate.midpoint, ph_estimate.min, ph_estimate.max, ph_estimate.confidence,
    )

    # ── Step 3: Weather data ──────────────────────────────────
    weather: Optional[WeatherData] = None
    if request.location and request.location.lower() != "unknown":
        try:
            weather = await get_weather(request.location)
            logger.info("Weather fetched: %s", weather.location_name)
        except Exception as exc:
            logger.warning("Weather fetch failed: %s", exc)
            weather = WeatherData(
                location_name=request.location,
                error="Weather service temporarily unavailable.",
            )
    else:
        weather = WeatherData(
            location_name="Unknown",
            error="No location provided for weather lookup.",
        )

    # ── Step 4: Crop recommendations ──────────────────────────
    recommendations = recommend_crops(
        features=features,
        ph_estimate=ph_estimate,
        weather=weather,
        target_crop=request.target_crop,
    )
    logger.info(
        "Recommendations: %d crops suggested",
        len(recommendations.suitable_crops),
    )

    # ── Step 5: LLM explanation ───────────────────────────────
    explanation = await _generate_explanation(
        features=features,
        ph_estimate=ph_estimate,
        weather=weather,
        recommendations=recommendations,
    )

    # ── Step 6: pH explanation ────────────────────────────────
    ph_explanation = _build_ph_explanation(features, ph_estimate)

    logger.info("Soil analysis complete.")

    return SoilAnalysisResponse(
        soil_profile=features,
        estimated_ph=ph_estimate,
        ph_explanation=ph_explanation,
        weather=weather,
        recommendations=recommendations,
        ai_explanation=explanation,
        demo_data_used=True,  # synthetic dataset used
    )


async def _generate_explanation(
    features: SoilFeatures,
    ph_estimate: PHEstimate,
    weather: WeatherData,
    recommendations: RecommendationResult,
) -> str:
    """Ask the LLM to explain the ML results in plain language."""
    crop_names = [r.crop_name for r in recommendations.suitable_crops[:3]]

    context = f"""
Soil Profile:
- Color: {features.soil_color}
- Texture: {features.texture}
- Drainage: {features.drainage}
- Moisture: {features.moisture}
- Organic Matter: {features.organic_matter}
- Location: {features.location}
- Target Crop: {features.target_crop}

ML Prediction (Random Forest):
- Estimated pH range: {ph_estimate.min}–{ph_estimate.max}
- Midpoint: {ph_estimate.midpoint}
- Model confidence: {ph_estimate.confidence * 100:.0f}%
- Warning: {ph_estimate.low_confidence_warning or 'None'}

Weather ({weather.location_name}):
- Temperature: {weather.temperature_celsius}°C
- Humidity: {weather.humidity_percent}%
- Precipitation probability: {weather.precipitation_probability}%
- Forecast: {weather.forecast_summary}
- Weather error: {weather.error or 'None'}

Top recommended crops: {', '.join(crop_names) if crop_names else 'None found'}
""".strip()

    messages = [{"role": "user", "content": f"Please explain this soil analysis:\n\n{context}"}]

    try:
        explanation = await chat_completion(
            messages=messages,
            system_prompt=EXPLANATION_SYSTEM_PROMPT,
            temperature=0.4,
        )
        return explanation.strip()
    except Exception as exc:
        logger.warning("LLM explanation failed: %s", exc)
        return (
            f"Your soil has been analysed. The ML model estimates a pH range of "
            f"{ph_estimate.min}–{ph_estimate.max} with {ph_estimate.confidence * 100:.0f}% confidence. "
            f"Please confirm this with a physical soil test before applying any soil amendments. "
            f"Top crop suggestions: {', '.join(crop_names)}."
        )


def _build_ph_explanation(features: SoilFeatures, ph_estimate: PHEstimate) -> str:
    """
    Build a plain-English explanation of which soil features influenced pH prediction.
    This is generated deterministically (no LLM) based on feature values.
    """
    drivers = []

    if features.texture not in ("unknown",):
        texture_impacts = {
            "sandy": "Sandy soils tend to be more acidic due to nutrient leaching",
            "clay": "Clay soils tend to buffer toward neutral to slightly alkaline pH",
            "loamy": "Loamy soils typically support a near-neutral, balanced pH",
            "silty": "Silty soils often have a slightly elevated pH",
            "clay-loam": "Clay-loam texture suggests a moderate to slightly alkaline buffering capacity",
            "sandy-loam": "Sandy-loam texture is associated with slightly acidic to neutral pH",
        }
        if features.texture in texture_impacts:
            drivers.append(texture_impacts[features.texture])

    if features.drainage == "poor":
        drivers.append("poor drainage can indicate waterlogging which tends to lower soil pH slightly")
    elif features.drainage == "good":
        drivers.append("good drainage is associated with stable, slightly neutral conditions")

    if features.organic_matter == "high":
        drivers.append("high organic matter (suggested by dark colour and earthworm activity) typically lowers pH slightly as organic acids are released during decomposition")
    elif features.organic_matter == "low":
        drivers.append("low organic matter is associated with slightly higher pH")

    color = features.soil_color.lower()
    if "dark" in color or "black" in color:
        drivers.append("the dark soil colour suggests higher organic content, which tends toward slightly acidic pH")
    elif "pale" in color or "white" in color:
        drivers.append("pale or white soil often contains calcium carbonate deposits, indicating alkaline conditions")
    elif "red" in color:
        drivers.append("reddish soil colour often indicates iron oxide minerals, common in acidic tropical soils")

    if not drivers:
        return (
            "The pH estimate was derived from the combination of soil texture, drainage, and moisture "
            "information provided. More details about soil colour and organic matter would help refine the estimate."
        )

    return "The model was influenced by the following characteristics: " + "; ".join(drivers) + "."


async def check_if_followup_needed(request: AnalyzeSoilRequest) -> FollowUpResult:
    """
    Determine if the soil description provides enough information for a confident prediction.
    If not, return targeted follow-up questions.
    """
    features = await extract_soil_features(
        description=request.description,
        location=request.location,
        target_crop=request.target_crop,
    )
    return await check_for_missing_info(features)
