#!/usr/bin/env python3
"""Patch the two Lior Langflow JSON snapshots for existing calendar settings.

The script has no network access and contains no credentials. It reads fresh flow
snapshots from .workflow-edit and emits PATCH request bodies in the same directory.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".workflow-edit"
ANALYTICS_IN = WORK / "analytics.before.json"
RECOMMENDATION_IN = WORK / "recommendation.before.json"
ANALYTICS_OUT = WORK / "analytics.patch.json"
RECOMMENDATION_OUT = WORK / "recommendation.patch.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def node_by_id(flow: dict[str, Any], node_id: str) -> dict[str, Any]:
    matches = [node for node in flow["data"]["nodes"] if node.get("id") == node_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one node {node_id}, found {len(matches)}")
    return matches[0]


def code_for(node: dict[str, Any]) -> str:
    return node["data"]["node"]["template"]["code"]["value"]


def set_code(node: dict[str, Any], code: str) -> None:
    ast.parse(code)
    definition = node["data"]["node"]
    definition["template"]["code"]["value"] = code
    definition["edited"] = True
    definition.setdefault("metadata", {})["code_hash"] = hashlib.sha256(code.encode()).hexdigest()[:12]


def patch_decision_kpi(code: str) -> str:
    code = replace_once(
        code,
        """        # Only calendar_status פנוי / העדפה represents the appointment universe
        # of the analyzed physician. Other calendar statuses may be useful as
        # calendar context, but they must not enter appointment reconstruction,
        # capacity inventory, lead-time, preference, reserve or actualization KPIs.""",
        """        # Only calendar_status פנוי / העדפה represents the appointment KPI
        # universe. Existing preference and reserve definitions are calendar
        # settings, so they are analyzed separately from raw rows below without
        # contaminating appointment reconstruction, capacity, or lead-time KPIs.""",
        "decision KPI scope comment",
    )

    code = replace_once(
        code,
        """        matched_id_set = matched_ids
        matched_urgent_id_set = matched_urgent_ids

        for row in appointment_rows:""",
        """        matched_id_set = matched_ids
        matched_urgent_id_set = matched_urgent_ids
        historical_scope = historical.get("appointment_scope", {}) or {}
        historical_statuses = {
            self._normalize_calendar_status(value)
            for value in (historical_scope.get("included_calendar_statuses") or [])
        }
        reserve_actualization_available = any("עתודה" in value for value in historical_statuses)

        # Calendar settings must come from the raw rows. The appointment KPI
        # universe intentionally excludes reserve rows.
        for row in raw_appointment_rows:""",
        "decision KPI raw settings rows",
    )

    code = replace_once(
        code,
        """            actualization = g["matched_units"] / g["booked_units"] if g["booked_units"] else None
            urgent_share = g["matched_urgent_units"] / g["matched_units"] if g["matched_units"] else None""",
        """            actualization = (
                g["matched_units"] / g["booked_units"]
                if reserve_actualization_available and g["booked_units"]
                else None
            )
            urgent_share = (
                g["matched_urgent_units"] / g["matched_units"]
                if reserve_actualization_available and g["matched_units"]
                else None
            )""",
        "reserve actualization availability",
    )

    code = replace_once(
        code,
        """                "reserve_actualization_rate": round(actualization, 4) if actualization is not None else None,
                "urgent_share_of_matched_reserve": round(urgent_share, 4) if urgent_share is not None else None,
                "weeks_with_reserve": len(g["weeks"]),""",
        """                "reserve_actualization_rate": round(actualization, 4) if actualization is not None else None,
                "reserve_actualization_measurement_status": (
                    "available" if reserve_actualization_available else "unavailable"
                ),
                "reserve_actualization_unavailable_reason": (
                    None
                    if reserve_actualization_available
                    else "historical appointment-to-visit matching excludes reserve calendar rows"
                ),
                "urgent_share_of_matched_reserve": round(urgent_share, 4) if urgent_share is not None else None,
                "weeks_with_reserve": len(g["weeks"]),""",
        "reserve output measurement status",
    )

    contract = """        existing_calendar_settings = {
            "contract_version": "v1",
            "complete": True,
            "inventory_status": "available",
            "source": "raw_calendar_rows_before_appointment_kpi_scope_filter",
            "window_semantics": "recurring_weekday_half_open_hour",
            "analysis_period": {
                "from": period_from.isoformat() if period_from else None,
                "to": period_to.isoformat() if period_to else None,
            },
            "preferences": [
                {
                    "setting_id": (
                        f"preference::{row.get('weekday')}::{row.get('time_from')}::{row.get('time_to')}"
                    ),
                    "setting_type": "preference",
                    "weekday": row.get("weekday"),
                    "time_from": row.get("time_from"),
                    "time_to": row.get("time_to"),
                    "defined_segment_units": row.get("defined_preference_segment_units"),
                    "booked_segment_units": row.get("booked_preference_segment_units"),
                    "weeks_with_setting": row.get("weeks_with_preference"),
                    "preferred_visit_types": row.get("preferred_labels") or [],
                    "actual_booked_visit_type_mix": row.get("actual_booked_visit_type_mix") or [],
                    "utilization": {
                        "status": (
                            "available"
                            if row.get("preference_utilization_rate") is not None
                            else "unavailable"
                        ),
                        "value": row.get("preference_utilization_rate"),
                        "unavailable_reason": (
                            None
                            if row.get("preference_utilization_rate") is not None
                            else "no defined preference segment units"
                        ),
                    },
                    "compliance": {
                        "status": (
                            "available"
                            if row.get("preference_compliance_rate_when_comparable") is not None
                            else "unavailable"
                        ),
                        "value": row.get("preference_compliance_rate_when_comparable"),
                        "comparable_booked_segments": row.get("comparable_booked_segments"),
                        "unavailable_reason": (
                            None
                            if row.get("preference_compliance_rate_when_comparable") is not None
                            else "configured preference could not be compared with booked visit types"
                        ),
                    },
                }
                for row in preference_windows
            ],
            "reserves": [
                {
                    "setting_id": (
                        f"reserve::{row.get('weekday')}::{row.get('time_from')}::{row.get('time_to')}"
                    ),
                    "setting_type": "reserve",
                    "weekday": row.get("weekday"),
                    "time_from": row.get("time_from"),
                    "time_to": row.get("time_to"),
                    "defined_segment_units": row.get("defined_reserve_segment_units"),
                    "booked_segment_units": row.get("booked_reserve_segment_units"),
                    "matched_actual_segment_units": row.get("matched_actual_reserve_segment_units"),
                    "matched_urgent_segment_units": row.get("matched_urgent_reserve_segment_units"),
                    "weeks_with_setting": row.get("weeks_with_reserve"),
                    "utilization": {
                        "status": (
                            "available"
                            if row.get("reserve_utilization_rate") is not None
                            else "unavailable"
                        ),
                        "value": row.get("reserve_utilization_rate"),
                        "unavailable_reason": (
                            None
                            if row.get("reserve_utilization_rate") is not None
                            else "no defined reserve segment units"
                        ),
                    },
                    "actualization": {
                        "status": row.get("reserve_actualization_measurement_status") or "unavailable",
                        "value": row.get("reserve_actualization_rate"),
                        "urgent_share": row.get("urgent_share_of_matched_reserve"),
                        "unavailable_reason": row.get("reserve_actualization_unavailable_reason"),
                    },
                }
                for row in reserve_windows
            ],
        }

"""
    code = replace_once(
        code,
        "        warnings.extend([\n",
        contract + "        warnings.extend([\n",
        "existing calendar settings contract",
    )
    code = replace_once(
        code,
        '            "findings": findings,\n            "recommendation_candidates": candidates,',
        '            "findings": findings,\n'
        '            "existing_calendar_settings": existing_calendar_settings,\n'
        '            "recommendation_candidates": candidates,',
        "decision KPI result contract",
    )
    code = replace_once(
        code,
        '            "Only calendar_status פנוי/העדפה enters appointment KPIs. Generic סגירה and other calendar statuses are not treated as physician appointments.",',
        '            "Only calendar_status פנוי/העדפה enters appointment KPIs. Preference and reserve settings are separately inventoried from raw calendar rows.",',
        "decision KPI warning",
    )
    return code


