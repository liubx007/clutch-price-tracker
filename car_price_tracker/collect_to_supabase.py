#!/usr/bin/env python3
"""Collect Clutch vehicle prices into Supabase/Postgres via REST."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .prediction import build_prediction
    from .track_clutch_price import API_BASE, fetch_vehicle, observation_from_vehicle, unavailable_observation
except ImportError:  # pragma: no cover - supports direct script execution
    from prediction import build_prediction
    from track_clutch_price import API_BASE, fetch_vehicle, observation_from_vehicle, unavailable_observation


DEFAULT_LOCATION_ID = "409eb95b-0ab4-4763-8316-65ca1d2ab9a3"  # Halifax
DEFAULT_SEGMENT_FILE = "car_price_tracker/config/tracked_segments.json"
DEFAULT_SEED_VEHICLE_FILE = "car_price_tracker/config/seed_vehicle_ids.json"


class SupabaseRest:
    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any | None = None,
        query: dict[str, str] | None = None,
        prefer: str | None = None,
    ) -> Any:
        qs = f"?{urllib.parse.urlencode(query)}" if query else ""
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        url = f"{self.url}/rest/v1/{path}{qs}"
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode("utf-8", errors="replace")
                return json.loads(text) if text.strip() else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase REST {method} {path} failed with HTTP {exc.code}: {body[:1000]}") from exc

    def upsert(self, table: str, rows: list[dict[str, Any]], *, conflict: str) -> Any:
        if not rows:
            return None
        return self.request(
            "POST",
            table,
            body=normalize_rows_for_postgrest(rows),
            query={"on_conflict": conflict},
            prefer="resolution=merge-duplicates,return=representation",
        )

    def insert(self, table: str, rows: list[dict[str, Any]]) -> Any:
        if not rows:
            return None
        return self.request("POST", table, body=normalize_rows_for_postgrest(rows), prefer="return=minimal")

    def get_recent_observations(self, vehicle_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.request(
            "GET",
            "price_observations",
            query={
                "vehicle_id": f"eq.{vehicle_id}",
                "select": "checked_at,price,admin_fee,mileage,purchase_status,check_status,website_state,current_disposition",
                "order": "checked_at.asc",
                "limit": str(limit),
            },
        )
        return rows or []


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_rows_for_postgrest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PostgREST bulk inserts require every object in the JSON array to share keys."""
    keys = sorted({key for row in rows for key in row})
    return [{key: row.get(key) for key in keys} for row in rows]


def extract_vehicle_ids(payload: Any) -> list[int]:
    ids: set[int] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            candidate = value.get("id") or value.get("vehicleId") or value.get("vehicle_id")
            if isinstance(candidate, int):
                ids.add(candidate)
            elif isinstance(candidate, str) and candidate.isdigit():
                ids.add(int(candidate))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return sorted(ids)


