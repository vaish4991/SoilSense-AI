"""
SoilSense AI — Soil Feature Extractor

Uses the configured LLM to convert a natural-language soil description into
a structured SoilFeatures object.  The LLM is used ONLY for language
understanding — it does NOT predict pH.

Prompt engineering guarantees JSON output with controlled enum values and
"unknown" for any field that cannot be reliably inferred.
"""
from __future__ import annotations
import json
import logging
import re
from typing import List, Optional

from backend.agents.llm_client import chat_completion
from backend.schemas.soil_schema import SoilFeatures, FollowUpQuestion, FollowUpResult

logger = logging.getLogger("soilsense.feature_extractor")

# ─────────────────────────────────────────────────────────────
# System prompt for feature extraction
# ─────────────────────────────────────────────────────────────
EXTRACTION_SYSTEM_PROMPT = """
You are a soil science assistant that extracts structured soil characteristics
from natural-language descriptions.

Your ONLY job is to output valid JSON that matches this exact schema:

{
  "soil_color": "<string>",
  "texture": "<sandy|loamy|clay|silty|clay-loam|sandy-loam|unknown>",
  "drainage": "<poor|moderate|good|unknown>",
  "moisture": "<dry|moderate|wet|unknown>",
  "organic_matter": "<low|moderate|high|unknown>",
  "soil_compaction": "<loose|moderate|compacted|unknown>",
  "water_retention": "<low|moderate|high|unknown>",
  "surface_deposits": "<string describing any salt, crust, etc. or 'none detected'>",
  "vegetation_observed": "<string or 'unknown'>",
  "location": "<string or 'unknown'>",
  "target_crop": "<string or 'unknown'>"
}

Rules:
- Only use the listed enum values for enum fields.
- Use "unknown" when information is NOT mentioned.
- Do NOT invent information that is not in the description.
- Do NOT produce a pH value — that is done by a separate ML model.
- Output ONLY the JSON object. No explanation, no markdown fences.

Inference rules you may apply:
- "sticky when wet, hard when dry, drains slowly" → texture: clay, drainage: poor, water_retention: high
- "gritty, drains quickly, feels sandy" → texture: sandy, drainage: good, water_retention: low
- "dark colour, earthworms present" → organic_matter: high
- "white crusty deposits on surface" → surface_deposits: "white salt-like deposits"
- "loose, crumbly" → soil_compaction: loose
""".strip()


async def extract_soil_features(
    description: str,
    location: str = "unknown",
    target_crop: str = "unknown",
    conversation_history: Optional[List[dict]] = None,
) -> SoilFeatures:
    """
    Parse a natural-language soil description into a SoilFeatures object.

    Args:
        description: The user's free-text soil description.
        location: User-provided location string.
        target_crop: Crop the user wants to grow.
        conversation_history: Previous chat turns for multi-turn context.

    Returns:
        SoilFeatures with "unknown" for undetectable fields.
    """
    messages: List[dict] = []

    # Include conversation history for multi-turn continuity
    if conversation_history:
        messages.extend(conversation_history[-6:])  # last 3 exchanges max

    user_message = (
        f"Extract soil features from this description:\n\n"
        f"Description: {description}\n"
        f"Location: {location}\n"
        f"Target crop: {target_crop}"
    )
    messages.append({"role": "user", "content": user_message})

    logger.info("Extracting soil features from description (len=%d)", len(description))

    try:
        raw_response = await chat_completion(
            messages=messages,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.1,
            json_mode=True,
        )
        features = _parse_features(raw_response, description, location, target_crop)
    except Exception as exc:
        logger.warning("LLM feature extraction failed (%s), falling back to heuristic parsing", exc)
        features = _extract_features_heuristics(description, location, target_crop)

    # If all core features ended up unknown, try heuristic enrichment
    if features.texture == "unknown" and features.drainage == "unknown":
        heuristic_feat = _extract_features_heuristics(description, location, target_crop)
        if heuristic_feat.texture != "unknown":
            features.texture = heuristic_feat.texture
        if heuristic_feat.drainage != "unknown":
            features.drainage = heuristic_feat.drainage
        if features.soil_color == "unknown" and heuristic_feat.soil_color != "unknown":
            features.soil_color = heuristic_feat.soil_color

    logger.info("Features extracted: texture=%s drainage=%s moisture=%s",
                features.texture, features.drainage, features.moisture)
    return features