ANALYTICS_SETTING_HELPERS = """
    @classmethod
    def _candidate_windows_for_existing_settings(cls, candidate):
        action = str(candidate.get("action") or candidate.get("allowed_action") or "")
        scope = str(candidate.get("scope") or candidate.get("decision_scope") or "")
        if action == "review_decrease_regular_segment" or scope == "entire_calendar":
            return [{"role": "calendar", "weekday": None, "time_from": None, "time_to": None}], True

        windows = []
        valid = True
        source_values = (
            candidate.get("weekday"),
            candidate.get("time_from"),
            candidate.get("time_to"),
        )
        if any(value is not None for value in source_values):
            if all(source_values):
                windows.append({
                    "role": "source",
                    "weekday": source_values[0],
                    "time_from": source_values[1],
                    "time_to": source_values[2],
                })
            else:
                valid = False

        target_values = (
            candidate.get("target_weekday"),
            candidate.get("target_time_from"),
            candidate.get("target_time_to"),
        )
        if any(value is not None for value in target_values):
            if all(target_values):
                windows.append({
                    "role": "target",
                    "weekday": target_values[0],
                    "time_from": target_values[1],
                    "time_to": target_values[2],
                })
            else:
                valid = False
        return windows, valid

    @classmethod
    def _existing_settings_context(cls, candidate, inventory):
        complete = isinstance(inventory, dict) and inventory.get("complete") is True
        windows, windows_valid = cls._candidate_windows_for_existing_settings(candidate)
        overlaps = []
        settings = []
        if isinstance(inventory, dict):
            for setting_type, key in (("preference", "preferences"), ("reserve", "reserves")):
                for setting in inventory.get(key) or []:
                    if isinstance(setting, dict):
                        settings.append((setting_type, setting))

        for window in windows:
            role = window.get("role")
            for setting_type, setting in settings:
                overlap_minutes = None
                if role == "calendar":
                    is_overlap = True
                elif window.get("weekday") != setting.get("weekday"):
                    is_overlap = False
                else:
                    start = cls._time_to_minutes(window.get("time_from"))
                    end = cls._time_to_minutes(window.get("time_to"))
                    setting_start = cls._time_to_minutes(setting.get("time_from"))
                    setting_end = cls._time_to_minutes(setting.get("time_to"))
                    is_overlap = (
                        None not in (start, end, setting_start, setting_end)
                        and max(start, setting_start) < min(end, setting_end)
                    )
                    if is_overlap:
                        overlap_minutes = int(min(end, setting_end) - max(start, setting_start))
                if not is_overlap:
                    continue
                overlaps.append({
                    "candidate_window_role": role,
                    "setting_id": setting.get("setting_id"),
                    "setting_type": setting_type,
                    "weekday": setting.get("weekday"),
                    "time_from": setting.get("time_from"),
                    "time_to": setting.get("time_to"),
                    "overlap_minutes": overlap_minutes,
                    "defined_segment_units": setting.get("defined_segment_units"),
                    "preferred_visit_types": setting.get("preferred_visit_types") or [],
                    "actual_booked_visit_type_mix": setting.get("actual_booked_visit_type_mix") or [],
                    "utilization": setting.get("utilization") or {},
                    "compliance": setting.get("compliance") or {},
                    "actualization": setting.get("actualization") or {},
                })

        if not complete:
            comparison_status = "inventory_unavailable"
        elif not windows_valid:
            comparison_status = "candidate_window_unavailable"
        elif not windows:
            comparison_status = "not_applicable"
        else:
            comparison_status = "complete"
        return {
            "contract_version": "v1",
            "considered": True,
            "settings_inventory_complete": complete,
            "comparison_status": comparison_status,
            "candidate_windows": windows,
            "overlaps": overlaps,
            "requires_resolution_before_implementation": bool(overlaps),
            "accounted_for": bool(complete and windows_valid),
        }

"""


