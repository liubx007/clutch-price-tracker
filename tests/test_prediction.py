from __future__ import annotations

import unittest

from car_price_tracker.prediction import build_prediction


class PredictionTests(unittest.TestCase):
    def test_thin_history_stays_conservative(self) -> None:
        result = build_prediction(
            [
                {
                    "checked_at": "2026-08-01T12:00:00+00:00",
                    "price": 26000,
                    "purchase_status": "available",
                    "check_status": "available",
                }
            ]
        )
        self.assertEqual(result["recommendation"], "watch_closely")
        self.assertEqual(result["confidence"], "low")
        self.assertIn("History is still thin", result["reasons"][0])

    def test_current_observed_low_can_be_buy_now(self) -> None:
        result = build_prediction(
            [
                {
                    "checked_at": "2026-07-01T12:00:00+00:00",
                    "price": 28000,
                    "purchase_status": "available",
                    "check_status": "available",
                },
                {
                    "checked_at": "2026-07-15T12:00:00+00:00",
                    "price": 27000,
                    "purchase_status": "available",
                    "check_status": "available",
                },
                {
                    "checked_at": "2026-08-01T12:00:00+00:00",
                    "price": 26500,
                    "purchase_status": "available",
                    "check_status": "available",
                },
                {
                    "checked_at": "2026-08-14T12:00:00+00:00",
                    "price": 26500,
                    "purchase_status": "available",
                    "check_status": "available",
                },
            ]
        )
        self.assertEqual(result["recommendation"], "buy_now")
        self.assertEqual(result["expected_drop_max"], 0)

    def test_stale_never_dropped_listing_suggests_waiting(self) -> None:
        result = build_prediction(
            [
                {
                    "checked_at": "2026-07-01T12:00:00+00:00",
                    "price": 30000,
                    "purchase_status": "available",
                    "check_status": "available",
                },
                {
                    "checked_at": "2026-07-20T12:00:00+00:00",
                    "price": 30000,
                    "purchase_status": "available",
                    "check_status": "available",
                },
                {
                    "checked_at": "2026-08-14T12:00:00+00:00",
                    "price": 30000,
                    "purchase_status": "available",
                    "check_status": "available",
                },
            ]
        )
        self.assertEqual(result["recommendation"], "wait")
        self.assertGreaterEqual(result["price_drop_probability_14d"], 0.7)


if __name__ == "__main__":
    unittest.main()
