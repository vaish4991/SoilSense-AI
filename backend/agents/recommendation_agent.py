"""
SoilSense AI — Crop Recommendation Engine

Combines ML pH estimate + soil features + weather data to recommend crops.

Architecture:
  1. A curated crop database (pH tolerance, texture preference, drainage needs)
  2. Rule-based suitability scoring
  3. LLM layer for natural-language explanation of the recommendations

SAFETY NOTE:
  This engine does NOT recommend specific fertilizer dosages or chemical
  quantities. For any soil amendment decisions, users are directed to
  confirm pH with a physical soil test.
"""
from __future__ import annotations
import logging
from typing import List

from backend.schemas.soil_schema import (
    CropRecommendation,
    ActionStep,
    RecommendationResult,
    PHEstimate,
    SoilFeatures,
    WeatherData,
)

logger = logging.getLogger("soilsense.recommendation")

# ─────────────────────────────────────────────────────────────
# Crop Database
# pH ranges sourced from: https://extension.psu.edu/soil-ph-for-field-crops
# and USDA NRCS Plant Guides
# ─────────────────────────────────────────────────────────────
CROP_DB = [
    {
        "name": "Tomato",
        "ph_min": 6.0, "ph_max": 6.8,
        "preferred_textures": ["loamy", "clay-loam", "sandy-loam"],
        "preferred_drainage": ["moderate", "good"],
        "moisture_tolerance": ["moderate"],
        "notes": "Requires well-drained soil. Sensitive to waterlogging.",
    },
    {
        "name": "Wheat",
        "ph_min": 6.0, "ph_max": 7.5,
        "preferred_textures": ["loamy", "clay-loam", "silty"],
        "preferred_drainage": ["moderate", "good"],
        "moisture_tolerance": ["moderate", "dry"],
        "notes": "Tolerates a wide pH range. Performs well in moderate rainfall.",
    },
    {
        "name": "Rice",
        "ph_min": 5.5, "ph_max": 7.0,
        "preferred_textures": ["clay", "clay-loam", "silty"],
        "preferred_drainage": ["poor", "moderate"],
        "moisture_tolerance": ["wet", "moderate"],
        "notes": "Thrives in poorly-drained or flooded conditions.",
    },
    {
        "name": "Maize (Corn)",
        "ph_min": 5.8, "ph_max": 7.0,
        "preferred_textures": ["loamy", "sandy-loam", "clay-loam"],
        "preferred_drainage": ["moderate", "good"],
        "moisture_tolerance": ["moderate"],
        "notes": "Sensitive to poor drainage. Needs adequate nitrogen.",
    },
    {
        "name": "Soybean",
        "ph_min": 6.0, "ph_max": 7.0,
        "preferred_textures": ["loamy", "clay-loam"],
        "preferred_drainage": ["moderate", "good"],
        "moisture_tolerance": ["moderate"],
        "notes": "Fixes its own nitrogen. Susceptible to iron deficiency in alkaline soils.",
    },
    {
        "name": "Potato",
        "ph_min": 4.8, "ph_max": 6.5,
        "preferred_textures": ["sandy", "sandy-loam", "loamy"],
        "preferred_drainage": ["good", "moderate"],
        "moisture_tolerance": ["moderate"],
        "notes": "Prefers slightly acidic soils. Well-drained, loose soil reduces scab.",
    },
    {
        "name": "Groundnut (Peanut)",
        "ph_min": 5.5, "ph_max": 7.0,
        "preferred_textures": ["sandy", "sandy-loam", "loamy"],
        "preferred_drainage": ["good", "moderate"],
        "moisture_tolerance": ["moderate", "dry"],
        "notes": "Needs loose soil for pod development. Poor drainage causes root rot.",
    },
    {
        "name": "Sugarcane",
        "ph_min": 6.0, "ph_max": 7.5,
        "preferred_textures": ["loamy", "clay-loam"],
        "preferred_drainage": ["moderate"],
        "moisture_tolerance": ["wet", "moderate"],
        "notes": "Requires high rainfall or irrigation. Good for tropical climates.",
    },
    {
        "name": "Chilli Pepper",
        "ph_min": 6.0, "ph_max": 7.0,
        "preferred_textures": ["loamy", "sandy-loam"],
        "preferred_drainage": ["good", "moderate"],
        "moisture_tolerance": ["moderate"],
        "notes": "Sensitive to waterlogging. Prefers warm temperatures.",
    },
    {
        "name": "Onion",
        "ph_min": 6.0, "ph_max": 7.0,
        "preferred_textures": ["loamy", "sandy-loam"],
        "preferred_drainage": ["good", "moderate"],
        "moisture_tolerance": ["moderate"],
        "notes": "Needs well-drained, loose soil for bulb development.",
    },
    {
        "name": "Spinach",
        "ph_min": 6.5, "ph_max": 7.5,
        "preferred_textures": ["loamy", "sandy-loam", "silty"],
        "preferred_drainage": ["moderate", "good"],
        "moisture_tolerance": ["moderate"],
        "notes": "Prefers neutral to slightly alkaline soil. Cold-tolerant.",
    },
    {
        "name": "Blueberry",
        "ph_min": 4.5, "ph_max": 5.5,
        "preferred_textures": ["sandy", "sandy-loam"],
        "preferred_drainage": ["good"],
        "moisture_tolerance": ["moderate"],
        "notes": "Requires distinctly acidic soil. Most other crops cannot grow at this pH.",
    },
    {
        "name": "Cotton",
        "ph_min": 5.8, "ph_max": 7.0,
        "preferred_textures": ["loamy", "clay-loam", "silty"],
        "preferred_drainage": ["moderate", "good"],
        "moisture_tolerance": ["moderate"],
        "notes": "Requires a long warm growing season. Moderate drought tolerance.",
    },
    {
        "name": "Mung Bean",
        "ph_min": 6.2, "ph_max": 7.2,
        "preferred_textures": ["sandy-loam", "loamy"],
        "preferred_drainage": ["good", "moderate"],
        "moisture_tolerance": ["moderate", "dry"],
        "notes": "Tolerates short dry spells. Good for summer cropping.",
    },
]


