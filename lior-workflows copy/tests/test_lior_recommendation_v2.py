from __future__ import annotations

import ast
import json
import sys
import types
from datetime import date, timedelta
from pathlib import Path

import pytest

from tools.apply_existing_calendar_settings_ticket import patch_recommendation
from tools.lior_recommendation_v2 import (
    patch_recommendation_v2,
    upgrade_recommendation_v2_return_types,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FLOW = Path("/tmp/lf-rec-lior.json")
BUSINESS_ID = "recommendation_business_rule_validator-TvYcq"
PRESENTER_ID = "recommendation_presenter-TuUXM"


class _Data:
    def __init__(self, data=None, **kwargs):
        self.data = data if data is not None else kwargs


class _Message:
    def __init__(self, text="", **kwargs):
        self.text = text
        self.data = kwargs


class _Component:
    pass


class _Field:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


@pytest.fixture(scope="module")
def patched_flow():
    flow = json.loads(SOURCE_FLOW.read_text())
    for node in flow["data"]["nodes"]:
        code = (
            ((node.get("data") or {}).get("node") or {})
            .get("template", {})
            .get("code")
        )
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            code["value"] = code["value"].replace("\r\n", "\n")
    patch_recommendation(flow)
    returned = patch_recommendation_v2(flow)
    assert returned is flow
    return flow


def _node(flow, node_id):
    return next(node for node in flow["data"]["nodes"] if node["id"] == node_id)


def _install_langflow_stubs(monkeypatch):
    modules = {
        "langflow": types.ModuleType("langflow"),
        "langflow.custom": types.ModuleType("langflow.custom"),
        "langflow.custom.custom_component": types.ModuleType(
            "langflow.custom.custom_component"
        ),
        "langflow.custom.custom_component.component": types.ModuleType(
            "langflow.custom.custom_component.component"
        ),
        "langflow.io": types.ModuleType("langflow.io"),
        "langflow.schema": types.ModuleType("langflow.schema"),
        "langflow.schema.data": types.ModuleType("langflow.schema.data"),
        "langflow.schema.message": types.ModuleType("langflow.schema.message"),
    }
    modules["langflow.custom.custom_component.component"].Component = _Component
    modules["langflow.io"].DataInput = _Field
    modules["langflow.io"].BoolInput = _Field
    modules["langflow.io"].Output = _Field
    modules["langflow.schema.data"].Data = _Data
    modules["langflow.schema.message"].Message = _Message
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def _component_class(flow, node_id, class_name, monkeypatch):
    _install_langflow_stubs(monkeypatch)
    code = _node(flow, node_id)["data"]["node"]["template"]["code"]["value"]
    tree = ast.parse(code)
    first_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    loader_tree = ast.Module(
        body=[
            node
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        + [first_class],
        type_ignores=[],
    )
    ast.fix_missing_locations(loader_tree)
    namespace = {}
    exec(compile(loader_tree, f"<first-{node_id}>", "exec"), namespace)
    return namespace[class_name]


def _inventory(*, preference=None, reserve=None):
    return {
        "contract_version": "v1",
        "complete": True,
        "inventory_status": "available",
        "preferences": [preference] if preference else [],
        "reserves": [reserve] if reserve else [],
    }


def _setting(setting_type, *, start="09:00", end="10:00", compliance=None):
    setting = {
        "setting_id": f"{setting_type}::ראשון::{start}::{end}",
        "setting_type": setting_type,
        "weekday": "ראשון",
        "time_from": start,
        "time_to": end,
        "defined_segment_units": 8,
        "booked_segment_units": 6,
        "matched_actual_segment_units": 4.25,
        "matched_urgent_segment_units": 3,
        "utilization": {"status": "available", "value": 0.75},
        "actualization": {"status": "available", "value": 4.25 / 6},
    }
    if setting_type == "preference":
        setting.update(
            {
                "preferred_visit_types": [
                    {
                        "preferred_visit_type_code": "17",
                        "preferred_label": "raw-code-label",
                        "preferred_visit_type_name": "ייעוץ מורכב",
                    }
                ],
                "actual_booked_visit_type_mix": [
                    {"visit_type_name": "ייעוץ מורכב", "segment_units": 6}
                ],
                "compliance": {
                    "status": "available",
                    "value": compliance,
                    "comparable_booked_segments": 1,
                },
            }
        )
    return setting


def _candidate(path, action, start="09:00", end="10:00", **extra):
    return {
        "candidate_id": path.rsplit("[", 1)[-1].rstrip("]"),
        "metric_path": path,
        "candidate_type": path.split(".")[1].split("[")[0],
        "action": action,
        "allowed_action": action,
        "weekday": "ראשון",
        "time_from": start,
        "time_to": end,
        "exact_allocation_window": True,
        **extra,
    }


def _factual_basis(
    *,
    numerator,
    denominator,
    wording_allowed,
    encounters=None,
    start="09:00",
    end="10:00",
    attributes=None,
    occurrence_dates=None,
    distributed=False,
):
    counts = {}
    if encounters is not None:
        counts["encounter_count"] = encounters
    basis = {
        "contract_version": "v2" if occurrence_dates is not None else "v1",
        "complete": True,
        "period": {
            "from": "2026-01-05",
            "to": "2026-06-28",
            "scope": "decision_period",
            "observed_weeks": 25,
        },
        "window": {
            "weekday": "ראשון",
            "time_from": start,
            "time_to": end,
        },
        "target_window": None,
        "support": {
            "numerator": numerator,
            "numerator_field": "support_occurrence_count",
            "denominator": denominator,
            "denominator_field": "eligible_occurrence_count",
            "rate": numerator / denominator,
            "rate_field": "computed",
            "required": 8,
            "required_field": "required_support_for_recommendation",
        },
        "counts": counts,
        "attributes": dict(attributes or {}),
        "threshold_evaluation": {
            "required_support_for_recommendation": 8,
        },
        "recurrence": {
            "wording_allowed": wording_allowed,
            "isolated": numerator <= 1,
            "tier": "recommendation",
            "evidence_type": "digital_admin_window",
        },
    }
    if occurrence_dates is not None:
        dates = sorted(occurrence_dates)
        basis["analysis_window"] = {
            "from": "2026-01-05",
            "to": "2026-06-28",
            "scope": "decision_period",
        }
        basis["observed_pattern_span"] = {
            "first_occurrence_date": dates[0] if dates else None,
            "last_occurrence_date": dates[-1] if dates else None,
            "occurrence_dates": dates,
            "active_date_count": len(dates),
            "distributed_across_analysis_window": distributed,
        }
        basis["recurrence"]["throughout_period_wording_allowed"] = bool(
            wording_allowed and distributed
        )
    return basis


def _business_context(candidates, inventory):
    actionable = {}
    for candidate in candidates:
        family = candidate["metric_path"].split(".")[1].split("[")[0]
        actionable.setdefault(family, []).append(
            {"metric_path": candidate["metric_path"], "value": candidate}
        )
    return {
        "analysis_run_id": 44,
        "analysis_context": {
            "value": {
                "decision_period": {
                    "from": "2026-01-05",
                    "to": "2026-06-28",
                }
            }
        },
        "baseline_constraints": {
            "value": {
                "working_windows": [
                    {
                        "weekday_name": "ראשון",
                        "shift_1": {"from": "08:00", "to": "13:00"},
                    }
                ]
            }
        },
        "existing_calendar_settings": {"value": inventory},
        "evidence_pack": {"actionable": actionable, "conflicts": []},
    }


def _llm_payload(candidates):
    return {
        "analysis_run_id": 44,
        "recommendations": [
            {
                "recommendation_type": "draft",
                "calendar_action": {"action": candidate["action"]},
                "evidence": [
                    {
                        "verified": True,
                        "metric_path": candidate["metric_path"],
                        "actual_metric_value": candidate,
                    }
                ],
            }
            for candidate in candidates
        ],
    }


def _validated(flow, monkeypatch, candidates, inventory):
    cls = _component_class(
        flow,
        BUSINESS_ID,
        "RecommendationBusinessRuleValidator",
        monkeypatch,
    )
    component = cls()
    component.validated_recommendations = _Data(_llm_payload(candidates))
    component.business_context = _Data(_business_context(candidates, inventory))
    return component.validate().data


def _present(flow, monkeypatch, payload):
    cls = _component_class(
        flow, PRESENTER_ID, "RecommendationPresenter", monkeypatch
    )
    component = cls()
    component.validated_recommendations = _Data(payload)
    return component.build_data().data, component.build_message().text


def test_full_composition_uses_guarded_anchors_and_parses_every_component(patched_flow):
    patch_recommendation_v2(patched_flow)
    for node in patched_flow["data"]["nodes"]:
        code = (
            ((node.get("data") or {}).get("node") or {})
            .get("template", {})
            .get("code", {})
            .get("value")
        )
        if isinstance(code, str):
            ast.parse(code)


def test_business_validator_keeps_langflow_1_9_2_data_output(patched_flow):
    upgrade_recommendation_v2_return_types(patched_flow)
    code = _node(patched_flow, BUSINESS_ID)["data"]["node"]["template"]["code"]["value"]
    tree = ast.parse(code)
    component_class = next(
        item
        for item in tree.body
        if isinstance(item, ast.ClassDef)
        and item.name == "RecommendationBusinessRuleValidator"
    )
    method = next(
        item
        for item in component_class.body
        if isinstance(item, ast.FunctionDef) and item.name == "validate"
    )
    assert ast.unparse(method.returns) == "Data"


def test_langflow_first_extracted_classes_are_the_only_active_definitions(
    patched_flow, monkeypatch
):
    expectations = {
        BUSINESS_ID: (
            "RecommendationBusinessRuleValidator",
            {"_lior_v2_family", "_lior_v2_preference_resolution", "validate"},
        ),
        PRESENTER_ID: (
            "RecommendationPresenter",
            {"_lior_v2_reserve_detail", "_lior_v2_impact_text", "_text_out"},
        ),
    }
    for node_id, (class_name, required_methods) in expectations.items():
        code = _node(patched_flow, node_id)["data"]["node"]["template"]["code"]["value"]
        classes = [
            node
            for node in ast.parse(code).body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        assert len(classes) == 1
        first_method_names = {
            node.name
            for node in classes[0].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert required_methods <= first_method_names
        loaded = _component_class(
            patched_flow, node_id, class_name, monkeypatch
        )
        assert required_methods <= set(vars(loaded))


def test_full_compliance_uses_resolved_name_and_keeps_current_preference(
    patched_flow, monkeypatch
):
    path = "recommendation_evidence.visit_type_allocation_candidates[0]"
    candidate = _candidate(
        path,
        "allocate_visit_type_window",
        visit_type_name="ייעוץ מורכב",
        recommended_minutes=30,
    )
    result = _validated(
        patched_flow,
        monkeypatch,
        [candidate],
        _inventory(preference=_setting("preference", compliance=1.0)),
    )

    rec = result["recommendations"][0]
    assert rec["preference_resolution"]["state"] == "preserve"
    assert rec["preference_resolution"]["resolved_preference_names"] == [
        "ייעוץ מורכב"
    ]
    assert rec["calendar_action"]["recommendation_mode"] == "keep_current"

    _, message = _present(patched_flow, monkeypatch, result)
    assert "ייעוץ מורכב" in message
    assert "לשמור על ההעדפה הקיימת" in message
    assert "בכל 1 המקטעים שניתנו להשוואה" in message
    assert "לרכז יותר" not in message
    assert "מדגם" not in message
    assert "שמירה על ההתאמה בין ההעדפה הקיימת" in message
    assert "ריכוז תפעולי עקבי יותר" not in message


def test_full_compliance_conflict_keeps_current_until_resolution(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.visit_type_allocation_candidates[0]",
        "allocate_visit_type_window",
        visit_type_name="מעקב קצר",
        recommended_minutes=30,
    )
    result = _validated(
        patched_flow,
        monkeypatch,
        [candidate],
        _inventory(preference=_setting("preference", compliance=1.0)),
    )
    rec = result["recommendations"][0]
    assert rec["preference_resolution"]["state"] == "conflict"
    assert rec["calendar_action"]["recommendation_mode"] == (
        "keep_current_pending_conflict_resolution"
    )
    _, message = _present(patched_flow, monkeypatch, result)
    assert "עד ליישוב הקונפליקט" in message
    assert "לרכז יותר" not in message


def test_telephone_action_semantically_matches_resolved_hebrew_preference(
    patched_flow, monkeypatch
):
    preference = _setting("preference", compliance=1.0)
    preference["preferred_visit_types"] = [
        {
            "preferred_code": "000GH",
            "preferred_label": "000GH",
            "preferred_name": "תור טלפוני",
        }
    ]
    candidate = _candidate(
        "recommendation_evidence.telephone_video_window_candidates[0]",
        "allocate_telephone_video_visit_window",
        recommended_minutes=30,
    )
    result = _validated(
        patched_flow,
        monkeypatch,
        [candidate],
        _inventory(preference=preference),
    )
    rec = result["recommendations"][0]
    assert rec["preference_resolution"]["state"] == "preserve"
    assert rec["preference_resolution"]["resolved_preference_names"] == [
        "תור טלפוני"
    ]
    assert rec["calendar_action"]["recommendation_mode"] == "keep_current"
    _, message = _present(patched_flow, monkeypatch, result)
    assert "לשמור על ההעדפה הקיימת" in message
    assert "לרכז יותר" not in message


@pytest.mark.parametrize("overlaps", [True, False])
def test_every_urgent_reserve_states_overlap_and_reports_available_quantities(
    patched_flow, monkeypatch, overlaps
):
    path = "recommendation_evidence.urgent_reserve_candidates[0]"
    candidate = _candidate(
        path,
        "allocate_reserve",
        recommended_reserve_minutes=30,
        recommended_reserve_slots=2,
    )
    reserve = _setting(
        "reserve",
        start="09:00" if overlaps else "11:00",
        end="10:00" if overlaps else "12:00",
    )
    result = _validated(
        patched_flow, monkeypatch, [candidate], _inventory(reserve=reserve)
    )

    rec = result["recommendations"][0]
    assert rec["reserve_overlap"]["overlaps"] is overlaps
    if overlaps:
        assert rec["calendar_action"]["reserve_handling"] == (
            "adjust_existing_reserve_not_add"
        )
        assert rec["reserve_overlap"]["quantities"] == {
            "defined": 8,
            "booked": 6,
            "matched_actual": 4.25,
            "matched_urgent": 3,
        }

    _, message = _present(patched_flow, monkeypatch, result)
    assert (
        "חופפת לעתודה קיימת" in message
        if overlaps
        else "אינה חופפת לעתודה קיימת" in message
    )
    if overlaps:
        assert "להתאים את העתודה הקיימת" in message
        assert "מוגדרות 8" in message
        assert "נקבעו 6" in message
        assert "מומשו בפועל 4.25" in message
        assert "מהם 3 דחופים" in message


def test_unavailable_reserve_measurement_is_disclosed_honestly(
    patched_flow, monkeypatch
):
    path = "recommendation_evidence.urgent_reserve_candidates[0]"
    candidate = _candidate(path, "allocate_reserve", recommended_reserve_minutes=20)
    reserve = _setting("reserve")
    reserve["matched_actual_segment_units"] = None
    reserve["matched_urgent_segment_units"] = None
    reserve["actualization"] = {
        "status": "unavailable",
        "value": None,
        "unavailable_reason": "reconciliation unavailable",
    }
    result = _validated(
        patched_flow, monkeypatch, [candidate], _inventory(reserve=reserve)
    )
    rec = result["recommendations"][0]
    assert rec["reserve_overlap"]["measurement_status"] == "unavailable"
    _, message = _present(patched_flow, monkeypatch, result)
    assert "נתוני המימוש בפועל והדחיפות אינם זמינים" in message
    assert "ולא פורשו כאפס" in message


def test_incomplete_settings_inventory_blocks_calendar_change(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.urgent_reserve_candidates[0]",
        "allocate_reserve",
        recommended_reserve_minutes=20,
    )
    inventory = _inventory()
    inventory["complete"] = False
    inventory["inventory_status"] = "incomplete"
    result = _validated(patched_flow, monkeypatch, [candidate], inventory)
    assert result["valid"] is False
    assert result["recommendations"] == []
    assert any("מלאי ההעדפות והעתודות" in warning for warning in result["warnings"])


def test_quantified_urgent_reserve_suppresses_same_window_buffer_with_non_exact_precision(
    patched_flow, monkeypatch
):
    urgent = _candidate(
        "recommendation_evidence.urgent_reserve_candidates[0]",
        "allocate_reserve",
        recommended_reserve_minutes=30,
        action_precision="quantity_within_hour",
    )
    buffer = _candidate(
        "recommendation_evidence.operational_buffer_candidates[0]",
        "protect_flexible_capacity",
        recommended_minutes=15,
    )
    urgent["exact_allocation_window"] = False
    buffer["exact_allocation_window"] = False
    result = _validated(
        patched_flow, monkeypatch, [buffer, urgent], _inventory()
    )

    assert [r["calendar_action"]["action"] for r in result["recommendations"]] == [
        "allocate_reserve"
    ]
    assert result["recommendations"][0]["calendar_action"]["allocation_precision"] == (
        "quantity_within_hour"
    )
    disposition = next(
        item
        for item in result["candidate_dispositions"]
        if item["metric_path"] == buffer["metric_path"]
    )
    assert disposition["disposition"] == "supporting_evidence"
    assert disposition["reason"] == (
        "same_planning_window_quantified_urgent_reserve_preferred_no_double_allocation"
    )
    assert result["validation"]["urgent_buffer_resolution_rechecked"] is True
    assert (
        result["validation"]["planning_window_double_allocation_remaining"] is False
    )
    assert result["validation"]["exact_window_double_allocation_remaining"] is False


def test_weekday_insights_are_hidden_while_general_insights_are_preserved(
    patched_flow, monkeypatch
):
    payload = {
        "recommendations": [],
        "analytics_insights": [
            {
                "insight_type": "recurring_delay_recommendation_strength",
                "weekday": "ראשון",
                "time_from": "09:00",
                "time_to": "10:00",
            },
            {
                "insight_type": "recurring_delay_below_action_threshold",
                "weekday": "ראשון",
                "time_from": "09:00",
                "time_to": "10:00",
            },
            {"insight_type": "forecast_change"},
            {
                "insight_type": "forecast_change",
                "direction": "increase",
                "magnitude": 12.345,
                "magnitude_unit": "percent",
            },
        ],
    }
    _, message = _present(patched_flow, monkeypatch, payload)
    assert "תובנות לפי ימי השבוע" not in message
    assert "התורים נוטים להתחיל באיחור" not in message
    assert "תובנות כלליות" in message
    assert "המגמה בתקופה האחרונה מצביעה על שינוי אפשרי" not in message
    assert message.count("תחזית") == 1
    assert "עלייה" in message
    assert "12.35%" in message


def test_expected_impact_is_qualitative_without_invented_numeric_impact(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.urgent_reserve_candidates[0]",
        "allocate_reserve",
        recommended_reserve_minutes=25,
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    impact = result["recommendations"][0]["expected_operational_impact"]
    assert impact["qualitative"]
    assert impact["numeric"] is None
    assert impact["numeric_source"] == "no_verified_candidate_impact_quantity"
    _, message = _present(patched_flow, monkeypatch, result)
    assert "**השפעה תפעולית צפויה:**" in message


def test_recurring_recommendation_displays_period_window_and_frequency(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        encounter_count=231,
        factual_basis=_factual_basis(
            numerator=23,
            denominator=24,
            wording_allowed=True,
            encounters=231,
        ),
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    rec = result["recommendations"][0]
    assert rec["factual_basis"]["support"]["numerator"] == 23
    assert result["validation"]["factual_basis_complete_for_recommendations"] is True

    _, message = _present(patched_flow, monkeypatch, result)
    assert "**תקופת הנתונים:** 05.01.2026–28.06.2026." in message
    assert "בסיס הנתונים:" in message
    assert "נתונים מ־05.01.2026 עד 28.06.2026" in message
    assert "יום ראשון, 09:00–10:00" in message
    assert "הדפוס חזר ב־23 מתוך 24 מועדים רלוונטיים" in message
    assert "95.83 אחוזים" in message
    assert "ביקורים מתועדים: 231" in message


def test_distributed_pattern_renders_analysis_window_span_and_frequency(
    patched_flow, monkeypatch
):
    occurrence_dates = [
        (date(2026, 1, 11) + timedelta(days=7 * index)).isoformat()
        for index in range(24)
        if index not in {4, 11, 18}
    ]
    candidate = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        factual_basis=_factual_basis(
            numerator=21,
            denominator=24,
            wording_allowed=True,
            occurrence_dates=occurrence_dates,
            distributed=True,
        ),
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    _, message = _present(patched_flow, monkeypatch, result)

    assert "חלון הניתוח: 05.01–28.06" in message
    assert "הדפוס הופיע לאורך התקופה בין 11.01 ל־21.06" in message
    assert "ב־21 מתוך 24 ימי ראשון רלוונטיים" in message
    assert "בשעות 09:00–10:00" in message
    assert "18.01" not in message
    assert "#### 09:00–10:00 | ריכוז פעילות דיגיטלית" in message


def test_concentrated_pattern_never_uses_throughout_period_wording(
    patched_flow, monkeypatch
):
    occurrence_dates = [
        (date(2026, 4, 5) + timedelta(days=7 * index)).isoformat()
        for index in range(8)
    ]
    candidate = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        interpretation="לאורך התקופה נמצא ריכוז פעילות.",
        factual_basis=_factual_basis(
            numerator=8,
            denominator=24,
            wording_allowed=True,
            occurrence_dates=occurrence_dates,
            distributed=False,
        ),
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    _, message = _present(patched_flow, monkeypatch, result)

    assert "הדפוס הופיע בין 05.04 ל־24.05" in message
    assert "לאורך התקופה" not in message


def test_incomplete_occurrence_dates_suppress_span_and_throughout_wording(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.operational_buffer_candidates[0]",
        "protect_flexible_capacity",
        interpretation="לאורך התקופה חזרו בזמן הזה תורים שנדחפו.",
        factual_basis=_factual_basis(
            numerator=12,
            denominator=24,
            wording_allowed=True,
            occurrence_dates=["2026-03-09"],
            distributed=True,
        ),
    )
    candidate["factual_basis"]["observed_pattern_span"][
        "occurrence_dates_complete"
    ] = False
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    _, message = _present(patched_flow, monkeypatch, result)

    assert "12 מתוך 24" in message
    assert "09.03" not in message
    assert "הדפוס הופיע" not in message
    assert "לאורך התקופה" not in message


def test_five_or_fewer_occurrences_render_every_exact_date(
    patched_flow, monkeypatch
):
    dates = ["2026-04-12", "2026-04-19", "2026-04-26"]
    candidate = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        factual_basis=_factual_basis(
            numerator=3,
            denominator=24,
            wording_allowed=False,
            occurrence_dates=dates,
            distributed=False,
        ),
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    _, message = _present(patched_flow, monkeypatch, result)

    assert "הדפוס הופיע בתאריכים: 12.04, 19.04 ו־26.04" in message
    assert "ב־3 מתוך 24 ימי ראשון רלוונטיים" in message


def test_same_window_with_different_occurrence_spans_has_distinct_signature(
    patched_flow, monkeypatch
):
    cls = _component_class(
        patched_flow,
        PRESENTER_ID,
        "RecommendationPresenter",
        monkeypatch,
    )
    first = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        factual_basis=_factual_basis(
            numerator=3,
            denominator=24,
            wording_allowed=False,
            occurrence_dates=["2026-01-11", "2026-01-18", "2026-01-25"],
        ),
    )
    second = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[1]",
        "allocate_digital_window",
        factual_basis=_factual_basis(
            numerator=3,
            denominator=24,
            wording_allowed=False,
            occurrence_dates=["2026-04-12", "2026-04-19", "2026-04-26"],
        ),
    )

    assert cls._lior_quality_basis_signature(first) != (
        cls._lior_quality_basis_signature(second)
    )


def test_isolated_event_is_quantified_and_never_described_as_recurring(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        encounter_count=2,
        factual_basis=_factual_basis(
            numerator=1,
            denominator=24,
            wording_allowed=False,
            encounters=2,
        ),
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    _, message = _present(patched_flow, monkeypatch, result)

    assert "הממצא נצפה ב־1 מתוך 24 מועדים רלוונטיים" in message
    assert "4.17 אחוזים" in message
    assert "הדפוס חזר" not in message
    assert "משמעותי" not in message
    assert "עקבי" not in message


def test_adjacent_same_family_windows_keep_distinct_factual_basis(
    patched_flow, monkeypatch
):
    first = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        start="09:00",
        end="10:00",
        factual_basis=_factual_basis(
            numerator=20,
            denominator=24,
            wording_allowed=True,
            start="09:00",
            end="10:00",
        ),
    )
    second = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[1]",
        "allocate_digital_window",
        start="10:00",
        end="11:00",
        factual_basis=_factual_basis(
            numerator=18,
            denominator=24,
            wording_allowed=True,
            start="10:00",
            end="11:00",
        ),
    )
    result = _validated(
        patched_flow, monkeypatch, [first, second], _inventory()
    )
    assert [
        (
            rec["calendar_action"]["time_from"],
            rec["calendar_action"]["time_to"],
        )
        for rec in result["recommendations"]
    ] == [("09:00", "10:00"), ("10:00", "11:00")]

    structured, message = _present(patched_flow, monkeypatch, result)
    assert [
        (group["time_from"], group["time_to"])
        for group in structured["presentation_groups"]
    ] == [("09:00", "10:00"), ("10:00", "11:00")]
    assert "יום ראשון, 09:00–10:00" in message
    assert "יום ראשון, 10:00–11:00" in message


def test_non_hebrew_attribute_removed_before_global_latin_sanitization(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        factual_basis=_factual_basis(
            numerator=20,
            denominator=24,
            wording_allowed=True,
            attributes={"modality": "Telephone"},
        ),
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    _, message = _present(patched_flow, monkeypatch, result)
    assert "מאפיין פעילות:" not in message
    assert "מאפיין פעילות: ." not in message


def test_occurrence_basis_omits_duplicate_active_days_and_dangling_separator(
    patched_flow, monkeypatch
):
    dates = [
        (date(2026, 1, 11) + timedelta(days=7 * index)).isoformat()
        for index in range(8)
    ]
    candidate = _candidate(
        "recommendation_evidence.digital_admin_window_candidates[0]",
        "allocate_digital_window",
        encounter_count=56,
        factual_basis=_factual_basis(
            numerator=8,
            denominator=24,
            wording_allowed=True,
            encounters=56,
            attributes={"modality": "telephone_video"},
            occurrence_dates=dates,
            distributed=False,
        ),
    )
    candidate["factual_basis"]["counts"]["active_date_count"] = 8
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    _, message = _present(patched_flow, monkeypatch, result)

    assert "ימים שבהם הממצא הופיע" not in message
    assert "ביקורים מתועדים: 56." in message
    assert "ביקורים מתועדים: 56;" not in message


def test_client_summary_rounding_and_recommendation_bullet_spacing(
    patched_flow, monkeypatch
):
    candidate = _candidate(
        "recommendation_evidence.urgent_reserve_candidates[0]",
        "allocate_reserve",
        recommended_reserve_minutes=25,
    )
    result = _validated(patched_flow, monkeypatch, [candidate], _inventory())
    result["performance_summary"] = {
        "weekly_working_hours": 25,
        "weekly_patient_visits": {"mean": 122.48},
        "no_show": {"average_combined_signal_per_week": 2.32},
        "delay": {"average_minutes": -2.62},
    }
    _, message = _present(patched_flow, monkeypatch, result)
    assert "122.5" in message
    assert "2.3" in message
    assert "2.6" in message
    assert "#### 09:00–10:00 |" in message
    assert "\n\n- **למה:**" in message


def test_weekly_schedule_is_interval_table_with_one_row_per_recommendation(
    patched_flow, monkeypatch
):
    reserve = _candidate(
        "recommendation_evidence.urgent_reserve_candidates[0]",
        "allocate_reserve",
        start="09:00",
        end="10:00",
        recommended_reserve_minutes=20,
    )
    buffer = _candidate(
        "recommendation_evidence.operational_buffer_candidates[0]",
        "protect_flexible_capacity",
        start="11:00",
        end="12:00",
        recommended_minutes=15,
    )
    result = _validated(
        patched_flow, monkeypatch, [reserve, buffer], _inventory()
    )
    _, message = _present(patched_flow, monkeypatch, result)
    schedule = message.split("## הלו״ז השבועי עם ההמלצות", 1)[1]
    rows = [
        line
        for line in schedule.splitlines()
        if line.startswith("| ראשון |")
    ]
    assert "| יום | שעות | המלצה |" in schedule
    assert rows == [
        "| ראשון | 08:00–09:00 | פעילות רגילה |",
        "| ראשון | 09:00–10:00 | שמירת 20 דקות לתורים דחופים |",
        "| ראשון | 10:00–11:00 | פעילות רגילה |",
        "| ראשון | 11:00–12:00 | השארת 15 דקות פנויות מראש לתורים שנדחפים |",
        "| ראשון | 12:00–13:00 | פעילות רגילה |",
    ]


def test_adjacent_windows_from_distinct_evidence_families_stay_distinct(
    patched_flow, monkeypatch
):
    first = _candidate(
        "recommendation_evidence.urgent_reserve_candidates[0]",
        "allocate_reserve",
        start="09:00",
        end="10:00",
        recommended_reserve_minutes=20,
    )
    second = _candidate(
        "recommendation_evidence.reserve_utilization_candidates[0]",
        "allocate_reserve",
        start="10:00",
        end="11:00",
        recommended_reserve_minutes=20,
    )
    cls = _component_class(
        patched_flow,
        BUSINESS_ID,
        "RecommendationBusinessRuleValidator",
        monkeypatch,
    )
    component = cls()
    component.validated_recommendations = _Data(
        {
            "analysis_run_id": 44,
            "recommendations": [
                {
                    "recommendation_type": "draft",
                    "calendar_action": {"action": "allocate_reserve"},
                    "evidence": [
                        {
                            "verified": True,
                            "metric_path": candidate["metric_path"],
                            "actual_metric_value": candidate,
                        }
                        for candidate in (first, second)
                    ],
                }
            ],
        }
    )
    component.business_context = _Data(
        _business_context([first, second], _inventory())
    )
    result = component.validate().data
    structured, message = _present(patched_flow, monkeypatch, result)
    assert [
        (group["time_from"], group["time_to"])
        for group in structured["presentation_groups"]
    ] == [("09:00", "10:00"), ("10:00", "11:00")]
    assert "ביקוש דחוף" in message
    assert "ניצול עתודה" in message


def test_all_required_analysis_domains_render_without_recommendations(
    patched_flow, monkeypatch
):
    domains = {
        "segment_duration_by_visit_type": {
            "status": "checked",
            "recommendation_found": False,
            "outcome": "no_change_recommended",
            "current_regular_segment_minutes": 15,
            "by_visit_type": [{
                "visit_type_name": "מעקב",
                "matched_visit_count": 12,
                "median_actual_duration_minutes": 13,
                "p75_actual_duration_minutes": 16,
            }],
        },
        "no_show_by_weekday_hour": {
            "status": "checked",
            "recommendation_found": False,
            "outcome": "no_change_recommended",
            "combined_no_show_signal_count": 12,
            "by_60_minute_window": [{
                "weekday": "שלישי",
                "time_from": "09:00",
                "time_to": "10:00",
                "combined_no_show_signal_count": 4,
                "combined_no_show_signal_rate_in_window": 0.08,
            }],
        },
        "no_show_by_modality": {
            "status": "checked",
            "recommendation_found": False,
            "outcome": "no_change_recommended",
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
        },
        "reserve_utilization": {
            "status": "checked",
            "recommendation_found": False,
            "outcome": "no_change_recommended",
            "reserve_found": True,
            "reserves": [{
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

    business_cls = _component_class(
        patched_flow,
        BUSINESS_ID,
        "RecommendationBusinessRuleValidator",
        monkeypatch,
    )
    business_component = business_cls()
    business_component.validated_recommendations = _Data(_llm_payload([]))
    context = _business_context([], _inventory())
    context["required_analysis_domains"] = {
        "metric_path": "required_analysis_domains",
        "value": domains,
        "actionable": False,
    }
    business_component.business_context = _Data(context)
    payload = business_component.validate().data
    _, message = _present(patched_flow, monkeypatch, payload)

    assert "### תחומי הניתוח הנדרשים" in message
    assert "#### התאמת גודל הסגמנט למשך הביקור בפועל לפי סוג ביקור" in message
    assert "#### אי־הגעה לפי יום ושעה" in message
    assert "#### השוואת אי־הגעה בין ביקורים פרונטליים לטלפוניים או בווידאו" in message
    assert "#### ניצול עתודות קיימות" in message
    assert "מעקב" in message
    assert "שלישי, 09:00–10:00" in message
    assert message.count("התחום נבדק ולא נמצאה המלצה לשינוי.") == 4


def test_required_no_show_lists_put_bullets_on_separate_lines(
    patched_flow, monkeypatch
):
    payload = {
        "recommendations": [],
        "required_analysis_domains": {
            "no_show_by_weekday_hour": {
                "status": "checked",
                "recommendation_found": False,
                "outcome": "no_change_recommended",
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
    }

    _, message = _present(patched_flow, monkeypatch, payload)

    assert "לפי יום:\n\n- שלישי: 12." in message
    assert "מוקדים בולטים:\n\n- שלישי, 09:00–10:00:" in message
    assert "בתקופה שנבדקה.\n\nלפי יום:" in message
    assert "מהתורים בחלון.\n\nהתחום נבדק" in message
    assert "לפי יום: -" not in message
    assert "מוקדים בולטים: -" not in message


def test_incomplete_modality_comparison_shows_coverage_gap(
    patched_flow, monkeypatch
):
    payload = {
        "recommendations": [],
        "required_analysis_domains": {
            "no_show_by_modality": {
                "status": "unavailable",
                "outcome": "comparison_incomplete",
                "recommendation_found": False,
                "modalities": {
                    "face_to_face": {
                        "logical_appointment_count": 20,
                        "no_show_count": 2,
                        "no_show_rate": 0.1,
                    },
                    "telephone_video": {
                        "logical_appointment_count": 20,
                        "no_show_count": 1,
                        "no_show_rate": 0.05,
                    },
                    "unknown": {
                        "logical_appointment_count": 60,
                        "no_show_count": 0,
                        "no_show_rate": 0,
                    },
                },
                "classification_coverage": {
                    "classified_appointment_count": 40,
                    "total_appointment_count": 100,
                    "rate": 0.4,
                    "minimum_required_rate": 0.8,
                },
                "comparison_unavailable_reasons": [
                    "classified_coverage_below_minimum"
                ],
                "no_show_classification_coverage": {
                    "total_no_show_signal_count": 58,
                    "excluded_pushed_no_show_count": 18,
                    "eligible_no_show_signal_count": 40,
                    "classified_no_show_signal_count": 40,
                    "unknown_no_show_signal_count": 0,
                    "rate": 1.0,
                    "minimum_required_rate": 0.8,
                },
            },
        },
    }

    _, message = _present(patched_flow, monkeypatch, payload)

    assert "40 מתוך 100 תורים סווגו" in message
    assert "נדרשים לפחות 80%" in message
    assert "60 תורים לא סווגו" in message
    assert "58 אותות אי־הגעה" in message
    assert "18 אותות מתורים שנדחפו הוצאו" in message
    assert "40 אותות נכללו בהשוואה" in message
    assert "לא ניתן היה להשלים את הבדיקה" in message
    assert "התחום נבדק ולא נמצאה המלצה לשינוי" not in message


def test_empty_general_insights_section_is_explicit(patched_flow, monkeypatch):
    _, message = _present(
        patched_flow,
        monkeypatch,
        {
            "recommendations": [],
            "analytics_insights": [],
            "candidate_insights": [],
        },
    )

    assert "### תובנות כלליות" in message
    assert "לא נמצאו תובנות כלליות נוספות להצגה." in message


def test_connected_text_prompts_and_saved_agent_copies_are_consistent(patched_flow):
    marker = "LIOR RECOMMENDATION V2 — MANDATORY"
    pairs = {
        "TextInput-enwvR": "Agent-nw0eZ",
        "TextInput-CsN8n": "Agent-1q7hm",
        "TextInput-t85tX": "Agent-N1co0",
    }
    for text_id, agent_id in pairs.items():
        text_template = _node(patched_flow, text_id)["data"]["node"]["template"]
        agent_template = _node(patched_flow, agent_id)["data"]["node"]["template"]
        text_prompt = text_template["input_value"]["value"]
        saved_prompt = agent_template["system_prompt"]["value"]
        assert marker in text_prompt
        assert marker in saved_prompt
        assert text_prompt.split(marker, 1)[1] == saved_prompt.split(marker, 1)[1]
