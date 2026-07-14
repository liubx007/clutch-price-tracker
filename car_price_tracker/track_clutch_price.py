#!/usr/bin/env python3
"""Track one Clutch vehicle's price and emit GitHub Actions outputs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.clutch.ca:443/v1"
DEFAULT_VEHICLE_ID = "115601"
DEFAULT_PROVINCE = "NS"


def fetch_vehicle(vehicle_id: str, retries: int, retry_delay: int) -> dict[str, Any]:
    url = f"{API_BASE}/vehicles/{vehicle_id}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en-CA,en;q=0.9",
            "Origin": "https://www.clutch.ca",
            "Referer": f"https://www.clutch.ca/vehicles/{vehicle_id}",
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
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                if response.status == 202 or not body.strip():
                    raise RuntimeError(f"Clutch API returned HTTP {response.status} with an empty body.")
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError as exc:
                    preview = body[:500].replace("\n", " ")
                    raise RuntimeError(f"Clutch API returned non-JSON content: {preview}") from exc
                if not isinstance(payload, dict):
                    raise RuntimeError("Clutch API returned JSON, but it was not an object.")
                return payload
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {body[:500]}"
        except urllib.error.URLError as exc:
            last_error = f"network error: {exc}"
        except RuntimeError as exc:
            last_error = str(exc)

        if attempt < retries:
            time.sleep(retry_delay * attempt)

    raise RuntimeError(f"Could not fetch Clutch vehicle after {retries} attempts: {last_error}")


def pick_price(vehicle: dict[str, Any], province: str) -> dict[str, Any]:
    prices = vehicle.get("vehiclePrices") or []
    for item in prices:
        if item.get("provinceId") == province:
            return item
    if prices:
        return prices[0]
    raise RuntimeError("Vehicle response did not include vehiclePrices.")


def observation_from_vehicle(vehicle: dict[str, Any], province: str) -> dict[str, Any]:
    price_row = pick_price(vehicle, province)
    price = price_row.get("price")
    admin_fee = price_row.get("adminFee")
    tax_rate = vehicle.get("taxRate")
    subtotal = price + admin_fee if isinstance(price, int) and isinstance(admin_fee, int) else None
    estimated_after_tax = round(subtotal * (1 + tax_rate), 2) if subtotal and isinstance(tax_rate, (int, float)) else None

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vehicle_id": vehicle.get("id"),
        "url": f"https://www.clutch.ca/vehicles/{vehicle.get('id')}",
        "name": vehicle.get("name") or vehicle.get("cvcName") or vehicle.get("idWithName"),
        "year": vehicle.get("year") or vehicle.get("cvcYear"),
        "make": (vehicle.get("make") or {}).get("name") or vehicle.get("cvcMake"),
        "model": (vehicle.get("model") or {}).get("name") or vehicle.get("cvcModel"),
        "trim": (vehicle.get("trim") or {}).get("name") or vehicle.get("cvcTrim"),
        "mileage": vehicle.get("mileage"),
        "province": price_row.get("provinceId"),
        "price": price,
        "admin_fee": admin_fee,
        "subtotal_before_tax": subtotal,
        "tax_rate": tax_rate,
        "estimated_after_tax": estimated_after_tax,
        "website_state": vehicle.get("websiteState"),
        "listing_type": vehicle.get("type"),
        "visible_on_site": vehicle.get("visibleOnSite"),
        "current_disposition": vehicle.get("currentDisposition"),
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"observations": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def comparable(observation: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "price",
        "admin_fee",
        "subtotal_before_tax",
        "estimated_after_tax",
        "website_state",
        "listing_type",
        "visible_on_site",
        "current_disposition",
    ]
    return {key: observation.get(key) for key in keys}


def write_github_output(values: dict[str, Any]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            text = "" if value is None else str(value)
            handle.write(f"{key}={text}\n")


def money(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"CAD ${value:,.0f}"
    return "unknown"


def build_issue_body(current: dict[str, Any], previous: dict[str, Any] | None) -> str:
    lines = [
        "The tracked Clutch vehicle was checked.",
        "",
        f"- Vehicle: {current.get('name')}",
        f"- URL: {current.get('url')}",
        f"- Province: {current.get('province')}",
        f"- Current price: {money(current.get('price'))}",
        f"- Current admin fee: {money(current.get('admin_fee'))}",
        f"- Current subtotal before tax: {money(current.get('subtotal_before_tax'))}",
        f"- Website state: {current.get('website_state')}",
        f"- Visible on site: {current.get('visible_on_site')}",
        f"- Checked at: {current.get('checked_at')}",
    ]
    if previous:
        lines.extend(
            [
                "",
                "Previous observation:",
                f"- Price: {money(previous.get('price'))}",
                f"- Admin fee: {money(previous.get('admin_fee'))}",
                f"- Subtotal before tax: {money(previous.get('subtotal_before_tax'))}",
                f"- Website state: {previous.get('website_state')}",
                f"- Visible on site: {previous.get('visible_on_site')}",
                f"- Checked at: {previous.get('checked_at')}",
            ]
        )
    return "\n".join(lines) + "\n"


def build_public_status(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    state: dict[str, Any],
    initialized: bool,
    changed: bool,
) -> dict[str, Any]:
    observations = state.get("observations") or []
    history = observations[-20:]
    previous_comparable = comparable(previous) if previous else None
    current_comparable = comparable(current)
    changed_fields = []
    if previous_comparable:
        changed_fields = [
            key
            for key, value in current_comparable.items()
            if previous_comparable.get(key) != value
        ]

    return {
        "generated_at": current.get("checked_at"),
        "initialized": initialized,
        "changed": changed,
        "changed_fields": changed_fields,
        "vehicle": {
            "id": current.get("vehicle_id"),
            "name": current.get("name"),
            "year": current.get("year"),
            "make": current.get("make"),
            "model": current.get("model"),
            "trim": current.get("trim"),
            "mileage": current.get("mileage"),
            "url": current.get("url"),
        },
        "province": current.get("province"),
        "latest": current,
        "previous": previous,
        "history": history,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Track a Clutch vehicle price.")
    parser.add_argument("--vehicle-id", default=DEFAULT_VEHICLE_ID)
    parser.add_argument("--province", default=DEFAULT_PROVINCE)
    parser.add_argument(
        "--state-file",
        default=f"car_price_tracker/history/vehicle_{DEFAULT_VEHICLE_ID}.json",
        help="JSON file used to persist observed price changes.",
    )
    parser.add_argument(
        "--issue-body-file",
        default="car_price_tracker/last_issue.md",
        help="Markdown file written when a notification body is useful.",
    )
    parser.add_argument(
        "--public-status-file",
        default="",
        help="Optional JSON file used by a public static status page.",
    )
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--retry-delay", type=int, default=20, help="Base retry delay in seconds.")
    args = parser.parse_args()

    state_path = Path(args.state_file)
    issue_body_path = Path(args.issue_body_file)

    vehicle = fetch_vehicle(args.vehicle_id, args.retries, args.retry_delay)
    current = observation_from_vehicle(vehicle, args.province)
    state = load_state(state_path)
    observations = state.setdefault("observations", [])
    previous = observations[-1] if observations else None

    initialized = previous is None
    changed = bool(previous and comparable(previous) != comparable(current))
    state_updated = initialized or changed

    if state_updated:
        observations.append(current)
        state["last_observation"] = current
        save_state(state_path, state)

    issue_body_path.parent.mkdir(parents=True, exist_ok=True)
    issue_body_path.write_text(build_issue_body(current, previous), encoding="utf-8")

    if args.public_status_file:
        public_status_path = Path(args.public_status_file)
        public_status_path.parent.mkdir(parents=True, exist_ok=True)
        public_status_path.write_text(
            json.dumps(
                build_public_status(current, previous, state, initialized, changed),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(f"Vehicle: {current.get('name')} ({current.get('url')})")
    print(f"Province: {current.get('province')}")
    print(f"Price: {money(current.get('price'))}")
    print(f"Admin fee: {money(current.get('admin_fee'))}")
    print(f"Website state: {current.get('website_state')}")
    if initialized:
        print("Initialized price history.")
    elif changed:
        print("Change detected.")
    else:
        print("No tracked fields changed.")

    write_github_output(
        {
            "initialized": str(initialized).lower(),
            "changed": str(changed).lower(),
            "state_updated": str(state_updated).lower(),
            "vehicle_name": current.get("name"),
            "vehicle_url": current.get("url"),
            "province": current.get("province"),
            "price": current.get("price"),
            "admin_fee": current.get("admin_fee"),
            "website_state": current.get("website_state"),
            "previous_price": previous.get("price") if previous else "",
            "public_status_updated": str(bool(args.public_status_file)).lower(),
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