def _extract_features_heuristics(
    description: str,
    location: str,
    target_crop: str,
) -> SoilFeatures:
    """Rule-based heuristic extractor when LLM is unavailable or fails."""
    text = description.lower()

    # Texture
    texture = "unknown"
    if "clay-loam" in text or "clay loam" in text:
        texture = "clay-loam"
    elif "sandy-loam" in text or "sandy loam" in text:
        texture = "sandy-loam"
    elif "clay" in text or "sticky" in text or "heavy" in text:
        texture = "clay"
    elif "sand" in text or "gritty" in text:
        texture = "sandy"
    elif "silt" in text or "powdery" in text or "floury" in text:
        texture = "silty"
    elif "loam" in text or "crumbly" in text or "rich soil" in text:
        texture = "loamy"

    # Drainage
    drainage = "unknown"
    if any(w in text for w in ["slow", "poor", "waterlog", "puddle", "standing water", "ponding", "swamp"]):
        drainage = "poor"
    elif any(w in text for w in ["fast", "quick", "rapid", "drains fast", "leach", "well-drained", "well drained", "good drainage", "good"]):
        drainage = "good"
    elif any(w in text for w in ["moderate", "normal", "medium"]):
        drainage = "moderate"

    # Moisture
    moisture = "unknown"
    if any(w in text for w in ["dry", "parched", "arid", "dust", "hard-baked"]):
        moisture = "dry"
    elif any(w in text for w in ["wet", "soggy", "waterlogged", "soaked", "damp"]):
        moisture = "wet"
    elif any(w in text for w in ["moist", "moderate moisture", "balanced"]):
        moisture = "moderate"

    # Organic matter
    organic_matter = "unknown"
    if any(w in text for w in ["earthworm", "worm", "compost", "manure", "humus", "rich", "black soil", "dark soil"]):
        organic_matter = "high"
    elif any(w in text for w in ["pale", "depleted", "poor", "rocky", "infertile", "chalky"]):
        organic_matter = "low"
    elif any(w in text for w in ["some organic", "moderate"]):
        organic_matter = "moderate"

    # Soil color
    color = "unknown"
    for c in ["black", "dark brown", "reddish-brown", "red", "yellow", "brown", "pale", "gray", "grey", "white"]:
        if c in text:
            color = c
            break

    # Compaction
    compaction = "unknown"
    if any(w in text for w in ["compact", "hard", "packed", "dense", "stiff"]):
        compaction = "compacted"
    elif any(w in text for w in ["loose", "crumbly", "fluffy", "friable"]):
        compaction = "loose"
    elif "moderate" in text:
        compaction = "moderate"

    # Surface deposits
    surface_deposits = "none detected"
    if any(w in text for w in ["salt", "white crust", "white deposit", "crusty"]):
        surface_deposits = "white salt-like deposits"
    elif any(w in text for w in ["crack", "fissure"]):
        surface_deposits = "surface cracking observed"

    return SoilFeatures(
        soil_color=color,
        texture=texture,
        drainage=drainage,
        moisture=moisture,
        organic_matter=organic_matter,
        soil_compaction=compaction,
        water_retention="high" if texture == "clay" else ("low" if texture == "sandy" else "moderate"),
        surface_deposits=surface_deposits,
        vegetation_observed="unknown",
        location=location if location and location != "unknown" else "unknown",
        target_crop=target_crop if target_crop and target_crop != "unknown" else "unknown",
        raw_description=description,
    )


