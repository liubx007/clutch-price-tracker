# Clutch Price Tracker

This tracks the Clutch vehicle at <https://www.clutch.ca/vehicles/115601>.

Current target:

- Vehicle: 2023 Honda HR-V LX
- Province tracked: NS
- Data source: `https://api.clutch.ca:443/v1/vehicles/115601`

Run locally from the repository root:

```powershell
py car_price_tracker\track_clutch_price.py
```

Cloud monitoring:

1. Push this repository to GitHub.
2. Make sure GitHub Actions is enabled for the repository.
3. The workflow in `.github/workflows/clutch-price-tracker.yml` runs every 6 hours and can also be started manually.
4. On the first run it records the baseline price. On later runs it opens a GitHub Issue when price, admin fee, listing state, or visibility changes.

The history file is `car_price_tracker/history/vehicle_115601.json`.

Clutch may return temporary `202` or `403` responses if checked repeatedly in a short window. The script retries by default, and the scheduled workflow checks every 6 hours to keep the traffic gentle.
