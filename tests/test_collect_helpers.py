from __future__ import annotations

import unittest

from car_price_tracker.collect_to_supabase import extract_vehicle_ids, normalize_rows_for_postgrest


class CollectHelperTests(unittest.TestCase):
    def test_extract_vehicle_ids_from_nested_payload(self) -> None:
        payload = {
            "data": {
                "vehicles": [
                    {"id": 123, "name": "A"},
                    {"vehicleId": "456", "name": "B"},
                    {"vehicle_id": 123, "name": "Duplicate"},
                ]
            }
        }
        self.assertEqual(extract_vehicle_ids(payload), [123, 456])

    def test_normalize_rows_for_postgrest_adds_missing_keys(self) -> None:
        rows = normalize_rows_for_postgrest([
            {"id": "honda-hr-v", "notes": "seed"},
            {"id": "toyota-rav4"},
        ])

        self.assertEqual(rows, [
            {"id": "honda-hr-v", "notes": "seed"},
            {"id": "toyota-rav4", "notes": None},
        ])


if __name__ == "__main__":
    unittest.main()
