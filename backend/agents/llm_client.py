"""
SoilSense AI — LLM client with Gemini-first, OpenAI fallback.

Architecture:
  - Tries Google Gemini (gemini-1.5-flash) first.
  - Falls back to OpenAI (gpt-4o-mini) if Gemini key is absent or call fails.
  - Both providers expose the same interface: chat_completion(messages) -> str
"""
from __future__ import annotations
import json
import logging
import os
from typing import List, Optional

logger = logging.getLogger("soilsense.llm")


def _get_provider() -> str:
    """Determine which LLM provider to use based on available env vars."""
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "none"


async def chat_completion(
    messages: List[dict],
    system_prompt: str = "",
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """
    Send messages to the configured LLM provider and return the text response.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        system_prompt: System/context instructions.
        temperature: Sampling temperature (lower = more deterministic).
        json_mode: If True, instructs the model to return valid JSON.

    Returns:
        String response from the model.

    Raises:
        RuntimeError: If no LLM provider is configured and no fallback is possible.
    """
    provider = _get_provider()
    logger.info("LLM provider selected: %s", provider)

    if provider == "gemini":
        try:
            return await _gemini_completion(messages, system_prompt, temperature, json_mode)
        except Exception as exc:
            logger.warning("Gemini call failed (%s), trying OpenAI fallback…", exc)
            if os.getenv("OPENAI_API_KEY"):
                try:
                    return await _openai_completion(messages, system_prompt, temperature, json_mode)
                except Exception as oe:
                    logger.warning("OpenAI fallback also failed (%s)", oe)
            raise

    if provider == "openai":
        try:
            return await _openai_completion(messages, system_prompt, temperature, json_mode)
        except Exception as oe:
            logger.warning("OpenAI call failed (%s), trying Gemini fallback…", oe)
            if os.getenv("GEMINI_API_KEY"):
                return await _gemini_completion(messages, system_prompt, temperature, json_mode)
            raise

    raise RuntimeError(
        "No LLM provider configured. Set GEMINI_API_KEY or OPENAI_API_KEY in your .env file."
    )


# ─────────────────────────────────────────────────────────────
# Gemini Implementation
# ─────────────────────────────────────────────────────────────

async def _gemini_completion(
    messages: List[dict],
    system_prompt: str,
    temperature: float,
    json_mode: bool,
) -> str:
    import google.generativeai as genai  # lazy import — only if provider active

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    generation_config = genai.types.GenerationConfig(
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )

    candidate_models = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]
    last_err = None

    # Convert messages to Gemini format
    gemini_messages = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        gemini_messages.append({"role": role, "parts": [m["content"]]})

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt or None,
                generation_config=generation_config,
            )
            response = await model.generate_content_async(gemini_messages)
            text = response.text
            logger.debug("Gemini (%s) response (first 200 chars): %s", model_name, text[:200])
            return text
        except Exception as exc:
            last_err = exc
            logger.warning("Gemini model %s call failed: %s", model_name, exc)
            continue

    raise last_err or RuntimeError("All Gemini candidate models failed.")


# ─────────────────────────────────────────────────────────────
# OpenAI Implementation
# ─────────────────────────────────────────────────────────────

async def _openai_completion(
    messages: List[dict],
    system_prompt: str,
    temperature: float,
    json_mode: bool,
) -> str:
    from openai import AsyncOpenAI  # lazy import

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    kwargs: dict = {
        "model": "gpt-4o-mini",
        "messages": full_messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    text = response.choices[0].message.content or ""
    logger.debug("OpenAI response (first 200 chars): %s", text[:200])
    return text


def get_active_provider_name() -> str:
    """Return human-readable name of the configured LLM provider."""
    provider = _get_provider()
    names = {
        "gemini": "Google Gemini (gemini-2.5-flash)",
        "openai": "OpenAI (gpt-4o-mini)",
        "none": "None — configure GEMINI_API_KEY or OPENAI_API_KEY",
    }
    return names[provider]

