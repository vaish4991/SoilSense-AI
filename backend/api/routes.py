"""
SoilSense AI — FastAPI route definitions

Endpoints:
  GET  /api/health           — service health + model status
  POST /api/analyze-soil     — full soil analysis pipeline
  POST /api/soil/follow-up   — check if more info is needed, return questions
  POST /api/chat             — multi-turn conversational interface
"""
from __future__ import annotations
import logging
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.agents.soil_agent import run_soil_analysis, check_if_followup_needed
from backend.agents.llm_client import chat_completion, get_active_provider_name
from backend.ml.predict import is_model_loaded, get_model_metadata
from backend.schemas.soil_schema import (
    AnalyzeSoilRequest,
    SoilAnalysisResponse,
    ChatRequest,
    HealthResponse,
    FollowUpResult,
)

router = APIRouter(prefix="/api")
logger = logging.getLogger("soilsense.routes")

CHAT_SYSTEM_PROMPT = """
You are SoilSense AI, an expert soil analysis assistant.
Help users understand their soil through friendly, educational conversation.
Ask targeted questions to understand soil texture, drainage, colour, moisture, and crop goals.
When you have enough information, say: "I now have enough information to analyse your soil — click Analyse My Soil to proceed."
Do NOT invent pH values. Explain that pH is estimated by an ML model from their descriptions.
Keep responses concise (under 120 words).
""".strip()


# ── Health ────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        ml_model_loaded=is_model_loaded(),
        llm_provider=get_active_provider_name(),
    )


# ── Full Soil Analysis ─────────────────────────────────────────

@router.post("/analyze-soil", response_model=SoilAnalysisResponse)
async def analyze_soil(request: AnalyzeSoilRequest):
    """
    Full soil analysis pipeline.

    Accepts a natural-language description, location, and optional target crop.
    Returns a complete soil intelligence report including pH estimate,
    weather data, and crop recommendations.
    """
    logger.info(
        "POST /api/analyze-soil | location=%s | crop=%s | desc=%s…",
        request.location, request.target_crop, request.description[:60],
    )

    try:
        result = await run_soil_analysis(request)
        logger.info("Analysis complete.")
        return result
    except RuntimeError as exc:
        # LLM not configured
        logger.error("LLM configuration error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Soil analysis failed. Please try again or contact support.",
        )


# ── Follow-up Questions ────────────────────────────────────────

@router.post("/soil/follow-up", response_model=FollowUpResult)
async def soil_follow_up(request: AnalyzeSoilRequest):
    """
    Check whether the current soil description has enough information
    for a confident pH estimate. Returns follow-up questions if needed.
    """
    logger.info("POST /api/soil/follow-up")
    try:
        result = await check_if_followup_needed(request)
        return result
    except Exception as exc:
        logger.error("Follow-up check failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not evaluate soil description.")


# ── Multi-turn Chat ────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Multi-turn conversational interface for soil Q&A.
    Maintains context through the message history.
    """
    logger.info("POST /api/chat | messages=%d", len(request.messages))

    if not request.messages:
        raise HTTPException(status_code=400, detail="Message list cannot be empty.")

    # Convert to LLM message format
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        reply = await chat_completion(
            messages=messages,
            system_prompt=CHAT_SYSTEM_PROMPT,
            temperature=0.5,
        )
        return {"reply": reply.strip()}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Chat failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Chat service temporarily unavailable. Please try again.",
        )
