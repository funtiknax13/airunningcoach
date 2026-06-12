"""Strava API: OAuth token refresh, activity fetch, type mapping."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE  = "https://www.strava.com/api/v3"

# Strava activity type → наш тип
STRAVA_TYPE_MAP: dict[str, str] = {
    "Run":             "run",
    "TrailRun":        "run",
    "VirtualRun":      "run",
    "Ride":            "ride",
    "VirtualRide":     "ride",
    "MountainBikeRide":"ride",
    "GravelRide":      "ride",
    "EBikeRide":       "ride",
    "EMountainBikeRide":"ride",
    "Velomobile":      "ride",
    "Handcycle":       "ride",
    "Walk":            "walk",
    "Hike":            "hike",
    "Snowshoe":        "hike",
    "Swim":            "swim",
    "WeightTraining":  "strength",
    "CrossFit":        "strength",
    "Workout":         "workout",
    "Elliptical":      "workout",
    "StairStepper":    "workout",
    "Yoga":            "workout",
    "Pilates":         "workout",
    "Rowing":          "workout",
    "Kayaking":        "workout",
    "StandUpPaddling": "workout",
    "Surfing":         "workout",
    "Kitesurf":        "workout",
    "Windsurf":        "workout",
    "Canoeing":        "workout",
    "Sail":            "workout",
    "Soccer":          "workout",
    "Tennis":          "workout",
    "Golf":            "workout",
    "RockClimbing":    "workout",
    "IceSkate":        "workout",
    "InlineSkate":     "workout",
    "AlpineSki":       "workout",
    "NordicSki":       "workout",
    "BackcountrySki":  "workout",
    "Snowboard":       "workout",
}


def map_strava_type(strava_type: str) -> str:
    return STRAVA_TYPE_MAP.get(strava_type, "other")


async def refresh_token_if_needed(user) -> Optional[str]:
    """Возвращает актуальный access_token, обновляя его при необходимости."""
    if not user.strava_access_token:
        return None

    expires_at = user.strava_token_expires_at
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < expires_at - timedelta(minutes=5):
            return user.strava_access_token

    # Токен истёк — обновляем
    async with httpx.AsyncClient() as client:
        resp = await client.post(STRAVA_TOKEN_URL, data={
            "client_id":     settings.STRAVA_CLIENT_ID,
            "client_secret": settings.STRAVA_CLIENT_SECRET,
            "grant_type":    "refresh_token",
            "refresh_token": user.strava_refresh_token,
        })
    if resp.status_code != 200:
        logger.error("Strava token refresh failed: %s", resp.text)
        return None

    data = resp.json()
    user.strava_access_token   = data["access_token"]
    user.strava_refresh_token  = data["refresh_token"]
    user.strava_token_expires_at = datetime.fromtimestamp(
        data["expires_at"], tz=timezone.utc
    )
    return user.strava_access_token


async def fetch_activities(access_token: str, after: int, per_page: int = 200) -> list[dict]:
    """Получает активности после указанного Unix timestamp."""
    all_activities: list[dict] = []
    page = 1
    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(
                f"{STRAVA_API_BASE}/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"after": after, "per_page": per_page, "page": page},
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error("Strava fetch activities failed: %s", resp.text)
                break
            batch = resp.json()
            if not batch:
                break
            all_activities.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
    return all_activities


async def fetch_single_activity(access_token: str, strava_activity_id: int) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{STRAVA_API_BASE}/activities/{strava_activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
    if resp.status_code != 200:
        logger.error("Strava fetch activity %d failed: %s", strava_activity_id, resp.text)
        return None
    return resp.json()


def strava_activity_to_dict(a: dict) -> dict:
    """Конвертирует Strava summary activity в наш формат."""
    moving_sec  = a.get("moving_time") or a.get("elapsed_time") or 0
    distance_m  = a.get("distance") or 0
    distance_km = round(distance_m / 1000, 2)
    duration_min = round(moving_sec / 60, 2)
    pace = duration_min / distance_km if distance_km > 0 else 0

    start_date = a.get("start_date") or a.get("start_date_local")
    date = datetime.fromisoformat(start_date.replace("Z", "+00:00")) if start_date else datetime.now(timezone.utc)

    return {
        "strava_id":      str(a["id"]),
        "activity_type":  map_strava_type(a.get("type", "Workout")),
        "date":           date,
        "distance_km":    distance_km,
        "duration_min":   duration_min,
        "pace_min_per_km": round(pace, 2),
        "avg_heart_rate": a.get("average_heartrate"),
        "max_heart_rate": a.get("max_heartrate"),
        "avg_cadence":    None,
        "elevation_gain": a.get("total_elevation_gain"),
        "calories":       a.get("calories"),
        "notes":          a.get("name") or "",
        "source":         "strava",
    }