def _ph_compatibility(crop: dict, ph_estimate: PHEstimate) -> str:
    """Check if the estimated pH range overlaps with crop's tolerance."""
    crop_min = crop["ph_min"]
    crop_max = crop["ph_max"]
    est_min = ph_estimate.min
    est_max = ph_estimate.max

    # Overlap check
    if est_max < crop_min or est_min > crop_max:
        return "incompatible"
    # Full overlap
    if est_min >= crop_min and est_max <= crop_max:
        return "excellent"
    # Partial overlap
    overlap = min(est_max, crop_max) - max(est_min, crop_min)
    range_size = est_max - est_min
    if range_size > 0 and overlap / range_size > 0.5:
        return "good"
    return "marginal"


def _texture_score(crop: dict, features: SoilFeatures) -> float:
    """Score texture compatibility (0–1)."""
    if features.texture == "unknown":
        return 0.5
    if features.texture in crop["preferred_textures"]:
        return 1.0
    # Adjacent textures
    adjacent = {
        "sandy": ["sandy-loam"],
        "sandy-loam": ["sandy", "loamy"],
        "loamy": ["sandy-loam", "clay-loam", "silty"],
        "silty": ["loamy", "clay-loam"],
        "clay-loam": ["loamy", "silty", "clay"],
        "clay": ["clay-loam"],
    }
    if any(t in crop["preferred_textures"] for t in adjacent.get(features.texture, [])):
        return 0.6
    return 0.2


def _drainage_score(crop: dict, features: SoilFeatures) -> float:
    """Score drainage compatibility (0–1)."""
    if features.drainage == "unknown":
        return 0.5
    if features.drainage in crop["preferred_drainage"]:
        return 1.0
    return 0.2


