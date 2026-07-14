# Clutch Price Tracker

Cloud-ready price tracker for <https://www.clutch.ca/vehicles/115601>.

It checks the public Clutch API for the tracked vehicle, stores price history in JSON, and uses GitHub Actions to run online every 6 hours. When tracked fields change, the workflow opens a GitHub Issue as the notification.

## Current Vehicle

- Vehicle: 2023 Honda HR-V LX
- Province: NS
- Last recorded price: CAD $26,790
- Last recorded admin fee: CAD $899
- Last recorded listing state: `COMING_SOON`

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