def patch_analytics_builder(code: str) -> str:
    code = replace_once(
        code,
        """    @staticmethod
    def _consumes_committed_minutes(candidate):""",
        ANALYTICS_SETTING_HELPERS
        + """    @staticmethod
    def _consumes_committed_minutes(candidate):""",
        "Analytics settings helpers",
    )
    code = replace_once(
        code,
        """            for i, item in enumerate(recommendations[family]):
                finalized.append(self._finalize_candidate(family, item, i))
            recommendation_evidence[family] = finalized""",
        """            for i, item in enumerate(recommendations[family]):
                finalized_item = self._finalize_candidate(family, item, i)
                finalized_item["existing_settings_context"] = self._existing_settings_context(
                    finalized_item,
                    decision.get("existing_calendar_settings") or {},
                )
                finalized.append(finalized_item)
            recommendation_evidence[family] = finalized""",
        "enrich finalized recommendations",
    )
    code = replace_once(
        code,
        '            "candidate_conflicts_must_be_resolved_before_exact_schedule_changes": True,\n',
        '            "candidate_conflicts_must_be_resolved_before_exact_schedule_changes": True,\n'
        '            "existing_calendar_settings_must_be_checked_before_schedule_changes": True,\n'
        '            "overlapping_preference_or_reserve_must_be_explained": True,\n'
        '            "existing_reserve_must_be_adjusted_instead_of_duplicated": True,\n',
        "Analytics business guardrails",
    )
    code = replace_once(
        code,
        '            "analysis_context": analysis_context,\n            "performance_summary": performance_summary,',
        '            "analysis_context": analysis_context,\n'
        '            "existing_calendar_settings": decision.get("existing_calendar_settings") or {\n'
        '                "contract_version": "v1",\n'
        '                "complete": False,\n'
        '                "inventory_status": "unavailable",\n'
        '                "preferences": [],\n'
        '                "reserves": [],\n'
        '            },\n'
        '            "performance_summary": performance_summary,',
        "Analytics metrics settings inventory",
    )
    return code


