from __future__ import annotations

import ast
import json
import unittest
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

from tools.lior_analytics_v2 import (
    patch_analytics_v2,
    upgrade_analytics_v2_nullsafe,
    upgrade_analytics_v2_return_types,
)


class Data:
    def __init__(self, data):
        self.data = data


class _Rows:
    def __init__(self, rows, columns=None):
        self._rows = rows
        self._columns = list(columns or [])

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def keys(self):
        return list(self._columns)


class _Connection:
    def __init__(self, tables):
        self.tables = tables

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, _params=None):
        statement = str(statement)
        if "visit_types" in statement:
            return _Rows(self.tables.get("visit_types", []))
        if "visits" in statement:
            if "WHERE 1 = 0" in statement:
                return _Rows([], self.tables.get("visits_columns", []))
            return _Rows(self.tables.get("visits", []))
        return _Rows(self.tables.get("appointments", []))


class _Engine:
    def __init__(self, tables):
        self.tables = tables

    def connect(self):
        return _Connection(self.tables)


def _node(node_id: str, code: str) -> dict:
    return {
        "id": node_id,
        "data": {
            "node": {
                "template": {"code": {"value": code}},
                "metadata": {},
            }
        },
    }


def _flow(historical_code: str, decision_code: str, builder_code: str) -> dict:
    return {
        "data": {
            "nodes": [
                _node("historical_performance_analyzer-cDHUJ", historical_code),
                _node("decision_kpi_analyzer-IBs8T", decision_code),
                _node("analytics_feature_builder-f0hrQ", builder_code),
                _node(
                    "urgent_reserve_pressure_analyzer-m0uiz",
                    PRESSURE_COMPONENT,
                ),
            ],
            "edges": [],
        }
    }


HISTORICAL_COMPONENT = r'''
class HistoricalPerformanceAnalyzer(Component):
    WEEKDAY_NAMES = {0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי", 4: "שישי", 5: "שבת", 6: "ראשון"}

    @staticmethod
    def _payload(value):
        return value.data if hasattr(value, "data") else value

    @staticmethod
    def _norm_id(value):
        return str(value).strip() if value not in (None, "") else None

    @staticmethod
    def _normalize_calendar_status(value):
        return str(value or "").strip() or None

    @staticmethod
    def _parse_date(value):
        return date.fromisoformat(str(value))

    @staticmethod
    def _parse_time(value):
        return time.fromisoformat(str(value))

    def _combine(self, day, clock):
        return datetime.combine(self._parse_date(day), self._parse_time(clock))

    @staticmethod
    def _inside_exclusion(_dt, _intervals):
        return False

    @staticmethod
    def _excluded_dates(_baseline):
        return set()

    @staticmethod
    def _excluded_intervals(_baseline):
        return {}

    @staticmethod
    def _urgent(value):
        return str(value) == "1"

    @staticmethod
    def _segment_units(row, regular_segment):
        return float(row.get("visit_duration") or regular_segment) / float(regular_segment)

    def _db_url(self):
        return "offline"

    def analyze(self):
        return Data(data={
            "valid": True,
            "match_records": [{
                "appointment_ids": [1],
                "visit_id": 101,
                "scheduled_start": "2026-09-01T09:00:00",
            }],
            "no_show": {"confirmed_no_show_count": 7},
            "delay": {"eligible_match_count": 1},
            "capacity_marker": "primary-only",
        })
'''


DECISION_COMPONENT = r'''
class DecisionKPIAnalyzer(Component):
    WEEKDAY_NAMES = {0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי", 4: "שישי", 5: "שבת", 6: "ראשון"}

    @staticmethod
    def _payload(value):
        return value.data if hasattr(value, "data") else value

    def _db_url(self):
        return "offline"

    def analyze(self):
        return Data(data={
            "valid": True,
            "existing_calendar_settings": {
                "contract_version": "v1",
                "complete": True,
                "preferences": [{
                    "setting_id": "preference::שלישי::09:00::10:00",
                    "preferred_visit_types": [{
                        "preferred_label": "000GH",
                        "count": 1,
                        "percentage": 100.0,
                    }],
                }],
                "reserves": [{
                    "setting_id": "reserve::שלישי::10:00::11:00",
                    "weekday": "שלישי",
                    "time_from": "10:00",
                    "time_to": "11:00",
                    "defined_segment_units": 4.0,
                    "booked_segment_units": 2.0,
                    "matched_actual_segment_units": 0.0,
                    "matched_urgent_segment_units": 0.0,
                    "utilization": {"status": "available", "value": 0.5},
                    "actualization": {"status": "unavailable", "value": None},
                }],
            },
            "findings": {"reserves": {"by_60_minute_window": [{
                "weekday": "שלישי",
                "time_from": "10:00",
                "time_to": "11:00",
                "matched_actual_reserve_segment_units": None,
                "matched_urgent_reserve_segment_units": None,
            }]}},
            "recommendation_candidates": {
                "visit_type_allocation_candidates": [{
                    "weekday": "שלישי",
                    "time_from": "09:00",
                    "time_to": "10:00",
                    "occurrence_dates": [
                        "2026-01-06",
                        "2026-02-03",
                        "2026-03-03",
                    ],
                }],
            },
        })
'''


PRESSURE_COMPONENT = r'''
class UrgentReservePressureAnalyzer(Component):
    def analyze(self):
        return Data(data={"valid": True})
'''