def recommend_crops(
    features: SoilFeatures,
    ph_estimate: PHEstimate,
    weather: WeatherData,
    target_crop: str = "unknown",
) -> RecommendationResult:
    """
    Generate crop recommendations from soil features, pH estimate, and weather.

    Returns a RecommendationResult with suitable crops, crops to avoid,
    and a prioritised action plan.
    """
    scored_crops = []

    for crop in CROP_DB:
        ph_compat = _ph_compatibility(crop, ph_estimate)

        if ph_compat == "incompatible":
            continue  # Skip entirely incompatible crops

        texture_s = _texture_score(crop, features)
        drainage_s = _drainage_score(crop, features)
        ph_scores = {"excellent": 1.0, "good": 0.75, "marginal": 0.4}
        ph_s = ph_scores.get(ph_compat, 0.0)

        total_score = (ph_s * 0.5) + (texture_s * 0.3) + (drainage_s * 0.2)
        scored_crops.append((total_score, ph_compat, crop))

    # Sort by score descending
    scored_crops.sort(key=lambda x: x[0], reverse=True)

    # Crops that are incompatible
    incompatible_names = [
        c["name"] for c in CROP_DB
        if _ph_compatibility(c, ph_estimate) == "incompatible"
    ]

    # Build recommendations (top 5)
    recommendations: List[CropRecommendation] = []
    for score, ph_compat, crop in scored_crops[:5]:
        if score >= 0.5:
            suitability = "highly_suitable"
        elif score >= 0.35:
            suitability = "suitable"
        else:
            suitability = "marginal"

        # Texture/drainage note
        texture_note = ""
        if features.texture != "unknown" and features.texture not in crop["preferred_textures"]:
            texture_note = f" Note: {features.texture} texture is not ideal for {crop['name']}."

        drainage_note = ""
        if features.drainage != "unknown" and features.drainage not in crop["preferred_drainage"]:
            drainage_note = f" Poor drainage should be addressed before planting {crop['name']}."

        ph_note = (
            f"Estimated pH {ph_estimate.min}–{ph_estimate.max} is "
            + ("well within" if ph_compat == "excellent" else "partially within" if ph_compat == "good" else "at the edge of")
            + f" {crop['name']}'s preferred pH range ({crop['ph_min']}–{crop['ph_max']})."
        )

        weather_note = _weather_crop_note(crop, weather)

        reason = f"{crop['notes']}{texture_note}{drainage_note}"

        recommendations.append(CropRecommendation(
            crop_name=crop["name"],
            suitability=suitability,
            reason=reason,
            ph_compatibility_note=ph_note,
            weather_note=weather_note,
        ))

    # Highlight user's target crop if it's not already in list
    if target_crop and target_crop.lower() != "unknown":
        target_in_list = any(
            r.crop_name.lower() == target_crop.lower() for r in recommendations
        )
        if not target_in_list:
            # Try to find it in full DB and add a specific note
            for crop in CROP_DB:
                if crop["name"].lower() == target_crop.lower():
                    ph_compat = _ph_compatibility(crop, ph_estimate)
                    note = (
                        f"Your target crop ({crop['name']}) may be challenging with the estimated pH range "
                        f"({ph_estimate.min}–{ph_estimate.max}). Its preferred range is "
                        f"{crop['ph_min']}–{crop['ph_max']}. Confirm pH before proceeding."
                    )
                    recommendations.insert(0, CropRecommendation(
                        crop_name=crop["name"],
                        suitability="marginal",
                        reason=note,
                        ph_compatibility_note=f"pH compatibility: {ph_compat}",
                        weather_note=_weather_crop_note(crop, weather),
                    ))
                    break

    # Build action plan
    action_steps = _build_action_plan(features, ph_estimate, weather)

    # Limitations
    limitations = [
        "This recommendation is based on an AI-estimated pH — not a laboratory measurement.",
        "Local soil conditions may vary significantly even within a small area.",
        "Variety selection within a crop type matters; consult local agricultural extension.",
    ]
    if ph_estimate.confidence < 0.5:
        limitations.insert(0, "Low model confidence: additional soil information would improve recommendations.")

    return RecommendationResult(
        suitable_crops=recommendations,
        crops_to_avoid=incompatible_names[:5],
        action_plan=action_steps,
        limitations=limitations,
    )


def _weather_crop_note(crop: dict, weather: WeatherData) -> str:
    if weather.error:
        return ""
    notes = []
    if weather.precipitation_probability is not None:
        if weather.precipitation_probability > 70 and "good" in crop["preferred_drainage"]:
            notes.append("Heavy rain expected — monitor drainage closely.")
        elif weather.precipitation_probability < 20 and "wet" in crop.get("moisture_tolerance", []):
            notes.append("Dry conditions forecast — irrigation may be needed.")
    if weather.temperature_celsius is not None and weather.temperature_celsius > 35:
        notes.append("High temperatures — consider heat-tolerant varieties.")
    return " ".join(notes)


def _build_action_plan(
    features: SoilFeatures,
    ph_estimate: PHEstimate,
    weather: WeatherData,
) -> List[ActionStep]:
    steps = []
    step_num = 1

    # Always: confirm pH
    steps.append(ActionStep(
        step_number=step_num,
        action=(
            "Confirm soil pH using a certified soil testing kit or laboratory. "
            "This AI estimate should NOT be used as the sole basis for major soil amendments."
        ),
        priority="high",
    ))
    step_num += 1

    # Drainage
    if features.drainage == "poor":
        steps.append(ActionStep(
            step_number=step_num,
            action="Improve soil drainage through raised beds, sub-surface drains, or organic matter addition before planting.",
            priority="high",
        ))
        step_num += 1

    # Weather-driven step
    if not weather.error:
        if weather.precipitation_probability and weather.precipitation_probability > 60:
            steps.append(ActionStep(
                step_number=step_num,
                action="Heavy rain is expected. Delay any fertilizer or amendment applications until after the rain passes.",
                priority="high",
            ))
        elif weather.precipitation_probability and weather.precipitation_probability < 20:
            steps.append(ActionStep(
                step_number=step_num,
                action="Dry conditions expected. Plan irrigation and consider mulching to retain soil moisture.",
                priority="medium",
            ))
        step_num += 1

    # Organic matter
    if features.organic_matter == "low":
        steps.append(ActionStep(
            step_number=step_num,
            action="Incorporate compost or organic matter to improve soil structure and nutrient availability.",
            priority="medium",
        ))
        step_num += 1

    # General monitoring
    steps.append(ActionStep(
        step_number=step_num,
        action="Monitor crops during the first 4 weeks after planting and adjust water/nutrients based on plant response.",
        priority="medium",
    ))
    step_num += 1

    steps.append(ActionStep(
        step_number=step_num,
        action="Re-evaluate soil conditions after significant rainfall events or any applied soil amendments.",
        priority="low",
    ))

    return steps
