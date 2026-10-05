from __future__ import annotations

import ast
import unittest
from datetime import datetime, time
from pathlib import Path

from tools.schedule_weekly_hours import (
    parse_schedule_time,
    patch_baseline_source,
    published_weekly_totals,
    resolve_weekly_interval,
)


BASELINE_PATH = (
    Path(__file__).resolve().parents[1] / ".tmp_analytics_extract" / "baseline.py"
)


class ScheduleWeeklyHoursTest(unittest.TestCase):
    def test_parse_packed_clock_and_excel_fraction(self):
        self.assertEqual(parse_schedule_time("800"), {"formatted": "08:00", "minutes": 480})
        self.assertEqual(parse_schedule_time("1330"), {"formatted": "13:30", "minutes": 810})
        self.assertEqual(parse_schedule_time("0800"), {"formatted": "08:00", "minutes": 480})
        self.assertEqual(parse_schedule_time("1330.0"), {"formatted": "13:30", "minutes": 810})
        self.assertEqual(parse_schedule_time(8 / 24)["formatted"], "08:00")
        self.assertEqual(
            parse_schedule_time("0.3333333333333333"),
            {"formatted": "08:00", "minutes": 480},
        )

    def test_parse_clock_strings_and_timestamps(self):
        self.assertEqual(parse_schedule_time("08:00"), {"formatted": "08:00", "minutes": 480})
        self.assertEqual(parse_schedule_time("8:00"), {"formatted": "08:00", "minutes": 480})
        self.assertEqual(parse_schedule_time("08:00:00"), {"formatted": "08:00", "minutes": 480})
        self.assertEqual(
            parse_schedule_time("1899-12-30 08:30:00"),
            {"formatted": "08:30", "minutes": 510},
        )
        self.assertEqual(
            parse_schedule_time("1899-12-30T08:00:00"),
            {"formatted": "08:00", "minutes": 480},
        )
        self.assertEqual(
            parse_schedule_time("08:00:00+00:00"),
            {"formatted": "08:00", "minutes": 480},
        )
        self.assertEqual(parse_schedule_time(time(14, 15)), {"formatted": "14:15", "minutes": 855})
        self.assertEqual(
            parse_schedule_time(datetime(1899, 12, 30, 16, 45)),
            {"formatted": "16:45", "minutes": 1005},
        )

    def test_empty_boundaries_stay_empty_and_invalid_values_raise(self):
        for value in (None, "", "0", "00", "0000", "0.0", "1899-12-30", "0.000000"):
            self.assertIsNone(parse_schedule_time(value))
        with self.assertRaises(ValueError):
            parse_schedule_time("99:00")
        with self.assertRaises(ValueError):
            parse_schedule_time("1360")
        with self.assertRaises(ValueError):
            parse_schedule_time("not-a-time")

    def test_missing_frequency_on_a_worked_row_is_weekly(self):
        warnings = []
        freq, interval = resolve_weekly_interval(
            {"raw": None, "interval_weeks": None, "type": "unknown"},
            300,
            warnings,
        )
        self.assertEqual(interval, 1)
        self.assertEqual(freq["type"], "weekly")
        self.assertTrue(freq["assumed_weekly_because_frequency_unparsed"])
        self.assertTrue(warnings)

        warnings = []
        _, interval = resolve_weekly_interval(
            {"raw": "שבועי", "interval_weeks": None, "type": "unknown"},
            300,
            warnings,
        )
        self.assertEqual(interval, 1)
        self.assertTrue(warnings)

    def test_existing_and_negative_frequencies_are_left_alone(self):
        warnings = []
        freq, interval = resolve_weekly_interval(
            {
                "raw": "2",
                "interval_weeks": 2,
                "occurrences_per_week": 0.5,
                "type": "every_2_weeks",
            },
            300,
            warnings,
        )
        self.assertEqual(interval, 2)
        self.assertEqual(freq["type"], "every_2_weeks")
        self.assertEqual(warnings, [])

        warnings = []
        _, interval = resolve_weekly_interval(
            {"raw": "-1", "interval_weeks": None, "type": "unknown"},
            300,
            warnings,
        )
        self.assertIsNone(interval)
        self.assertEqual(warnings, [])

        warnings = []
        _, interval = resolve_weekly_interval(
            {"raw": None, "interval_weeks": None, "type": "unknown"},
            0,
            warnings,
        )
        self.assertIsNone(interval)
        self.assertEqual(warnings, [])

    def test_unpublished_zero_hours_stay_missing(self):
        self.assertEqual(published_weekly_totals(False, 0), (None, None))
        self.assertEqual(published_weekly_totals(True, 0), (None, None))
        self.assertEqual(published_weekly_totals(True, 540), (540, 9))

    def test_live_baseline_source_patches_and_parses(self):
        if not BASELINE_PATH.exists():
            self.skipTest("live baseline extract is not available")
        patched = patch_baseline_source(BASELINE_PATH.read_text())
        ast.parse(patched)
        self.assertIn("return parse_schedule_time(value)", patched)
        self.assertNotIn("len(value) > 4", patched)
        self.assertIn(
            "resolve_weekly_interval(freq, daily_minutes, row_warnings)",
            patched,
        )
        self.assertIn("weekly_hours_value", patched)
        self.assertNotIn("round(weekly_minutes / 60.0, 3)", patched)
        self.assertNotIn("_clock(", patched)

    def test_patch_is_idempotent(self):
        if not BASELINE_PATH.exists():
            self.skipTest("live baseline extract is not available")
        once = patch_baseline_source(BASELINE_PATH.read_text())
        self.assertEqual(patch_baseline_source(once), once)


if __name__ == "__main__":
    unittest.main()