BUILDER_COMPONENT = r'''
class AnalyticsFeatureBuilder(Component):
    persist_metrics = False

    @staticmethod
    def _payload(value):
        return value.data if hasattr(value, "data") else value

    @staticmethod
    def _time_to_minutes(value):
        hour, minute = [int(x) for x in str(value).split(":")[:2]]
        return hour * 60 + minute

    @staticmethod
    def _mt(value):
        return f"{value // 60:02d}:{value % 60:02d}"

    @classmethod
    def _baseline_shift_map(cls, baseline):
        result = defaultdict(list)
        for entry in baseline["schedule"]["entries"]:
            for key in ("shift_1", "shift_2"):
                shift = entry.get(key)
                if shift:
                    result[entry["weekday_name"]].append((
                        cls._time_to_minutes(shift["from"]),
                        cls._time_to_minutes(shift["to"]),
                        shift["from"],
                        shift["to"],
                    ))
        return result

    @classmethod
    def _effective_window(cls, baseline, weekday, time_from, time_to):
        start = cls._time_to_minutes(time_from)
        finish = cls._time_to_minutes(time_to)
        for shift_start, shift_end, _, _ in cls._baseline_shift_map(baseline).get(weekday, []):
            overlap_start = max(start, shift_start)
            overlap_end = min(finish, shift_end)
            if overlap_end > overlap_start:
                return cls._mt(overlap_start), cls._mt(overlap_end)
        return None

    @classmethod
    def _apply_effective_window(cls, baseline, item):
        effective = cls._effective_window(
            baseline, item.get("weekday"), item.get("time_from"), item.get("time_to")
        )
        if effective:
            old = (item["time_from"], item["time_to"])
            item["time_from"], item["time_to"] = effective
            item["effective_window_clipped_to_baseline"] = effective != old
        return item

    def build(self):
        metrics = {
            "analysis_context": {
                "decision_period": {
                    "from": "2026-01-05",
                    "to": "2026-06-28",
                },
                "source_analysis_period": {
                    "from": "2026-01-05",
                    "to": "2026-06-28",
                },
            },
            "performance_summary": {
                "weekly_patient_visits": {"observed_week_count": 25}
            },
            "existing_calendar_settings": {"contract_version": "v1", "complete": True},
            "recommendation_evidence": {
                "telephone_video_window_candidates": [{
                    "candidate_type": "telephone_video_window",
                    "decision_tier": "recommendation",
                    "weekday": "שלישי",
                    "time_from": "09:15", "time_to": "10:00",
                    "support_occurrence_count": 1,
                    "eligible_occurrence_count": 24,
                    "occurrence_dates": ["2026-03-03"],
                    "encounter_count": 2,
                    "threshold_evaluation": {
                        "required_support_for_recommendation": 8,
                        "min_encounters": 12,
                    },
                    "existing_settings_context": {"comparison_status": "complete"},
                }],
                "visit_type_allocation_candidates": [{
                    "candidate_type": "visit_type_allocation",
                    "decision_tier": "recommendation",
                    "weekday": "שלישי",
                    "time_from": "09:30", "time_to": "10:30",
                    "support_occurrence_count": 23,
                    "eligible_occurrence_count": 24,
                    "occurrence_dates": [
                        (date(2026, 1, 6) + timedelta(days=7 * index)).isoformat()
                        for index in range(25)
                        if index not in {4, 11}
                    ],
                    "logical_appointment_count": 231,
                    "visit_type_name": "מעקב",
                    "threshold_evaluation": {
                        "required_support_for_recommendation": 8,
                    },
                    "existing_settings_context": {"comparison_status": "complete"},
                }],
            },
            "insight_candidates": [{
                "insight_type": "forecast_change",
                "decision_tier": "insight",
                "weekday": "שלישי",
                "time_from": "09:00",
                "time_to": "10:00",
            }],
        }
        persistence = {"requested": bool(self.persist_metrics), "saved": False, "analysis_metric_id": None, "error": None}
        self.persisted_metrics = json.loads(json.dumps(metrics))
        return Data(data={
            "valid": True,
            "metrics": metrics,
            "persistence": persistence,
        })
'''


class Component:
    pass


def _embedded_globals(tables=None) -> dict:
    return {
        "Component": Component,
        "Data": Data,
        "date": date,
        "datetime": datetime,
        "time": time,
        "timedelta": timedelta,
        "defaultdict": defaultdict,
        "hashlib": __import__("hashlib"),
        "json": json,
        "text": lambda statement: statement,
        "get_cached_engine": lambda _url: _Engine(tables or {}),
    }


def _langflow_first_component_class(code: str, tables=None):
    """Emulate extract_class_name followed by first matching class extraction."""
    tree = ast.parse(code)
    class_name = None
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if any(isinstance(base, ast.Name) and base.id == "Component" for base in node.bases):
            class_name = node.name
            break
    if class_name is None:
        raise AssertionError("No Component subclass found")
    first_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    namespace = _embedded_globals(tables)
    ast.fix_missing_locations(first_class)
    exec(
        compile(ast.Module(body=[first_class], type_ignores=[]), "<langflow-extracted>", "exec"),
        namespace,
    )
    return namespace[class_name]


def _patched_namespace(code: str, tables=None) -> dict:
    namespace = _embedded_globals(tables)
    exec(compile(code, "<embedded-component>", "exec"), namespace)
    return namespace