def patch_analytics(flow: dict[str, Any]) -> None:
    decision = node_by_id(flow, "decision_kpi_analyzer-IBs8T")
    builder = node_by_id(flow, "analytics_feature_builder-f0hrQ")
    set_code(decision, patch_decision_kpi(code_for(decision)))
    set_code(builder, patch_analytics_builder(code_for(builder)))


def patch_context_splitter(code: str) -> str:
    code = replace_once(
        code,
        """        analysis_context = metrics.get("analysis_context") or {}
        baseline_value = self._baseline_from_analysis_context(analysis_context)

        business = {""",
        """        analysis_context = metrics.get("analysis_context") or {}
        baseline_value = self._baseline_from_analysis_context(analysis_context)
        existing_settings = metrics.get("existing_calendar_settings")
        if not isinstance(existing_settings, dict):
            existing_settings = {
                "contract_version": "v1",
                "complete": False,
                "inventory_status": "unavailable",
                "unavailable_reason": "analytics metrics predate the existing-calendar-settings contract",
                "preferences": [],
                "reserves": [],
            }

        business = {""",
        "Recommendation settings inventory normalization",
    )
    code = replace_once(
        code,
        '            "baseline_constraints": {"metric_path": "analysis_context.baseline_schedule", "value": baseline_value},\n'
        '            "business_guardrails": {"metric_path": "business_guardrails", "value": metrics.get("business_guardrails") or {}, "actionable": False},',
        '            "baseline_constraints": {"metric_path": "analysis_context.baseline_schedule", "value": baseline_value},\n'
        '            "existing_calendar_settings": {\n'
        '                "metric_path": "existing_calendar_settings",\n'
        '                "value": existing_settings,\n'
        '                "actionable": False,\n'
        '            },\n'
        '            "business_guardrails": {"metric_path": "business_guardrails", "value": metrics.get("business_guardrails") or {}, "actionable": False},',
        "Recommendation business settings inventory",
    )
    code = replace_once(
        code,
        '            "business_guardrails": guardrails,\n            "actionable_candidates": selected,',
        '            "business_guardrails": guardrails,\n'
        '            "existing_calendar_settings": (\n'
        '                (business.get("existing_calendar_settings") or {}).get("value") or {}\n'
        '            ),\n'
        '            "actionable_candidates": selected,',
        "Recommendation domain settings inventory",
    )
    return code


