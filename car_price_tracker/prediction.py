"""Transparent wait-or-buy scoring for tracked Clutch vehicles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _days_between(start: datetime | None, end: datetime | None) -> int:
    if not start or not end:
        return 0
    return max(0, (end - start).days)


def _price_points(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points = [
        item
        for item in observations
        if isinstance(item.get("price"), int) and item.get("check_status", "available") == "available"
    ]
    return sorted(points, key=lambda item: item.get("checked_at") or "")


def _last_drop_days(points: list[dict[str, Any]], now: datetime) -> int | None:
    previous_price: int | None = None
    last_drop_at: datetime | None = None
    for item in points:
        price = item.get("price")
        if previous_price is not None and isinstance(price, int) and price < previous_price:
            last_drop_at = _parse_time(item.get("checked_at"))
        if isinstance(price, int):
            previous_price = price
    return _days_between(last_drop_at, now) if last_drop_at else None


def _count_drops(points: list[dict[str, Any]]) -> int:
    count = 0
    previous_price: int | None = None
    for item in points:
        price = item.get("price")
        if previous_price is not None and isinstance(price, int) and price < previous_price:
            count += 1
        if isinstance(price, int):
            previous_price = price
    return count


def build_prediction(
    observations: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a conservative rule-based recommendation.

    This is intentionally explainable. It is not a trained model yet; it gives
    us a stable baseline while we collect enough history to validate patterns.
    """

    now = now or datetime.now(timezone.utc)
    points = _price_points(observations)
    if not points:
        return {
            "recommendation": "watch",
            "score": 50,
            "confidence": "low",
            "price_drop_probability_7d": 0.15,
            "price_drop_probability_14d": 0.25,
            "expected_drop_min": 0,
            "expected_drop_max": 0,
            "reasons": ["No usable price history yet."],
            "features": {"observation_count": 0},
        }

    latest = points[-1]
    first_at = _parse_time(points[0].get("checked_at"))
    latest_at = _parse_time(latest.get("checked_at")) or now
    tracking_days = _days_between(first_at, latest_at)
    prices = [item["price"] for item in points]
    latest_price = prices[-1]
    min_price = min(prices)
    max_price = max(prices)
    total_drop = max_price - latest_price
    drop_count = _count_drops(points)
    last_drop_days = _last_drop_days(points, latest_at)
    stable_days = last_drop_days if last_drop_days is not None else tracking_days
    latest_status = latest.get("purchase_status") or "unknown"

    wait_score = 35
    reasons: list[str] = []

    if len(points) < 4:
        wait_score += 8
        reasons.append("History is still thin, so the safest move is to keep watching.")
    if tracking_days >= 14 and stable_days >= 10:
        wait_score += 22
        reasons.append("Price has been stable for a while, which can precede a markdown.")
    if drop_count == 0 and tracking_days >= 10:
        wait_score += 16
        reasons.append("No recorded price drop yet during the tracking window.")
    if latest_price > min_price:
        wait_score += 12
        reasons.append("Current price is above the observed low.")
    if latest_price == min_price and drop_count > 0 and tracking_days >= 7:
        wait_score -= 18
        reasons.append("Current price is already at the observed low.")
    if total_drop >= 1000:
        wait_score -= 8
        reasons.append("It has already taken a meaningful markdown.")
    if latest_status in {"sale_pending", "coming_soon"}:
        wait_score -= 20
        reasons.append(f"Listing status is {latest_status}; waiting may mean losing the car.")
    if latest_status == "unavailable":
        wait_score = 50
        reasons.append("Listing is unavailable; preserve history and monitor for relisting.")

    wait_score = max(0, min(100, wait_score))
    probability_7d = round(max(0.05, min(0.85, wait_score / 125)), 2)
    probability_14d = round(max(probability_7d, min(0.92, wait_score / 100)), 2)

    if len(points) < 3:
        recommendation = "watch_closely"
    elif wait_score >= 70:
        recommendation = "wait"
    elif wait_score >= 55:
        recommendation = "watch_closely"
    elif latest_price == min_price:
        recommendation = "buy_now"
    else:
        recommendation = "negotiate"

    expected_drop_min = 0 if recommendation == "buy_now" else 200
    expected_drop_max = 0 if recommendation == "buy_now" else min(1200, max(300, round(latest_price * 0.025 / 50) * 50))
    confidence = "low" if len(points) < 7 else "medium" if tracking_days < 30 else "high"

    if not reasons:
        reasons.append("Price pattern is neutral; keep watching for a clearer signal.")

    return {
        "recommendation": recommendation,
        "score": wait_score,
        "confidence": confidence,
        "price_drop_probability_7d": probability_7d,
        "price_drop_probability_14d": probability_14d,
        "expected_drop_min": expected_drop_min,
        "expected_drop_max": expected_drop_max,
        "reasons": reasons[:4],
        "features": {
            "observation_count": len(points),
            "tracking_days": tracking_days,
            "latest_price": latest_price,
            "min_price": min_price,
            "max_price": max_price,
            "drop_count": drop_count,
            "last_drop_days": last_drop_days,
            "stable_days": stable_days,
            "latest_status": latest_status,
        },
    }