def test_reserve_reconciliation_is_separate_from_primary_analytics():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    component_class = _langflow_first_component_class(
        code,
        {
            "appointments": [
                {
                    "appointment_id": 1, "member_id": "A", "appointment_date": "2026-09-01",
                    "appointment_time": "09:00", "calendar_status": "פנוי",
                    "appointment_type_code": "0", "visit_duration": 15,
                },
                {
                    "appointment_id": 2, "member_id": "A", "appointment_date": "2026-09-01",
                    "appointment_time": "10:00", "calendar_status": "עתודה",
                    "appointment_type_code": "1", "visit_duration": 15,
                },
                {
                    "appointment_id": 3, "member_id": "B", "appointment_date": "2026-09-01",
                    "appointment_time": "11:00", "calendar_status": "עתודה",
                    "appointment_type_code": "0", "visit_duration": 30,
                },
            ],
            "visits": [
                {"visit_id": 101, "customer_id": "A", "encounter_start_datetime": "2026-09-01T09:05:00"},
                {"visit_id": 102, "customer_id": "A", "encounter_start_datetime": "2026-09-01T10:10:00"},
                {"visit_id": 103, "customer_id": "B", "encounter_start_datetime": "2026-09-01T11:20:00"},
            ],
        },
    )
    component = component_class()
    component.baseline = {
        "analysis_run_id": 9,
        "analysis_period": {"from": "2026-09-01", "to": "2026-09-30"},
        "segment": {"regular_segment_minutes": 15},
    }

    result = component.analyze().data
    reserve = result["reserve_to_visit_reconciliation"]

    assert result["match_records"] == [{
        "appointment_ids": [1],
        "visit_id": 101,
        "scheduled_start": "2026-09-01T09:00:00",
    }]
    assert result["no_show"] == {"confirmed_no_show_count": 7}
    assert result["delay"] == {"eligible_match_count": 1}
    assert result["capacity_marker"] == "primary-only"
    assert reserve["measurement_status"] == "available"
    assert reserve["matched_reserve_appointment_ids"] == [2, 3]
    assert reserve["matched_urgent_reserve_appointment_ids"] == [2]
    assert reserve["matched_visit_ids"] == [102, 103]
    assert 101 not in reserve["matched_visit_ids"]


def test_decision_output_resolves_preference_and_measures_reserve():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][1]["data"]["node"]["template"]["code"]["value"]
    component_class = _langflow_first_component_class(
        code,
        {
            "visit_types": [{
                "visit_type_code": "000GH",
                "visit_type_name": "תור טלפוני",
                "calendar_short_name": None,
                "source_description": None,
                "source_short_description": None,
            }]
        },
    )
    component = component_class()
    component.historical = {
        "reserve_to_visit_reconciliation": {
            "measurement_status": "available",
            "matched_reserve_appointment_ids": [2, 3],
            "matched_urgent_reserve_appointment_ids": [2],
            "matches": [
                {
                    "appointment_ids": [2],
                    "scheduled_start": "2026-09-01T10:05:00",
                    "segment_units": 1.0,
                    "is_urgent": False,
                },
                {
                    "appointment_ids": [3],
                    "scheduled_start": "2026-09-08T10:20:00",
                    "segment_units": 1.0,
                    "is_urgent": False,
                },
                {
                    "appointment_ids": [999],
                    "scheduled_start": "2026-09-15T10:20:00",
                    "segment_units": 5.0,
                    "is_urgent": True,
                },
            ],
        }
    }

    result = component.analyze().data
    settings = result["existing_calendar_settings"]
    preferred = settings["preferences"][0]["preferred_visit_types"][0]
    reserve = settings["reserves"][0]

    assert preferred["preferred_visit_type_code"] == "000GH"
    assert preferred["preferred_visit_type_name"] == "תור טלפוני"
    assert preferred["preferred_code"] == "000GH"
    assert preferred["preferred_name"] == "תור טלפוני"
    assert preferred["preferred_label"] == "תור טלפוני"
    assert reserve == {
        **reserve,
        "defined_segment_units": 4.0,
        "booked_segment_units": 2.0,
        "matched_actual_segment_units": 2.0,
        "matched_urgent_segment_units": 1.0,
        "measurement_status": "available",
    }
    assert reserve["utilization"] == {"status": "available", "value": 0.5}
    assert reserve["actualization"]["status"] == "available"
    assert reserve["actualization"]["value"] == 1.0
    assert reserve["actualization"]["urgent_share"] == 0.5
    finding = result["findings"]["reserves"]["by_60_minute_window"][0]
    assert finding["matched_actual_reserve_segment_units"] == 2.0
    assert finding["matched_urgent_reserve_segment_units"] == 1.0
    assert finding["reserve_actualization_measurement_status"] == "available"
    assert finding["reserve_actualization_rate"] == 1.0
    assert finding["urgent_share_of_matched_reserve"] == 0.5
    assert (
        result["findings"]["reserves"][
            "reserve_to_visit_reconciliation_measurement_status"
        ]
        == "available"
    )


def test_decision_output_exposes_normalized_occurrence_dates():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][1]["data"]["node"]["template"]["code"]["value"]
    component = _langflow_first_component_class(code)()
    component.historical = {}

    candidate = component.analyze().data["recommendation_candidates"][
        "visit_type_allocation_candidates"
    ][0]

    assert candidate["occurrence_dates"] == [
        "2026-01-06",
        "2026-02-03",
        "2026-03-03",
    ]
    assert candidate["first_occurrence_date"] == "2026-01-06"
    assert candidate["last_occurrence_date"] == "2026-03-03"
    assert candidate["active_date_count"] == 3