BUSINESS_SETTING_HELPERS = """
    @classmethod
    def _calendar_overlap_accounting(cls, action, inventory):
        complete = isinstance(inventory, dict) and inventory.get("complete") is True
        action_name = str(action.get("action") or "")
        scope = str(action.get("scope") or "")
        windows = []
        windows_valid = True

        if action_name == "review_decrease_regular_segment" or scope == "entire_calendar":
            windows.append({"role": "calendar", "weekday": None, "time_from": None, "time_to": None})
        else:
            source = (action.get("weekday"), action.get("time_from"), action.get("time_to"))
            if any(value is not None for value in source):
                if all(source):
                    windows.append({
                        "role": "source",
                        "weekday": source[0],
                        "time_from": source[1],
                        "time_to": source[2],
                    })
                else:
                    windows_valid = False
            target = (
                action.get("target_weekday"),
                action.get("target_time_from"),
                action.get("target_time_to"),
            )
            if any(value is not None for value in target):
                if all(target):
                    windows.append({
                        "role": "target",
                        "weekday": target[0],
                        "time_from": target[1],
                        "time_to": target[2],
                    })
                else:
                    windows_valid = False

        requirements = []
        for setting_type, key in (("preference", "preferences"), ("reserve", "reserves")):
            for setting in (inventory.get(key) or []) if isinstance(inventory, dict) else []:
                if not isinstance(setting, dict):
                    continue
                for window in windows:
                    role = window.get("role")
                    overlap_from = None
                    overlap_to = None
                    overlap_minutes = None
                    if role == "calendar":
                        overlaps = True
                    elif window.get("weekday") != setting.get("weekday"):
                        overlaps = False
                    else:
                        start = cls._minutes(window.get("time_from"))
                        end = cls._minutes(window.get("time_to"))
                        setting_start = cls._minutes(setting.get("time_from"))
                        setting_end = cls._minutes(setting.get("time_to"))
                        overlaps = (
                            None not in (start, end, setting_start, setting_end)
                            and max(start, setting_start) < min(end, setting_end)
                        )
                        if overlaps:
                            overlap_start = max(start, setting_start)
                            overlap_end = min(end, setting_end)
                            overlap_from = f"{overlap_start // 60:02d}:{overlap_start % 60:02d}"
                            overlap_to = f"{overlap_end // 60:02d}:{overlap_end % 60:02d}"
                            overlap_minutes = int(overlap_end - overlap_start)
                    if not overlaps:
                        continue
                    if setting_type == "preference":
                        strategy = "coordinate_existing_preference"
                    elif action_name == "allocate_reserve":
                        strategy = "adjust_existing_reserve_not_add"
                    else:
                        strategy = "coordinate_existing_reserve"
                    requirements.append({
                        "setting_id": setting.get("setting_id"),
                        "setting_type": setting_type,
                        "candidate_window_role": role,
                        "overlap_from": overlap_from,
                        "overlap_to": overlap_to,
                        "overlap_minutes": overlap_minutes,
                        "strategy": strategy,
                        "setting": {
                            "weekday": setting.get("weekday"),
                            "time_from": setting.get("time_from"),
                            "time_to": setting.get("time_to"),
                            "defined_segment_units": setting.get("defined_segment_units"),
                            "preferred_visit_types": setting.get("preferred_visit_types") or [],
                            "actual_booked_visit_type_mix": setting.get("actual_booked_visit_type_mix") or [],
                            "utilization": setting.get("utilization") or {},
                            "compliance": setting.get("compliance") or {},
                            "actualization": setting.get("actualization") or {},
                        },
                    })

        if not complete:
            status = "inventory_unavailable"
        elif not windows_valid:
            status = "candidate_window_unavailable"
        elif not windows:
            status = "not_applicable"
        else:
            status = "complete"
        accounted_for = bool(complete and windows_valid)
        return {
            "contract_version": "v1",
            "considered": True,
            "settings_inventory_complete": complete,
            "comparison_status": status,
            "source_and_target_windows_checked": True,
            "required": bool(requirements),
            "requirements": requirements,
            "accounted_for": accounted_for,
            "hebrew_explanation_required": bool(requirements),
        }

"""


