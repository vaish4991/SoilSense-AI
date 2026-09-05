"""
SoilSense AI — Weather Service (Open-Meteo, no API key required)

Flow:
  1. Geocode location string → (lat, lon) via Open-Meteo Geocoding API
  2. Fetch current weather + 7-day forecast via Open-Meteo Forecast API
  3. Interpret weather data for soil/crop recommendations

Error handling:
  - Network timeout → returns WeatherData with error field populated
  - Invalid location → returns WeatherData with error message
  - API error → graceful degradation (analysis continues without weather)
"""
from __future__ import annotations
import logging
from typing import Optional, Tuple

import httpx

from backend.schemas.soil_schema import WeatherData

logger = logging.getLogger("soilsense.weather")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10.0  # seconds


async def get_weather(location: str) -> WeatherData:
    """
    Fetch weather data for the given location string.

    Returns a WeatherData object. If any step fails, returns a WeatherData
    with error populated but other fields still present where possible.
    """
    if not location or location.strip().lower() in ("unknown", ""):
        logger.warning("No valid location provided for weather lookup")
        return WeatherData(
            location_name="Unknown",
            error="No location provided. Enter a city or region for weather-based recommendations.",
        )

    try:
        lat, lon, resolved_name = await _geocode(location)
    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", location, exc)
        return WeatherData(
            location_name=location,
            error=f"Could not resolve location '{location}'. Weather data unavailable.",
        )

    try:
        weather = await _fetch_forecast(lat, lon, resolved_name)
        logger.info("Weather fetched for %s (%.2f, %.2f)", resolved_name, lat, lon)
        return weather
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)
        return WeatherData(
            location_name=resolved_name,
            error="Weather API temporarily unavailable. Soil analysis continues without weather data.",
        )


async def _geocode(location: str) -> Tuple[float, float, str]:
    """
    Convert a location string to (latitude, longitude, resolved_name).

    Raises:
        ValueError: If the location cannot be resolved.
        httpx.TimeoutException: If the request times out.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            GEOCODING_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        raise ValueError(f"Location not found: {location}")

    top = results[0]
    lat = float(top["latitude"])
    lon = float(top["longitude"])
    name_parts = [top.get("name", location)]
    if top.get("country"):
        name_parts.append(top["country"])
    resolved_name = ", ".join(name_parts)

    return lat, lon, resolved_name


async def _fetch_forecast(lat: float, lon: float, location_name: str) -> WeatherData:
    """Fetch current weather and 3-day forecast from Open-Meteo."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation",
                    "weather_code",
                ],
                "daily": [
                    "precipitation_sum",
                    "precipitation_probability_max",
                    "temperature_2m_max",
                    "temperature_2m_min",
                ],
                "forecast_days": 7,
                "timezone": "auto",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    precip_now = current.get("precipitation", 0.0)
    weather_code = current.get("weather_code", 0)

    # 7-day totals
    daily_precip = daily.get("precipitation_sum", [])
    precip_7d_total = sum(p for p in daily_precip if p is not None)
    precip_prob = daily.get("precipitation_probability_max", [None])
    max_precip_prob = max((p for p in precip_prob if p is not None), default=None)

    # Human-readable description
    description = _weather_code_to_description(weather_code)

    # Forecast summary
    forecast_summary = _build_forecast_summary(daily)

    # Soil/crop impact note
    impact_note = _build_impact_note(
        temp=temp,
        humidity=humidity,
        precip_now=precip_now,
        precip_7d_total=precip_7d_total,
        max_precip_prob=max_precip_prob,
    )

    return WeatherData(
        location_name=location_name,
        temperature_celsius=round(temp, 1) if temp is not None else None,
        humidity_percent=round(humidity, 1) if humidity is not None else None,
        precipitation_mm=round(precip_now, 2) if precip_now is not None else None,
        precipitation_probability=round(max_precip_prob, 1) if max_precip_prob is not None else None,
        weather_description=description,
        forecast_summary=forecast_summary,
        weather_impact_note=impact_note,
    )


def _weather_code_to_description(code: int) -> str:
    """Map WMO weather code to human-readable string."""
    descriptions = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Freezing fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm",
    }
    return descriptions.get(code, f"Weather code {code}")


def _build_forecast_summary(daily: dict) -> str:
    """Build a brief 7-day forecast summary string."""
    precip_sums = daily.get("precipitation_sum", [])
    precip_probs = daily.get("precipitation_probability_max", [])
    max_probs = [p for p in precip_probs if p is not None]
    total_precip = sum(p for p in precip_sums if p is not None)

    if not max_probs:
        return "Forecast data unavailable."

    avg_prob = sum(max_probs) / len(max_probs)

    if total_precip > 50:
        rain_str = f"Heavy rainfall expected ({total_precip:.0f} mm over 7 days)"
    elif total_precip > 15:
        rain_str = f"Moderate rainfall expected ({total_precip:.0f} mm over 7 days)"
    elif total_precip > 2:
        rain_str = f"Light rainfall expected ({total_precip:.0f} mm over 7 days)"
    else:
        rain_str = "Mostly dry conditions expected"

    return f"{rain_str}. Average precipitation probability: {avg_prob:.0f}%."


def _build_impact_note(
    temp: Optional[float],
    humidity: Optional[float],
    precip_now: Optional[float],
    precip_7d_total: float,
    max_precip_prob: Optional[float],
) -> str:
    """Generate a practical agronomic impact note based on weather data."""
    notes = []

    if precip_7d_total > 50:
        notes.append(
            "Heavy rainfall is expected over the next 7 days. "
            "Avoid applying soil amendments (lime, sulfur, fertilizers) immediately — "
            "rain may wash nutrients away before they can be absorbed."
        )
    elif precip_7d_total < 5:
        notes.append(
            "Dry conditions are expected. Consider irrigation planning and "
            "moisture-retention practices such as mulching to preserve soil moisture."
        )
    else:
        notes.append(
            "Moderate rainfall is expected, which is generally favourable for soil "
            "amendment absorption and plant establishment."
        )

    if temp is not None:
        if temp > 35:
            notes.append(
                f"Current temperature is high ({temp:.1f}°C). "
                "Heat stress may reduce seedling establishment; consider shade nets or delayed planting."
            )
        elif temp < 10:
            notes.append(
                f"Current temperature is low ({temp:.1f}°C). "
                "Germination and root activity may be slower than optimal."
            )

    if humidity is not None and humidity > 80:
        notes.append(
            f"High humidity ({humidity:.0f}%) increases the risk of fungal diseases. "
            "Ensure adequate plant spacing and airflow."
        )

    return " ".join(notes) if notes else "Weather conditions appear favourable for general soil management."