def test_actual_end_time_alias_produces_real_duration_by_visit_type():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    code = patch_analytics_v2(flow)["data"]["nodes"][1]["data"]["node"]["template"]["code"]["value"]
    namespace = _patched_namespace(
        code,
        {
            "visits_columns": [
                "visit_id",
                "encounter_start_datetime",
                "actual_end_time",
            ],
            "visits": [
                {
                    "visit_id": 101,
                    "encounter_start_datetime": "2026-09-01T09:00:00",
                    "actual_duration_value": "09:12:00",
                },
                {
                    "visit_id": 102,
                    "encounter_start_datetime": "2026-09-08T09:00:00",
                    "actual_duration_value": "09:18:00",
                },
            ],
            "visit_types": [{
                "visit_type_code": "REG",
                "visit_type_name": "ביקור רגיל",
                "calendar_short_name": None,
                "source_description": None,
                "source_short_description": None,
            }],
        },
    )
    component = namespace["DecisionKPIAnalyzer"]()
    component.baseline = {
        "analysis_run_id": 9,
        "segment": {"regular_segment_minutes": 15},
    }
    component._schedule_windows = lambda _baseline: []
    component.historical = {
        "match_records": [
            {"visit_id": 101, "visit_type_code": "REG"},
            {"visit_id": 102, "visit_type_code": "REG"},
        ],
        "no_show": {"classification_records": []},
    }

    measured = component.analyze().data["required_analysis_inputs"][
        "segment_duration_by_visit_type"
    ]

    assert measured["measurement_status"] == "available"
    assert measured["duration_source_field"] == "actual_end_time"
    assert measured["uses_start_to_next_start_proxy"] is False
    assert measured["by_visit_type"][0]["median_actual_duration_minutes"] == 15
    assert measured["by_visit_type"][0]["p75_actual_duration_minutes"] == 18


def test_absent_actual_duration_source_remains_unavailable_without_cadence_proxy():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    code = patch_analytics_v2(flow)["data"]["nodes"][1]["data"]["node"]["template"]["code"]["value"]
    namespace = _patched_namespace(
        code,
        {
            "visits_columns": ["visit_id", "encounter_start_datetime"],
            "visits": [],
            "visit_types": [],
        },
    )
    component = namespace["DecisionKPIAnalyzer"]()
    component.baseline = {
        "analysis_run_id": 9,
        "segment": {"regular_segment_minutes": 15},
    }
    component._schedule_windows = lambda _baseline: []
    component.historical = {
        "match_records": [],
        "no_show": {"classification_records": []},
    }

    measured = component.analyze().data["required_analysis_inputs"][
        "segment_duration_by_visit_type"
    ]

    assert measured["measurement_status"] == "unavailable"
    assert measured["unavailable_reason"] == "actual_visit_duration_field_not_found"
    assert measured["uses_start_to_next_start_proxy"] is False


def _modality_result(visit_type_rows, records=None, visit_type_names=None):
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    code = patch_analytics_v2(flow)["data"]["nodes"][1]["data"]["node"]["template"]["code"]["value"]
    component = _patched_namespace(code)["DecisionKPIAnalyzer"]()
    component.baseline = {"schedule": {"entries": []}}
    component._schedule_windows = lambda _baseline: []
    component._dt = lambda value: datetime.fromisoformat(str(value))
    component._inside_schedule = lambda _value, _schedule: True
    return component._lior_required_no_show_modality(
        {
            "findings": {
                "visit_type_allocation": {
                    "by_visit_type_capacity": visit_type_rows,
                }
            },
            "analysis_period": {},
        },
        {"no_show": {"classification_records": list(records or [])}},
        dict(visit_type_names or {}),
    )


def test_regular_visit_is_business_mapped_to_face_to_face():
    result = _modality_result([
        {
            "visit_type_name": "ביקור רגיל",
            "visit_type_code": "REG",
            "logical_appointment_count": 80,
        },
        {
            "visit_type_name": "תור טלפוני",
            "visit_type_code": "TEL",
            "logical_appointment_count": 20,
        },
    ])

    assert result["measurement_status"] == "available"
    assert result["modalities"]["face_to_face"]["logical_appointment_count"] == 80
    assert result["modalities"]["telephone_video"]["logical_appointment_count"] == 20
    assert result["classification_coverage"]["rate"] == 1.0


def test_empty_modality_group_marks_comparison_unavailable():
    result = _modality_result([
        {
            "visit_type_name": "ביקור רגיל",
            "logical_appointment_count": 100,
        }
    ])

    assert result["measurement_status"] == "unavailable"
    assert result["comparison"]["measurement_status"] == "unavailable"
    assert "telephone_video_group_empty" in result["comparison_unavailable_reasons"]


def test_low_modality_classification_coverage_marks_comparison_unavailable():
    result = _modality_result([
        {
            "visit_type_name": "ביקור רגיל",
            "logical_appointment_count": 20,
        },
        {
            "visit_type_name": "תור טלפוני",
            "logical_appointment_count": 20,
        },
        {
            "visit_type_name": "סוג לא מסווג",
            "logical_appointment_count": 60,
        },
    ])

    assert result["classification_coverage"]["rate"] == 0.4
    assert result["classification_coverage"]["minimum_required_rate"] == 0.8
    assert result["measurement_status"] == "unavailable"
    assert "classified_coverage_below_minimum" in result[
        "comparison_unavailable_reasons"
    ]