def patch_business_validator(code: str) -> str:
    code = replace_once(
        code,
        """    @classmethod
    def _canonical_action(cls, c, window_map):""",
        BUSINESS_SETTING_HELPERS
        + """    @classmethod
    def _canonical_action(cls, c, window_map):""",
        "Recommendation business overlap helpers",
    )
    code = replace_once(
        code,
        """        window_map = self._window_map(baseline)
        candidate_values = self._candidate_values(business)

        accepted = []""",
        """        window_map = self._window_map(baseline)
        candidate_values = self._candidate_values(business)
        existing_settings = (business.get("existing_calendar_settings") or {}).get("value") or {}
        existing_settings_complete = (
            isinstance(existing_settings, dict) and existing_settings.get("complete") is True
        )

        accepted = []""",
        "Recommendation business inventory input",
    )
    code = replace_once(
        code,
        """        warnings = list(validated.get("warnings") or [])
        covered = set()

        blocked_standalone_actions = {""",
        """        warnings = list(validated.get("warnings") or [])
        covered = set()
        overlap_requirement_count = 0
        overlap_accounted_count = 0
        overlap_accounting_failures = 0
        if not existing_settings_complete:
            warnings.append(
                "המלצות לשינוי היומן נחסמו משום שמלאי ההעדפות והעתודות הקיימות אינו זמין או אינו מלא."
            )

        blocked_standalone_actions = {""",
        "Recommendation business accounting counters",
    )
    code = replace_once(
        code,
        """                if action.get("effective_window_clipped_to_baseline"):
                    corrections.append({""",
        """                accounting = self._calendar_overlap_accounting(action, existing_settings)
                overlap_requirement_count += len(accounting.get("requirements") or [])
                if not accounting.get("accounted_for"):
                    overlap_accounting_failures += 1
                    warnings.append(
                        f"Candidate {candidate.get('candidate_id')} was blocked because existing calendar settings could not be checked completely."
                    )
                    continue
                overlap_accounted_count += len(accounting.get("requirements") or [])
                if (
                    action_name == "allocate_reserve"
                    and any(
                        requirement.get("setting_type") == "reserve"
                        for requirement in (accounting.get("requirements") or [])
                    )
                ):
                    action["reserve_handling"] = "adjust_existing_reserve_not_add"
                    action["existing_reserve_checked"] = True

                if action.get("effective_window_clipped_to_baseline"):
                    corrections.append({""",
        "Recommendation business enforce accounting",
    )
    code = replace_once(
        code,
        """                normalized["decision_tier"] = "recommendation"
                normalized["decision_source"] = "deterministic_analytics_threshold"

                # Preserve only the verified evidence""",
        """                normalized["decision_tier"] = "recommendation"
                normalized["decision_source"] = "deterministic_analytics_threshold"
                normalized["existing_settings_context"] = accounting
                normalized["existing_settings_checked"] = accounting.get("accounted_for") is True

                # Preserve only the verified evidence""",
        "Recommendation attach accounting",
    )
    code = replace_once(
        code,
        '            "valid": True,\n            "analysis_run_id": validated.get("analysis_run_id") or business.get("analysis_run_id"),',
        '            "valid": bool(existing_settings_complete and overlap_accounting_failures == 0),\n'
        '            "analysis_run_id": validated.get("analysis_run_id") or business.get("analysis_run_id"),',
        "Recommendation validity accounting",
    )
    code = replace_once(
        code,
        '                "adjacent_windows_merge_only_for_exact_same_recommendation": True,\n',
        '                "adjacent_windows_merge_only_for_exact_same_recommendation": True,\n'
        '                "existing_calendar_settings_contract_complete": existing_settings_complete,\n'
        '                "calendar_overlap_requirement_count": overlap_requirement_count,\n'
        '                "calendar_overlap_accounted_count": overlap_accounted_count,\n'
        '                "calendar_overlap_accounting_complete": bool(\n'
        '                    existing_settings_complete and overlap_accounting_failures == 0\n'
        '                ),\n'
        '                "source_and_target_windows_checked": True,\n'
        '                "existing_reserve_adjusted_instead_of_duplicated": True,\n',
        "Recommendation validation accounting",
    )
    return code