def _parse_features(
    raw: str,
    description: str,
    location: str,
    target_crop: str,
) -> SoilFeatures:
    """Parse LLM JSON output into SoilFeatures with graceful fallbacks."""
    try:
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse LLM JSON response: %s | raw: %s", exc, raw[:300])
        data = {}

    # Override location and target_crop from explicit user inputs
    data["location"] = location if location and location != "unknown" else data.get("location", "unknown")
    data["target_crop"] = target_crop if target_crop and target_crop != "unknown" else data.get("target_crop", "unknown")
    data["raw_description"] = description

    # Safely build SoilFeatures, defaulting unknown for bad enum values
    safe_data = {}
    enum_fields = {
        "texture": ["sandy", "loamy", "clay", "silty", "clay-loam", "sandy-loam", "unknown"],
        "drainage": ["poor", "moderate", "good", "unknown"],
        "moisture": ["dry", "moderate", "wet", "unknown"],
        "organic_matter": ["low", "moderate", "high", "unknown"],
        "soil_compaction": ["loose", "moderate", "compacted", "unknown"],
        "water_retention": ["low", "moderate", "high", "unknown"],
    }
    for field, allowed in enum_fields.items():
        val = str(data.get(field, "unknown")).lower()
        safe_data[field] = val if val in allowed else "unknown"

    # Agronomic physics inferences for compaction and water retention when texture is known
    tex = safe_data.get("texture", "unknown")
    if safe_data.get("water_retention") == "unknown":
        if tex in ("clay", "clay-loam"):
            safe_data["water_retention"] = "high"
        elif tex in ("sandy", "sandy-loam"):
            safe_data["water_retention"] = "low"
        elif tex in ("loamy", "silty"):
            safe_data["water_retention"] = "moderate"

    if safe_data.get("soil_compaction") == "unknown":
        if tex in ("sandy", "sandy-loam"):
            safe_data["soil_compaction"] = "loose"
        elif tex in ("clay", "clay-loam"):
            safe_data["soil_compaction"] = "compacted"
        elif tex in ("loamy", "silty"):
            safe_data["soil_compaction"] = "moderate"

    for str_field in ["soil_color", "surface_deposits", "vegetation_observed", "location", "target_crop", "raw_description"]:
        safe_data[str_field] = str(data.get(str_field, "unknown"))

    return SoilFeatures(**safe_data)


# ─────────────────────────────────────────────────────────────
# Follow-up question generator
# ─────────────────────────────────────────────────────────────

FOLLOW_UP_SYSTEM_PROMPT = """
You are a soil science assistant. Given a partially-filled soil feature profile,
decide whether you need more information to make a confident soil pH estimate.

If more information is needed, return JSON:
{
  "needs_more_info": true,
  "questions": [
    {"question": "...", "reason": "..."},
    ...
  ]
}

If you have enough information, return:
{
  "needs_more_info": false,
  "questions": []
}

Rules:
- Ask at most 3 questions at a time.
- Only ask questions that will materially improve the prediction.
- Do NOT ask redundant questions if the information is already present.
- If texture, drainage, and at least one of (colour, moisture, organic_matter) are known, you likely have enough.
- Phrase questions conversationally for a non-expert farmer/user.
- Output ONLY the JSON object.
""".strip()


async def check_for_missing_info(features: SoilFeatures) -> FollowUpResult:
    """
    Determine whether the current feature set is sufficient for a pH estimate,
    and generate targeted follow-up questions if not.
    """
    known_count = sum(
        1 for v in [features.texture, features.drainage, features.moisture,
                    features.organic_matter, features.soil_color]
        if v != "unknown"
    )

    # Fast path: if we have at least 3 meaningful features, skip LLM check
    if known_count >= 3:
        logger.info("Sufficient features detected (%d/5 core fields known) — skipping follow-up", known_count)
        return FollowUpResult(
            needs_more_info=False,
            questions=[],
            available_features=features,
        )

    feature_summary = features.model_dump()
    messages = [{
        "role": "user",
        "content": f"Soil features detected so far:\n{json.dumps(feature_summary, indent=2)}\n\nDo you need more info?",
    }]

    raw = await chat_completion(
        messages=messages,
        system_prompt=FOLLOW_UP_SYSTEM_PROMPT,
        temperature=0.1,
        json_mode=True,
    )

    try:
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        data = json.loads(cleaned)
        questions = [
            FollowUpQuestion(question=q["question"], reason=q.get("reason", ""))
            for q in data.get("questions", [])
        ]
        return FollowUpResult(
            needs_more_info=data.get("needs_more_info", False),
            questions=questions,
            available_features=features,
        )
    except Exception as exc:
        logger.warning("Follow-up parsing failed: %s", exc)
        return FollowUpResult(
            needs_more_info=False,
            questions=[],
            available_features=features,
        )