def test_modality_comparison_accounts_for_excluded_and_unclassified_no_shows():
    result = _modality_result(
        [
            {
                "visit_type_name": "ביקור רגיל",
                "logical_appointment_count": 80,
            },
            {
                "visit_type_name": "תור טלפוני",
                "logical_appointment_count": 20,
            },
        ],
        records=[
            {
                "classification": "confirmed_no_show",
                "scheduled_start": "2026-09-01T09:00:00",
                "visit_type_code": "REG",
                "calendar_source_kind": "regular",
            },
            {
                "classification": "probable_no_show",
                "scheduled_start": "2026-09-01T10:00:00",
                "visit_type_code": "UNKNOWN",
                "calendar_source_kind": "regular",
            },
            {
                "classification": "confirmed_no_show",
                "scheduled_start": "2026-09-01T11:00:00",
                "visit_type_code": "REG",
                "calendar_source_kind": "pushed",
            },
        ],
        visit_type_names={"REG": "ביקור רגיל"},
    )

    coverage = result["no_show_classification_coverage"]
    assert coverage["total_no_show_signal_count"] == 3
    assert coverage["excluded_pushed_no_show_count"] == 1
    assert coverage["eligible_no_show_signal_count"] == 2
    assert coverage["classified_no_show_signal_count"] == 1
    assert coverage["unknown_no_show_signal_count"] == 1
    assert coverage["rate"] == 0.5
    assert result["measurement_status"] == "unavailable"
    assert "no_show_classified_coverage_below_minimum" in result[
        "comparison_unavailable_reasons"
    ]


def test_late_forecast_insights_are_clipped_without_merging_candidate_families():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][2]["data"]["node"]["template"]["code"]["value"]
    component = _langflow_first_component_class(code)()
    component.baseline = {
        "schedule": {
            "entries": [{
                "weekday_name": "שלישי",
                "shift_1": {"from": "09:15", "to": "10:30"},
                "shift_2": None,
            }]
        }
    }

    metrics = component.build().data["metrics"]
    insight = metrics["insight_candidates"][0]
    recommendations = metrics["recommendation_evidence"]

    assert (insight["time_from"], insight["time_to"]) == ("09:15", "10:00")
    assert insight["effective_window_clipped_to_baseline"] is True
    assert metrics["existing_calendar_settings"] == {"contract_version": "v1", "complete": True}
    assert recommendations["telephone_video_window_candidates"][0]["time_from"] == "09:15"
    assert recommendations["visit_type_allocation_candidates"][0]["time_from"] == "09:30"
    assert all(
        item[0]["existing_settings_context"]["comparison_status"] == "complete"
        for item in recommendations.values()
    )


def test_every_candidate_and_insight_has_period_and_verified_recurrence_basis():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][2]["data"]["node"]["template"]["code"]["value"]
    component = _langflow_first_component_class(code)()
    component.baseline = {
        "schedule": {
            "entries": [{
                "weekday_name": "שלישי",
                "shift_1": {"from": "09:15", "to": "10:30"},
                "shift_2": None,
            }]
        }
    }

    metrics = component.build().data["metrics"]
    isolated = metrics["recommendation_evidence"][
        "telephone_video_window_candidates"
    ][0]["factual_basis"]
    recurring = metrics["recommendation_evidence"][
        "visit_type_allocation_candidates"
    ][0]["factual_basis"]
    insight = metrics["insight_candidates"][0]["factual_basis"]

    assert isolated["period"]["from"] == "2026-01-05"
    assert isolated["period"]["to"] == "2026-06-28"
    assert isolated["support"]["numerator"] == 1
    assert isolated["support"]["denominator"] == 24
    assert isolated["recurrence"]["isolated"] is True
    assert isolated["recurrence"]["wording_allowed"] is False
    assert isolated["analysis_window"]["from"] == "2026-01-05"
    assert isolated["observed_pattern_span"]["occurrence_dates"] == ["2026-03-03"]
    assert (
        isolated["observed_pattern_span"]["distributed_across_analysis_window"]
        is False
    )
    assert (
        isolated["recurrence"]["throughout_period_wording_allowed"]
        is False
    )
    assert recurring["support"]["numerator"] == 23
    assert recurring["support"]["denominator"] == 24
    assert recurring["support"]["rate"] == 0.9583
    assert recurring["recurrence"]["wording_allowed"] is True
    assert recurring["contract_version"] == "v2"
    assert recurring["observed_pattern_span"]["first_occurrence_date"] == "2026-01-06"
    assert recurring["observed_pattern_span"]["last_occurrence_date"] == "2026-06-23"
    assert recurring["observed_pattern_span"]["active_date_count"] == 23
    assert (
        recurring["observed_pattern_span"]["distributed_across_analysis_window"]
        is True
    )
    assert recurring["recurrence"]["throughout_period_wording_allowed"] is True
    assert recurring["counts"]["logical_appointment_count"] == 231
    assert recurring["attributes"]["visit_type_name"] == "מעקב"
    assert insight["period"]["observed_weeks"] == 25
    assert component.persisted_metrics["recommendation_evidence"][
        "visit_type_allocation_candidates"
    ][0]["factual_basis"]["observed_pattern_span"]["last_occurrence_date"] == (
        "2026-06-23"
    )
    assert metrics["factual_basis_contract"]["contract_version"] == "v2"
    assert metrics["factual_basis_contract"][
        "isolated_events_must_not_be_described_as_recurring"
    ] is True
    assert metrics["factual_basis_contract"][
        "throughout_period_wording_requires_distributed_occurrences"
    ] is True


def test_occurrences_concentrated_in_part_of_window_fail_distribution_gate():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][2]["data"]["node"]["template"]["code"]["value"]
    component = _langflow_first_component_class(code)()
    dates = [
        (date(2026, 4, 5) + timedelta(days=7 * index)).isoformat()
        for index in range(8)
    ]
    basis = component._lior_grounding_factual_basis(
        {
            "decision_tier": "recommendation",
            "support_occurrence_count": 8,
            "eligible_occurrence_count": 24,
            "occurrence_dates": dates,
            "threshold_evaluation": {
                "required_support_for_recommendation": 8,
            },
        },
        {
            "analysis_context": {
                "decision_period": {
                    "from": "2026-01-05",
                    "to": "2026-06-28",
                },
            },
        },
    )

    assert basis["recurrence"]["wording_allowed"] is True
    assert basis["observed_pattern_span"]["first_occurrence_date"] == "2026-04-05"
    assert basis["observed_pattern_span"]["last_occurrence_date"] == "2026-05-24"
    assert (
        basis["observed_pattern_span"]["distributed_across_analysis_window"]
        is False
    )
    assert basis["recurrence"]["throughout_period_wording_allowed"] is False