PRESENTER_SETTING_HELPERS = """
    @staticmethod
    def _setting_distribution_labels(rows, keys):
        labels = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            for key in keys:
                value = row.get(key)
                if value:
                    labels.append(str(value))
                    break
        return labels[:3]

    @staticmethod
    def _percentage(metric):
        if not isinstance(metric, dict) or metric.get("status") != "available":
            return None
        try:
            return int(round(float(metric.get("value")) * 100))
        except Exception:
            return None

    @classmethod
    def _existing_settings_explanations(cls, rec):
        context = rec.get("existing_settings_context") or {}
        if context.get("accounted_for") is not True:
            return []
        sentences = []
        for requirement in context.get("requirements") or []:
            if not isinstance(requirement, dict):
                continue
            setting = requirement.get("setting") or {}
            role = requirement.get("candidate_window_role")
            role_he = {
                "source": "בחלון ההמלצה",
                "target": "בחלון היעד",
                "calendar": "ביומן",
            }.get(role, "בטווח ההמלצה")
            setting_type = requirement.get("setting_type")
            if setting_type == "preference":
                preferred = cls._setting_distribution_labels(
                    setting.get("preferred_visit_types") or [],
                    ("preferred_label", "visit_type", "name", "label"),
                )
                actual = cls._setting_distribution_labels(
                    setting.get("actual_booked_visit_type_mix") or [],
                    ("visit_type", "visit_type_name", "name", "label"),
                )
                parts = [f"{role_he} קיימת כבר העדפה ביומן"]
                if preferred:
                    parts.append(f"לסוג ביקור {', '.join(preferred)}")
                if actual:
                    parts.append(f"ובפועל נקבעו שם בעיקר ביקורים מסוג {', '.join(actual)}")
                compliance = cls._percentage(setting.get("compliance") or {})
                utilization = cls._percentage(setting.get("utilization") or {})
                if compliance is not None:
                    parts.append(f"שיעור ההתאמה להעדפה הוא {compliance} אחוזים")
                elif utilization is not None:
                    parts.append(f"שיעור ניצול חלון ההעדפה הוא {utilization} אחוזים")
                parts.append("ההעדפה נבדקה לפני גיבוש ההמלצה")
                sentences.append("; ".join(parts) + ".")
            elif setting_type == "reserve":
                parts = [f"{role_he} קיימת כבר עתודה ביומן"]
                utilization = cls._percentage(setting.get("utilization") or {})
                actualization = setting.get("actualization") or {}
                actualized = cls._percentage(actualization)
                if utilization is not None:
                    parts.append(f"שיעור ניצול העתודה הוא {utilization} אחוזים")
                if actualized is not None:
                    parts.append(f"שיעור המימוש בביקורים בפועל הוא {actualized} אחוזים")
                elif actualization.get("status") == "unavailable":
                    parts.append("נתון המימוש בביקורים בפועל אינו זמין ולכן לא פורש כאפס ניצול")
                if requirement.get("strategy") == "adjust_existing_reserve_not_add":
                    parts.append("ההמלצה מתייחסת להתאמת העתודה הקיימת ולא ליצירת עתודה נוספת")
                else:
                    parts.append("מיקום העתודה וניצולה נבדקו לפני גיבוש ההמלצה")
                sentences.append("; ".join(parts) + ".")
        return cls._unique(sentences)

"""


def patch_presenter(code: str) -> str:
    code = replace_once(
        code,
        """    @classmethod
    def _recommendation_parts(cls, rec):""",
        PRESENTER_SETTING_HELPERS
        + """    @classmethod
    def _recommendation_parts(cls, rec):""",
        "Presenter existing settings helpers",
    )
    code = replace_once(
        code,
        """        headlines = cls._unique([x[0] for x in parts])
        whys = cls._unique([x[1] for x in parts])
        whats = cls._unique([x[2] for x in parts])
        return {
            "headline": headlines[0],
            "why": " ".join(whys),
            "what": " ".join(whats),
        }""",
        """        headlines = cls._unique([x[0] for x in parts])
        whys = cls._unique([x[1] for x in parts])
        setting_whys = cls._unique([
            explanation
            for rec in recs
            if isinstance(rec, dict)
            for explanation in cls._existing_settings_explanations(rec)
        ])
        whats = cls._unique([x[2] for x in parts])
        return {
            "headline": headlines[0],
            "why": " ".join(whys + setting_whys),
            "what": " ".join(whats),
        }""",
        "Presenter grouped explanation",
    )
    code = replace_once(
        code,
        """            action.get("current_regular_segment_minutes"),
            action.get("suggested_regular_segment_minutes"),
        )""",
        """            action.get("current_regular_segment_minutes"),
            action.get("suggested_regular_segment_minutes"),
            tuple(sorted(
                (
                    requirement.get("setting_id"),
                    requirement.get("setting_type"),
                    requirement.get("candidate_window_role"),
                    requirement.get("strategy"),
                )
                for requirement in (
                    (rec.get("existing_settings_context") or {}).get("requirements") or []
                )
                if isinstance(requirement, dict)
            )),
        )""",
        "Presenter grouping signature",
    )
    code = replace_once(
        code,
        """                title, why, what = parts
                lines.append(f"**{title}**")
                lines.append(f"- **למה:** {why}")""",
        """                title, why, what = parts
                setting_explanations = self._existing_settings_explanations(rec)
                if setting_explanations:
                    why = " ".join([why, *setting_explanations])
                lines.append(f"**{title}**")
                lines.append(f"- **למה:** {why}")""",
        "Presenter global explanation",
    )
    return code


