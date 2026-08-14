# Clutch Price Tracker

Cloud-ready price tracker for two Clutch Honda HR-V listings:

- Original HR-V: <https://www.clutch.ca/vehicles/115601>
- White HR-V: <https://www.clutch.ca/vehicles/107537>

It checks the public Clutch API for each tracked vehicle, stores price history in JSON, and uses GitHub Actions to run online every 6 hours. When tracked fields change, the workflow opens a GitHub Issue as the notification.

## Current Vehicles

- Original HR-V: `car_price_tracker/history/vehicle_115601.json`
- White HR-V: `car_price_tracker/history/vehicle_107537.json`
- Public dashboard data: `docs/status_115601.json` and `docs/status_107537.json`
- Backward-compatible original HR-V status: `docs/status.json`

## Run Locally

```powershell
py car_price_tracker\track_clutch_price.py
```

If `py` is not available, run it with any Python 3.10+ interpreter:

```powershell
python car_price_tracker\track_clutch_price.py
```

## Run Online

1. Create a GitHub repository and push this folder.
2. In GitHub, enable Actions for the repository if prompted.
3. The workflow at `.github/workflows/clutch-price-tracker.yml` runs every 6 hours.
4. Use the workflow's `Run workflow` button for a manual check.

The workflow has enough permission to commit updated history and open Issues. No extra Python dependencies or secrets are required.

Clutch may temporarily return `202` or `403` if checked repeatedly in a short window. The script retries, and the 6-hour schedule keeps traffic gentle.