def api_get_json(path: str, *, params: dict[str, Any] | None = None, retries: int = 4, retry_delay: int = 12) -> Any:
    query = f"?{urllib.parse.urlencode(params or {}, doseq=True)}" if params else ""
    request = urllib.request.Request(
        f"{API_BASE}{path}{query}",
        headers={
            "Accept": "application/json",
            "Accept-Language": "en-CA,en;q=0.9",
            "Origin": "https://www.clutch.ca",
            "Referer": "https://www.clutch.ca/cars",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        },
    )
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
                if response.status == 202 or not text.strip():
                    raise RuntimeError(f"Clutch API returned HTTP {response.status} with an empty body.")
                return json.loads(text)
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}"
        except (urllib.error.URLError, RuntimeError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        if attempt < retries:
            time.sleep(retry_delay * attempt)
    raise RuntimeError(f"Could not fetch {path}: {last_error}")


def discover_vehicle_ids_for_segment(
    segment: dict[str, Any],
    *,
    location_id: str,
    max_ids: int,
    page_size: int,
    retries: int,
    retry_delay: int,
) -> list[int]:
    params = {
        "page": 0,
        "pageSize": page_size,
        "make": segment["make"],
        "model": segment["model"],
    }
    payload = api_get_json(
        f"/vehicles/locations/{location_id}",
        params=params,
        retries=retries,
        retry_delay=retry_delay,
    )
    return extract_vehicle_ids(payload)[:max_ids]


def vehicle_row(observation: dict[str, Any], segment_id: str | None) -> dict[str, Any]:
    return {
        "vehicle_id": observation.get("vehicle_id"),
        "url": observation.get("url"),
        "source_segment_id": segment_id,
        "province": observation.get("province"),
        "year": observation.get("year"),
        "make": observation.get("make"),
        "model": observation.get("model"),
        "trim": observation.get("trim"),
        "mileage": observation.get("mileage"),
        "exterior_color": observation.get("exterior_color"),
        "image_url": observation.get("image_url"),
        "purchase_status": observation.get("purchase_status"),
        "website_state": observation.get("website_state"),
        "visible_on_site": observation.get("visible_on_site"),
        "current_disposition": observation.get("current_disposition"),
        "last_seen_at": observation.get("checked_at"),
        "last_checked_at": observation.get("checked_at"),
        "is_active": observation.get("purchase_status") != "unavailable",
        "last_snapshot": observation,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def observation_row(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "vehicle_id": observation.get("vehicle_id"),
        "checked_at": observation.get("checked_at"),
        "province": observation.get("province"),
        "price": observation.get("price"),
        "admin_fee": observation.get("admin_fee"),
        "subtotal_before_tax": observation.get("subtotal_before_tax"),
        "estimated_after_tax": observation.get("estimated_after_tax"),
        "mileage": observation.get("mileage"),
        "purchase_status": observation.get("purchase_status"),
        "website_state": observation.get("website_state"),
        "listing_type": observation.get("listing_type"),
        "visible_on_site": observation.get("visible_on_site"),
        "current_disposition": observation.get("current_disposition"),
        "check_status": observation.get("check_status") or "available",
        "check_error": observation.get("check_error"),
        "raw": observation,
    }


def prediction_row(vehicle_id: int, prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "vehicle_id": vehicle_id,
        "recommendation": prediction["recommendation"],
        "score": prediction["score"],
        "confidence": prediction["confidence"],
        "price_drop_probability_7d": prediction["price_drop_probability_7d"],
        "price_drop_probability_14d": prediction["price_drop_probability_14d"],
        "expected_drop_min": prediction["expected_drop_min"],
        "expected_drop_max": prediction["expected_drop_max"],
        "reasons": prediction["reasons"],
        "features": prediction["features"],
    }


def collect_vehicle(vehicle_id: int, *, province: str, segment_id: str | None, retries: int, retry_delay: int) -> dict[str, Any]:
    previous = None
    try:
        vehicle = fetch_vehicle(str(vehicle_id), retries, retry_delay)
        observation = observation_from_vehicle(vehicle, province)
    except Exception as exc:
        observation = unavailable_observation(str(vehicle_id), province, previous, exc)
    observation["_source_segment_id"] = segment_id
    return observation


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Clutch prices into Supabase.")
    parser.add_argument("--supabase-url", default=os.environ.get("SUPABASE_URL", ""))
    parser.add_argument(
        "--supabase-key",
        default=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", ""),
        help="Use SERVICE_ROLE_KEY for scheduled writes. The anon key is only useful if insert policies allow it.",
    )
    parser.add_argument("--province", default=os.environ.get("CLUTCH_PROVINCE", "NS"))
    parser.add_argument("--location-id", default=os.environ.get("CLUTCH_LOCATION_ID", DEFAULT_LOCATION_ID))
    parser.add_argument("--segments-file", default=DEFAULT_SEGMENT_FILE)
    parser.add_argument("--seed-vehicles-file", default=DEFAULT_SEED_VEHICLE_FILE)
    parser.add_argument("--vehicle-id", action="append", type=int, default=[])
    parser.add_argument("--discover", action="store_true", help="Discover vehicle ids from configured make/model segments.")
    parser.add_argument("--include-seed-vehicles", action="store_true", default=True)
    parser.add_argument("--skip-seed-vehicles", action="store_true", help="Do not include configured seed vehicle ids.")
    parser.add_argument("--max-per-segment", type=int, default=20)
    parser.add_argument("--max-vehicles", type=int, default=250)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--request-delay", type=float, default=1.5)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--retry-delay", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and (not args.supabase_url or not args.supabase_key):
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required unless --dry-run is used.", file=sys.stderr)
        return 2

    segments = load_json(args.segments_file)
    segment_by_id = {item["id"]: item for item in segments}
    candidates: dict[int, str | None] = {vehicle_id: None for vehicle_id in args.vehicle_id}

    if args.include_seed_vehicles and not args.skip_seed_vehicles and Path(args.seed_vehicles_file).exists():
        for item in load_json(args.seed_vehicles_file):
            candidates[int(item["vehicle_id"])] = item.get("segment_id")

    if args.discover:
        for segment in sorted(segments, key=lambda item: item.get("priority", 0), reverse=True):
            if segment.get("enabled", True) is False:
                continue
            try:
                ids = discover_vehicle_ids_for_segment(
                    segment,
                    location_id=args.location_id,
                    max_ids=args.max_per_segment,
                    page_size=args.page_size,
                    retries=args.retries,
                    retry_delay=args.retry_delay,
                )
                for vehicle_id in ids:
                    candidates.setdefault(vehicle_id, segment["id"])
                print(f"Discovered {len(ids)} vehicles for {segment['make']} {segment['model']}.")
            except Exception as exc:
                print(f"WARN: could not discover {segment['make']} {segment['model']}: {exc}", file=sys.stderr)
            if len(candidates) >= args.max_vehicles:
                break
            time.sleep(args.request_delay)

    selected = list(candidates.items())[: args.max_vehicles]
    print(f"Collecting {len(selected)} vehicles.")

    client = None if args.dry_run else SupabaseRest(args.supabase_url, args.supabase_key)
    if client:
        client.upsert("tracked_segments", segments, conflict="id")

    observations: list[dict[str, Any]] = []
    for vehicle_id, segment_id in selected:
        observation = collect_vehicle(
            vehicle_id,
            province=args.province,
            segment_id=segment_id,
            retries=args.retries,
            retry_delay=args.retry_delay,
        )
        observations.append(observation)
        print(
            f"{observation.get('vehicle_id')}: {observation.get('make')} {observation.get('model')} "
            f"{observation.get('price')} {observation.get('purchase_status')}"
        )
        time.sleep(args.request_delay)

    if args.dry_run:
        print(json.dumps(observations[:5], ensure_ascii=False, indent=2))
        return 0

    assert client is not None
    vehicle_rows = [vehicle_row(item, item.get("_source_segment_id")) for item in observations if item.get("vehicle_id")]
    observation_rows = [observation_row(item) for item in observations if item.get("vehicle_id")]
    client.upsert("tracked_vehicles", vehicle_rows, conflict="vehicle_id")
    client.insert("price_observations", observation_rows)

    prediction_rows = []
    for item in observations:
        vehicle_id = item.get("vehicle_id")
        if not isinstance(vehicle_id, int):
            continue
        history = client.get_recent_observations(vehicle_id)
        history.append(item)
        prediction_rows.append(prediction_row(vehicle_id, build_prediction(history)))
    client.insert("prediction_snapshots", prediction_rows)

    print(f"Wrote {len(vehicle_rows)} vehicles, {len(observation_rows)} observations, {len(prediction_rows)} predictions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
