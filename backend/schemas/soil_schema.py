"""
SoilSense AI — Pydantic schemas for all domain objects.
Defines structured representations of soil features, pH estimates,
weather data, recommendations, and API request/response models.
"""
from __future__ import annotations
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────────────────────
# Soil Feature Schema (structured output from LLM extraction)
# ─────────────────────────────────────────────────────────────

TextureEnum = Literal["sandy", "loamy", "clay", "silty", "clay-loam", "sandy-loam", "unknown"]
DrainageEnum = Literal["poor", "moderate", "good", "unknown"]
MoistureEnum = Literal["dry", "moderate", "wet", "unknown"]
OrganicMatterEnum = Literal["low", "moderate", "high", "unknown"]
CompactionEnum = Literal["loose", "moderate", "compacted", "unknown"]


class SoilFeatures(BaseModel):
    """Structured soil characteristics extracted from natural-language description."""
    soil_color: str = Field(default="unknown", description="Observed soil colour (e.g. dark brown, red, pale)")
    texture: TextureEnum = Field(default="unknown")
    drainage: DrainageEnum = Field(default="unknown")
    moisture: MoistureEnum = Field(default="unknown")
    organic_matter: OrganicMatterEnum = Field(default="unknown", description="Inferred organic matter level")
    soil_compaction: CompactionEnum = Field(default="unknown")
    water_retention: Literal["low", "moderate", "high", "unknown"] = Field(default="unknown")
    surface_deposits: str = Field(default="none detected", description="E.g. white salt-like deposits, crust")
    vegetation_observed: str = Field(default="unknown", description="Vegetation or organisms noticed in soil")
    location: str = Field(default="unknown")
    target_crop: str = Field(default="unknown")
    raw_description: str = Field(default="", description="Original user description for reference")


# ─────────────────────────────────────────────────────────────
# pH Estimate
# ─────────────────────────────────────────────────────────────

class PHEstimate(BaseModel):
    """pH estimate produced by the ML model, always presented as a range with confidence."""
    # Calibrated interval bounds & point estimate (Requirement 10)
    estimated_ph: float = Field(default=6.5, ge=0.0, le=14.0, description="Estimated point pH")
    lower_bound: float = Field(default=5.5, ge=0.0, le=14.0, description="Lower pH bound (calibrated conformal prediction interval)")
    upper_bound: float = Field(default=7.5, ge=0.0, le=14.0, description="Upper pH bound (calibrated conformal prediction interval)")
    confidence_level: Literal["High", "Medium", "Low"] = Field(default="Medium", description="Qualitative confidence rating")

    # Backwards-compatible fields for frontend and existing endpoints
    min: float = Field(default=5.5, ge=0.0, le=14.0, description="Alias for lower_bound")
    max: float = Field(default=7.5, ge=0.0, le=14.0, description="Alias for upper_bound")
    midpoint: float = Field(default=6.5, ge=0.0, le=14.0, description="Alias for estimated_ph")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score 0–1")
    low_confidence_warning: Optional[str] = Field(
        default=None,
        description="Warning message if prediction is outside training distribution or inputs are sparse"
    )
    feature_completeness: float = Field(default=0.8, ge=0.0, le=1.0, description="Proportion of key observable characteristics detected (0-1)")
    detected_features_count: int = Field(default=4, ge=0, le=5, description="Number of observable core features detected out of 5")
    ensemble_agreement: str = Field(default="High", description="Degree of agreement across Random Forest decision trees")
    method_note: str = Field(
        default="Split Conformal Prediction interval calibrated on real USDA NRCS SSURGO measured soil data.",
        description="Brief explanation of how uncertainty and bounds were derived"
    )

    @model_validator(mode="before")
    @classmethod
    def sync_bounds(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync estimated_ph <-> midpoint
            if "estimated_ph" not in data and "midpoint" in data:
                data["estimated_ph"] = data["midpoint"]
            elif "midpoint" not in data and "estimated_ph" in data:
                data["midpoint"] = data["estimated_ph"]

            # Sync lower_bound <-> min
            if "lower_bound" not in data and "min" in data:
                data["lower_bound"] = data["min"]
            elif "min" not in data and "lower_bound" in data:
                data["min"] = data["lower_bound"]

            # Sync upper_bound <-> max
            if "upper_bound" not in data and "max" in data:
                data["upper_bound"] = data["max"]
            elif "max" not in data and "upper_bound" in data:
                data["max"] = data["upper_bound"]
        return data


# ─────────────────────────────────────────────────────────────
# Weather
# ─────────────────────────────────────────────────────────────

class WeatherData(BaseModel):
    location_name: str
    temperature_celsius: Optional[float] = None
    humidity_percent: Optional[float] = None
    precipitation_mm: Optional[float] = None
    precipitation_probability: Optional[float] = None
    weather_description: str = "Unknown"
    forecast_summary: str = "Forecast unavailable"
    weather_impact_note: str = Field(
        default="",
        description="How current weather conditions affect soil recommendations"
    )
    source: str = "Open-Meteo (open-meteo.com)"
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Recommendations
# ─────────────────────────────────────────────────────────────

class CropRecommendation(BaseModel):
    crop_name: str
    suitability: Literal["highly_suitable", "suitable", "marginal", "not_recommended"]
    reason: str
    ph_compatibility_note: str
    weather_note: str = ""


class ActionStep(BaseModel):
    step_number: int
    action: str
    priority: Literal["high", "medium", "low"]


class RecommendationResult(BaseModel):
    suitable_crops: List[CropRecommendation]
    crops_to_avoid: List[str]
    action_plan: List[ActionStep]
    amendment_warning: str = (
        "Confirm pH with a physical soil test before applying lime, sulfur, or other major soil amendments."
    )
    limitations: List[str]


# ─────────────────────────────────────────────────────────────
# Follow-up questions
# ─────────────────────────────────────────────────────────────

class FollowUpQuestion(BaseModel):
    question: str
    reason: str = Field(description="Why this question is needed for better prediction")


class FollowUpResult(BaseModel):
    needs_more_info: bool
    questions: List[FollowUpQuestion]
    available_features: SoilFeatures


# ─────────────────────────────────────────────────────────────
# API Request / Response
# ─────────────────────────────────────────────────────────────

class AnalyzeSoilRequest(BaseModel):
    description: str = Field(..., min_length=5, description="Natural-language soil description")
    location: str = Field(default="unknown", description="City, region, or country")
    target_crop: str = Field(default="unknown", description="Crop the user wants to grow")
    conversation_history: List[dict] = Field(
        default_factory=list,
        description="Previous messages in multi-turn chat [[role, content], ...]"
    )


class SoilAnalysisResponse(BaseModel):
    soil_profile: SoilFeatures
    estimated_ph: PHEstimate
    ph_explanation: str = Field(description="Plain-English explanation of which features drove the pH estimate")
    weather: Optional[WeatherData] = None
    recommendations: RecommendationResult
    ai_explanation: str = Field(description="Full narrative explanation from the LLM")
    safety_disclaimer: str = (
        "This is an AI-based estimate derived from described soil characteristics. "
        "It is NOT a laboratory measurement. For agricultural decisions involving soil amendments "
        "or treatments, confirm pH using a certified physical soil test."
    )
    demo_data_used: bool = Field(
        default=False,
        description="True if synthetic demo dataset was used for ML prediction"
    )


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    location: str = "unknown"
    target_crop: str = "unknown"


class HealthResponse(BaseModel):
    status: str
    ml_model_loaded: bool
    llm_provider: str
    version: str = "1.0.0"
