from __future__ import annotations

import unittest

from car_price_tracker.collect_to_supabase import extract_vehicle_ids


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


if __name__ == "__main__":
    unittest.main()