def test_incomplete_pushed_occurrence_dates_cannot_authorize_span_wording():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][2]["data"]["node"]["template"]["code"]["value"]
    component = _langflow_first_component_class(code)()
    basis = component._lior_grounding_factual_basis(
        {
            "decision_tier": "recommendation",
            "source_kind": "pushed",
            "support_occurrence_count": 12,
            "eligible_occurrence_count": 24,
            "occurrence_dates": ["2026-03-09"],
            "threshold_evaluation": {
                "required_support_for_recommendation": 8,
            },
        },
        {
            "analysis_context": {
                "decision_period": {
                    "from": "2026-01-05",
                    "to": "2026-06-28",
                },
            },
        },
    )

    assert basis["support"]["numerator"] == 12
    assert basis["observed_pattern_span"]["active_date_count"] == 1
    assert basis["observed_pattern_span"]["occurrence_dates_complete"] is False
    assert (
        basis["observed_pattern_span"]["distributed_across_analysis_window"]
        is False
    )
    assert basis["recurrence"]["throughout_period_wording_allowed"] is False


def test_booked_but_unused_reserve_is_measured_as_zero_not_unavailable():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][1]["data"]["node"]["template"]["code"]["value"]
    namespace = _patched_namespace(code, {"visit_types": []})
    component = namespace["DecisionKPIAnalyzer"]()
    component.historical = {
        "reserve_to_visit_reconciliation": {
            "measurement_status": "available",
            "matched_reserve_appointment_ids": [],
            "matched_urgent_reserve_appointment_ids": [],
            "matches": [],
        }
    }
    reserve = component.analyze().data["existing_calendar_settings"]["reserves"][0]
    assert reserve["booked_segment_units"] == 2.0
    assert reserve["matched_actual_segment_units"] == 0.0
    assert reserve["matched_urgent_segment_units"] == 0.0
    assert reserve["actualization"]["status"] == "available"
    assert reserve["actualization"]["value"] == 0.0
    assert reserve["actualization"]["urgent_share"] is None


def test_real_snapshot_composes_after_v1_and_all_embedded_python_parses():
    source = Path("/tmp/lf-analytics-lior.json")
    if not source.exists():
        raise unittest.SkipTest("offline source snapshot is not present")

    from tools.apply_existing_calendar_settings_ticket import patch_analytics

    flow = json.loads(source.read_text())
    for node in flow["data"]["nodes"]:
        code = (((node.get("data") or {}).get("node") or {}).get("template") or {}).get("code")
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            code["value"] = code["value"].replace("\r\n", "\n")
    patch_analytics(flow)
    assert patch_analytics_v2(flow) is flow
    decision_code = next(
        node["data"]["node"]["template"]["code"]["value"]
        for node in flow["data"]["nodes"]
        if node.get("id") == "decision_kpi_analyzer-IBs8T"
    )
    assert "LIOR_ANALYTICS_OCCURRENCE_DATES_V2" in decision_code
    assert decision_code.count('"occurrence_dates"') >= 12
    pressure_code = next(
        node["data"]["node"]["template"]["code"]["value"]
        for node in flow["data"]["nodes"]
        if node.get("id") == "urgent_reserve_pressure_analyzer-m0uiz"
    )
    assert "LIOR_ANALYTICS_PUSHED_OCCURRENCE_DATES_V2" in pressure_code
    assert '"occurrence_dates": sorted(g["dates"])' in pressure_code
    assert '"first_occurrence_date": p.get("first_occurrence_date")' in pressure_code
    builder_code = next(
        node["data"]["node"]["template"]["code"]["value"]
        for node in flow["data"]["nodes"]
        if node.get("id") == "analytics_feature_builder-f0hrQ"
    )
    assert "LIOR_ANALYTICS_PUSHED_OCCURRENCE_PROPAGATION_V2" in builder_code
    assert '"occurrence_dates": list(row.get("occurrence_dates") or [])' in builder_code
    first_pass = {
        node["id"]: (((node.get("data") or {}).get("node") or {}).get("template") or {})["code"]["value"]
        for node in flow["data"]["nodes"]
        if node.get("id") in {
            "historical_performance_analyzer-cDHUJ",
            "decision_kpi_analyzer-IBs8T",
            "analytics_feature_builder-f0hrQ",
            "urgent_reserve_pressure_analyzer-m0uiz",
        }
    }
    assert patch_analytics_v2(flow) is flow

    for node in flow["data"]["nodes"]:
        code = (((node.get("data") or {}).get("node") or {}).get("template") or {}).get("code")
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            tree = ast.parse(code["value"])
            if node.get("id") in first_pass:
                expected_name = {
                    "historical_performance_analyzer-cDHUJ": "HistoricalPerformanceAnalyzer",
                    "decision_kpi_analyzer-IBs8T": "DecisionKPIAnalyzer",
                    "analytics_feature_builder-f0hrQ": "AnalyticsFeatureBuilder",
                    "urgent_reserve_pressure_analyzer-m0uiz": "UrgentReservePressureAnalyzer",
                }[node["id"]]
                assert sum(
                    isinstance(item, ast.ClassDef) and item.name == expected_name
                    for item in tree.body
                ) == 1
                assert code["value"] == first_pass[node["id"]]