PROMPT_ADDITION = """

EXISTING CALENDAR SETTINGS — MANDATORY:
- Every candidate may contain existing_settings_context with overlapping preferences and reserves.
- Before phrasing a recommendation, inspect every overlap for both source and target windows.
- In `reason`, explicitly mention each relevant existing preference or reserve and how it affected the recommendation.
- For a preference, mention the configured visit type and the actual booked visit-type mix when available.
- For a reserve, mention its current utilization and actualization when available.
- Never propose a second reserve when an existing reserve overlaps; phrase the action as adjustment of the existing reserve.
- Do not add these setting references to `evidence`; they are verified calendar context, not decision-tier evidence.
- Deterministic validation will recompute this accounting, so never invent or alter the setting data.
"""


def patch_prompt(node: dict[str, Any]) -> None:
    field = node["data"]["node"]["template"]["input_value"]
    value = str(field.get("value") or "")
    marker = "EXISTING CALENDAR SETTINGS — MANDATORY:"
    if marker not in value:
        field["value"] = value.rstrip() + PROMPT_ADDITION


def patch_recommendation(flow: dict[str, Any]) -> None:
    splitter = node_by_id(flow, "recommendation_context_splitter-dU9xQ")
    business = node_by_id(flow, "recommendation_business_rule_validator-TvYcq")
    presenter = node_by_id(flow, "recommendation_presenter-TuUXM")
    set_code(splitter, patch_context_splitter(code_for(splitter)))
    set_code(business, patch_business_validator(code_for(business)))
    set_code(presenter, patch_presenter(code_for(presenter)))
    for node_id in ("TextInput-enwvR", "TextInput-CsN8n", "TextInput-t85tX"):
        patch_prompt(node_by_id(flow, node_id))


def patch_payload(flow: dict[str, Any]) -> dict[str, Any]:
    return {"data": flow["data"]}


def verify_flow(flow: dict[str, Any], expected_nodes: int, expected_edges: int) -> None:
    assert len(flow["data"]["nodes"]) == expected_nodes
    assert len(flow["data"]["edges"]) == expected_edges
    node_ids = {node["id"] for node in flow["data"]["nodes"]}
    for edge in flow["data"]["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
    for node in flow["data"]["nodes"]:
        template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
        code = template.get("code")
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            ast.parse(code["value"])


def main() -> None:
    analytics = json.loads(ANALYTICS_IN.read_text())
    recommendation = json.loads(RECOMMENDATION_IN.read_text())

    patch_analytics(analytics)
    patch_recommendation(recommendation)
    verify_flow(analytics, 32, 44)
    verify_flow(recommendation, 29, 26)

    ANALYTICS_OUT.write_text(json.dumps(patch_payload(analytics), ensure_ascii=False))
    RECOMMENDATION_OUT.write_text(json.dumps(patch_payload(recommendation), ensure_ascii=False))
    print(f"Wrote {ANALYTICS_OUT.name}: {ANALYTICS_OUT.stat().st_size} bytes")
    print(f"Wrote {RECOMMENDATION_OUT.name}: {RECOMMENDATION_OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
