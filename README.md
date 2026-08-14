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

## Product Data Collector

The product MVP collector writes active Clutch vehicle history into Supabase instead of Git JSON files.

It is designed for a controlled seed pool, not full-site crawling:

- Canada's popular models from the seed file
- Tesla Model Y and Model 3
- Existing manually tracked vehicle ids
- A polite twice-daily GitHub Actions schedule

### Supabase Setup

1. Create a Supabase project.
2. Open the SQL Editor.
3. Run `supabase/schema.sql`.
4. Add these GitHub repository secrets:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Do not commit `SUPABASE_SERVICE_ROLE_KEY`. The publishable/anon key is for browser reads later; scheduled writes need the service role key.

### Local Dry Run

```powershell
python car_price_tracker\collect_to_supabase.py --dry-run --vehicle-id 115601 --vehicle-id 107537
```

### Local Supabase Write

```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="..."
python car_price_tracker\collect_to_supabase.py --vehicle-id 115601 --vehicle-id 107537
```

### Twice-Daily Collection

The workflow `.github/workflows/clutch-supabase-collector.yml` runs at 05:11 and 17:11 UTC. It skips safely until the Supabase secrets are configured.