def test_reconciliation_failure_uses_stable_public_reason_and_warning():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    code = patch_analytics_v2(flow)["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"]

    class BrokenEngine:
        def connect(self):
            raise RuntimeError("postgresql://user:secret@example.invalid/private")

    namespace = _embedded_globals()
    namespace["get_cached_engine"] = lambda _url: BrokenEngine()
    tree = ast.parse(code)
    first_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "HistoricalPerformanceAnalyzer"
    )
    exec(
        compile(ast.Module(body=[first_class], type_ignores=[]), "<langflow-extracted>", "exec"),
        namespace,
    )
    component = namespace["HistoricalPerformanceAnalyzer"]()
    component.baseline = {
        "analysis_run_id": 9,
        "analysis_period": {"from": "2026-09-01", "to": "2026-09-30"},
        "segment": {"regular_segment_minutes": 15},
    }

    result = component.analyze().data
    reconciliation = result["reserve_to_visit_reconciliation"]
    assert reconciliation["measurement_status"] == "unavailable"
    assert reconciliation["unavailable_reason"] == "reserve_to_visit_reconciliation_failed"
    assert "secret" not in json.dumps(result)
    assert result["warnings"] == [
        "Reserve-to-visit reconciliation is unavailable; primary analytics remain valid."
    ]


def test_reserve_reconciliation_rejects_unrelated_same_day_visits():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    namespace = _patched_namespace(
        code,
        {
            "appointments": [{
                "appointment_id": 7,
                "member_id": "A",
                "appointment_date": "2026-09-01",
                "appointment_time": "09:00",
                "calendar_status": "עתודה",
                "appointment_type_code": "0",
                "visit_duration": 15,
            }],
            "visits": [{
                "visit_id": 107,
                "customer_id": "A",
                "encounter_start_datetime": "2026-09-01T15:00:00",
            }],
        },
    )
    component = namespace["HistoricalPerformanceAnalyzer"]()
    component.baseline = {
        "analysis_run_id": 9,
        "analysis_period": {"from": "2026-09-01", "to": "2026-09-30"},
        "segment": {"regular_segment_minutes": 15},
    }
    result = component.analyze().data["reserve_to_visit_reconciliation"]
    assert result["matched_reserve_appointment_ids"] == []
    assert result["summary"]["matched_reserve_events"] == 0
    assert result["summary"]["unmatched_booked_reserve_events"] == 1


def test_decision_v2_upgrade_tolerates_nullable_nested_contracts():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patch_analytics_v2(flow)
    upgrade_analytics_v2_nullsafe(flow)
    upgrade_analytics_v2_nullsafe(flow)
    code = flow["data"]["nodes"][1]["data"]["node"]["template"]["code"]["value"]
    namespace = _patched_namespace(code, {"visit_types": []})
    component = namespace["DecisionKPIAnalyzer"]()
    component._lior_v2_original_analyze = lambda: Data(data={
        "existing_calendar_settings": {
            "complete": True,
            "preferences": None,
            "reserves": None,
        },
        "findings": None,
        "warnings": None,
    })
    component.historical = None
    result = component.analyze().data
    assert result["warnings"] == []
    assert result["findings"]["reserves"][
        "reserve_to_visit_reconciliation_measurement_status"
    ] == "unavailable"
    assert code.count("LIOR_ANALYTICS_V2_DECISION_NULLSAFE_ACTIVE") == 1


def test_required_analysis_domains_are_persisted_even_without_recommendations():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patched = patch_analytics_v2(flow)
    code = patched["data"]["nodes"][2]["data"]["node"]["template"]["code"]["value"]
    component = _langflow_first_component_class(code)()
    component.baseline = {
        "schedule": {
            "entries": [{
                "weekday_name": "שלישי",
                "shift_1": {"from": "09:00", "to": "12:00"},
                "shift_2": None,
            }]
        }
    }
    component.decision_kpis = {
        "required_analysis_inputs": {
            "segment_duration_by_visit_type": {
                "measurement_status": "available",
                "measurement_source": "documented_actual_duration",
                "current_regular_segment_minutes": 15,
                "by_visit_type": [{
                    "visit_type_code": "FUP",
                    "visit_type_name": "מעקב",
                    "matched_visit_count": 12,
                    "median_actual_duration_minutes": 13,
                    "p75_actual_duration_minutes": 16,
                    "median_difference_from_segment_minutes": -2,
                }],
            },
            "no_show_by_modality": {
                "measurement_status": "available",
                "modalities": {
                    "face_to_face": {
                        "logical_appointment_count": 100,
                        "no_show_count": 10,
                        "no_show_rate": 0.1,
                    },
                    "telephone_video": {
                        "logical_appointment_count": 40,
                        "no_show_count": 2,
                        "no_show_rate": 0.05,
                    },
                },
                "comparison": {
                    "rate_difference_percentage_points": 5.0,
                    "higher_no_show_modality": "face_to_face",
                },
            },
        },
        "findings": {
            "no_show": {
                "combined_no_show_signal_count": 12,
                "by_weekday": [{
                    "weekday": "שלישי",
                    "combined_no_show_signal_count": 12,
                }],
                "by_60_minute_window": [{
                    "weekday": "שלישי",
                    "time_from": "09:00",
                    "time_to": "10:00",
                    "combined_no_show_signal_count": 4,
                    "combined_no_show_signal_rate_in_window": 0.08,
                }],
            },
        },
        "existing_calendar_settings": {
            "contract_version": "v1",
            "complete": True,
            "inventory_status": "available",
            "reserves": [{
                "setting_id": "reserve::שלישי::10:00::11:00",
                "weekday": "שלישי",
                "time_from": "10:00",
                "time_to": "11:00",
                "defined_segment_units": 4,
                "booked_segment_units": 2,
                "matched_actual_segment_units": 1,
                "utilization": {"status": "available", "value": 0.5},
                "actualization": {"status": "available", "value": 0.5},
            }],
        },
    }

    metrics = component.build().data["metrics"]
    domains = metrics["required_analysis_domains"]

    assert set(domains) == {
        "segment_duration_by_visit_type",
        "no_show_by_weekday_hour",
        "no_show_by_modality",
        "reserve_utilization",
    }
    assert domains["segment_duration_by_visit_type"]["status"] == "checked"
    assert domains["segment_duration_by_visit_type"]["by_visit_type"][0][
        "median_actual_duration_minutes"
    ] == 13
    assert domains["no_show_by_weekday_hour"]["by_60_minute_window"][0][
        "combined_no_show_signal_count"
    ] == 4
    assert domains["no_show_by_modality"]["modalities"]["face_to_face"][
        "no_show_rate"
    ] == 0.1
    assert domains["reserve_utilization"]["reserves"][0]["actualization"][
        "value"
    ] == 0.5
    assert all(
        domain["recommendation_found"] is False
        and domain["outcome"] == "no_change_recommended"
        for domain in domains.values()
    )
    assert component.persisted_metrics["required_analysis_domains"] == domains


def test_incomplete_modality_comparison_never_becomes_no_change_recommended():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    code = patch_analytics_v2(flow)["data"]["nodes"][2]["data"]["node"]["template"]["code"]["value"]
    component = _langflow_first_component_class(code)()
    component.baseline = {
        "schedule": {
            "entries": [{
                "weekday_name": "שלישי",
                "shift_1": {"from": "09:00", "to": "12:00"},
                "shift_2": None,
            }]
        }
    }
    component.decision_kpis = {
        "required_analysis_inputs": {
            "no_show_by_modality": {
                "measurement_status": "unavailable",
                "comparison_unavailable_reasons": [
                    "telephone_video_group_empty"
                ],
                "classification_coverage": {
                    "classified_appointment_count": 100,
                    "total_appointment_count": 100,
                    "rate": 1.0,
                    "minimum_required_rate": 0.8,
                },
                "modalities": {
                    "face_to_face": {"logical_appointment_count": 100},
                    "telephone_video": {"logical_appointment_count": 0},
                    "unknown": {"logical_appointment_count": 0},
                },
            }
        },
        "findings": {"no_show": {}},
        "existing_calendar_settings": {
            "complete": True,
            "inventory_status": "available",
            "reserves": [],
        },
    }

    domain = component.build().data["metrics"]["required_analysis_domains"][
        "no_show_by_modality"
    ]

    assert domain["status"] == "unavailable"
    assert domain["checked"] is False
    assert domain["outcome"] == "comparison_incomplete"
    assert domain["no_recommendation_reason"] == "comparison_incomplete"


def test_langflow_1_9_2_output_methods_keep_data_return_types():
    flow = _flow(HISTORICAL_COMPONENT, DECISION_COMPONENT, BUILDER_COMPONENT)
    patch_analytics_v2(flow)
    upgrade_analytics_v2_nullsafe(flow)
    upgrade_analytics_v2_return_types(flow)
    expected = {
        "historical_performance_analyzer-cDHUJ": (
            "HistoricalPerformanceAnalyzer",
            "analyze",
        ),
        "decision_kpi_analyzer-IBs8T": ("DecisionKPIAnalyzer", "analyze"),
        "analytics_feature_builder-f0hrQ": ("AnalyticsFeatureBuilder", "build"),
    }
    for node in flow["data"]["nodes"]:
        if node["id"] not in expected:
            continue
        class_name, method_name = expected[node["id"]]
        tree = ast.parse(node["data"]["node"]["template"]["code"]["value"])
        component_class = next(
            item
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == class_name
        )
        method = next(
            item
            for item in component_class.body
            if isinstance(item, ast.FunctionDef) and item.name == method_name
        )
        assert ast.unparse(method.returns) == "Data"


class AnalyticsV2ContractTests(unittest.TestCase):
    def test_reserve_reconciliation_contract(self):
        test_reserve_reconciliation_is_separate_from_primary_analytics()

    def test_decision_output_contract(self):
        test_decision_output_resolves_preference_and_measures_reserve()

    def test_late_forecast_insight_contract(self):
        test_late_forecast_insights_are_clipped_without_merging_candidate_families()

    def test_factual_basis_contract(self):
        test_every_candidate_and_insight_has_period_and_verified_recurrence_basis()

    def test_unused_reserve_contract(self):
        test_booked_but_unused_reserve_is_measured_as_zero_not_unavailable()

    def test_real_snapshot_composition(self):
        test_real_snapshot_composes_after_v1_and_all_embedded_python_parses()

    def test_stable_unavailable_contract(self):
        test_reconciliation_failure_uses_stable_public_reason_and_warning()

    def test_unrelated_visit_is_not_actualized(self):
        test_reserve_reconciliation_rejects_unrelated_same_day_visits()

    def test_nullable_decision_contract(self):
        test_decision_v2_upgrade_tolerates_nullable_nested_contracts()

    def test_langflow_output_types(self):
        test_langflow_1_9_2_output_methods_keep_data_return_types()
