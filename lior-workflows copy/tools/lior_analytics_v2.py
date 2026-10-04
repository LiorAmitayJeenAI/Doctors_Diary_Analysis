#!/usr/bin/env python3
"""Offline, composable Analytics v2 patch for the Lior Langflow flow."""

from __future__ import annotations

import ast
import hashlib
import textwrap
from typing import Any


HISTORICAL_NODE_ID = "historical_performance_analyzer-cDHUJ"
DECISION_NODE_ID = "decision_kpi_analyzer-IBs8T"
BUILDER_NODE_ID = "analytics_feature_builder-f0hrQ"
PRESSURE_NODE_ID = "urgent_reserve_pressure_analyzer-m0uiz"


def _node_by_id(flow: dict[str, Any], node_id: str) -> dict[str, Any]:
    matches = [node for node in flow["data"]["nodes"] if node.get("id") == node_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one node {node_id}, found {len(matches)}")
    return matches[0]


def _code(node: dict[str, Any]) -> str:
    return node["data"]["node"]["template"]["code"]["value"]


def _set_code(node: dict[str, Any], code: str) -> None:
    ast.parse(code)
    definition = node["data"]["node"]
    definition["template"]["code"]["value"] = code
    definition["edited"] = True
    definition.setdefault("metadata", {})["code_hash"] = hashlib.sha256(
        code.encode("utf-8")
    ).hexdigest()[:12]


def _inject_guarded_methods(
    code: str,
    class_name: str,
    marker: str,
    wrapper: str,
    entry_method: str,
) -> str:
    active_marker = f"{marker}_ACTIVE"
    if active_marker in code:
        tree = ast.parse(code)
        definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if len(definitions) != 1:
            raise ValueError(
                f"{active_marker}: expected one top-level {class_name}, "
                f"found {len(definitions)}"
            )
        return code

    # Migrate output from the superseded append-wrapper implementation.
    legacy_marker = f"# {marker}"
    if legacy_marker in code:
        code = code.split(legacy_marker, 1)[0].rstrip() + "\n"

    tree = ast.parse(code)
    definitions = [
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(definitions) != 1:
        raise ValueError(
            f"{marker}: expected one top-level {class_name}, found {len(definitions)}"
        )
    class_node = definitions[0]
    entry_methods = [
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == entry_method
    ]
    if len(entry_methods) != 1:
        raise ValueError(
            f"{marker}: expected one {class_name}.{entry_method}, "
            f"found {len(entry_methods)}"
        )

    wrapper_tree = ast.parse(wrapper)
    wrapper_classes = [
        node
        for node in wrapper_tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(wrapper_classes) != 1:
        raise ValueError(
            f"{marker}: invalid method template for {class_name}"
        )
    injected_nodes = [
        node
        for node in wrapper_classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if not any(node.name == entry_method for node in injected_nodes):
        raise ValueError(f"{marker}: template does not replace {entry_method}")

    lines = code.splitlines()
    original_method = entry_methods[0]
    line_index = original_method.lineno - 1
    old_token = f"def {entry_method}"
    new_token = f"def _lior_v2_original_{entry_method}"
    if lines[line_index].count(old_token) != 1:
        raise ValueError(f"{marker}: unstable {entry_method} definition anchor")
    lines[line_index] = lines[line_index].replace(old_token, new_token, 1)

    rendered_methods = []
    for node in injected_nodes:
        source = ast.unparse(node)
        source = source.replace(
            f"super().{entry_method}()",
            f"self._lior_v2_original_{entry_method}()",
        )
        rendered_methods.append(textwrap.indent(source, "    "))
    injection = (
        f"\n    {active_marker} = True\n\n"
        + "\n\n".join(rendered_methods)
        + "\n"
    )
    lines.insert(class_node.end_lineno, injection.rstrip("\n"))
    patched = "\n".join(lines).rstrip() + "\n"
    ast.parse(patched)
    patched_tree = ast.parse(patched)
    patched_definitions = [
        node
        for node in patched_tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(patched_definitions) != 1:
        raise ValueError(
            f"{marker}: direct injection did not preserve one {class_name}"
        )
    return patched


def _replace_class_methods(
    code: str,
    class_name: str,
    template: str,
    method_names: tuple[str, ...],
    marker: str,
    replacements: dict[str, str],
) -> str:
    if marker in code:
        return code
    tree = ast.parse(code)
    definition = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ),
        None,
    )
    if definition is None:
        raise ValueError(f"{marker}: {class_name} was not found")
    template_tree = ast.parse(template)
    template_class = next(
        node
        for node in template_tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    desired = {
        node.name: node
        for node in template_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    }
    current = {
        node.name: node
        for node in definition.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    }
    if set(current) != set(method_names) or set(desired) != set(method_names):
        raise ValueError(f"{marker}: method set does not match")
    lines = code.splitlines()
    for name in sorted(method_names, key=lambda item: current[item].lineno, reverse=True):
        node = current[name]
        start = min(
            [node.lineno, *(decorator.lineno for decorator in node.decorator_list)]
        )
        rendered = textwrap.indent(ast.unparse(desired[name]), "    ")
        for old, new in replacements.items():
            rendered = rendered.replace(old, new)
        lines[start - 1 : node.end_lineno] = rendered.splitlines()
    patched = "\n".join(lines).rstrip() + "\n"
    patched_tree = ast.parse(patched)
    patched_class = next(
        node
        for node in patched_tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    lines = patched.splitlines()
    lines.insert(patched_class.end_lineno, f"    {marker} = True")
    patched = "\n".join(lines).rstrip() + "\n"
    ast.parse(patched)
    return patched


def _insert_class_methods(
    code: str,
    class_name: str,
    template: str,
    method_names: tuple[str, ...],
    marker: str,
) -> str:
    if marker in code:
        return code
    tree = ast.parse(code)
    definition = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ),
        None,
    )
    if definition is None:
        raise ValueError(f"{marker}: {class_name} was not found")
    template_class = next(
        node
        for node in ast.parse(template).body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    desired = {
        node.name: node
        for node in template_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    }
    if set(desired) != set(method_names):
        raise ValueError(f"{marker}: template method set does not match")
    existing = {
        node.name
        for node in definition.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [name for name in method_names if name not in existing]
    rendered = [
        textwrap.indent(ast.unparse(desired[name]), "    ")
        for name in missing
    ]
    lines = code.splitlines()
    addition = ["", f"    {marker} = True"]
    if rendered:
        addition.extend(["", *("\n\n".join(rendered).splitlines())])
    lines[definition.end_lineno : definition.end_lineno] = addition
    patched = "\n".join(lines).rstrip() + "\n"
    ast.parse(patched)
    return patched


def _wrap_class_method(
    code: str,
    class_name: str,
    method_name: str,
    base_method_name: str,
    template: str,
    marker: str,
) -> str:
    """Rename one active method and append a deterministic wrapper plus helpers."""

    if marker in code:
        return code
    tree = ast.parse(code)
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(definitions) != 1:
        raise ValueError(f"{marker}: expected one {class_name}")
    definition = definitions[0]
    methods = [
        node
        for node in definition.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method_name
    ]
    existing_names = {
        node.name
        for node in definition.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if len(methods) != 1 or base_method_name in existing_names:
        raise ValueError(f"{marker}: unstable {class_name}.{method_name}")

    lines = code.splitlines()
    method = methods[0]
    source_line = lines[method.lineno - 1]
    token = f"def {method_name}"
    if source_line[method.col_offset :].count(token) != 1:
        raise ValueError(f"{marker}: unstable method definition")
    lines[method.lineno - 1] = (
        source_line[: method.col_offset]
        + source_line[method.col_offset :].replace(
            token, f"def {base_method_name}", 1
        )
    )

    template_class = next(
        (
            node
            for node in ast.parse(template).body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ),
        None,
    )
    if template_class is None:
        raise ValueError(f"{marker}: invalid template")
    rendered = [
        textwrap.indent(ast.unparse(node), "    ")
        for node in template_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if method_name not in {
        node.name
        for node in template_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }:
        raise ValueError(f"{marker}: wrapper method missing")
    lines[definition.end_lineno : definition.end_lineno] = [
        "",
        f"    {marker} = True",
        "",
        *("\n\n".join(rendered).splitlines()),
    ]
    patched = "\n".join(lines).rstrip() + "\n"
    ast.parse(patched)
    return patched


HISTORICAL_METHOD_TEMPLATE = r'''
# LIOR_ANALYTICS_V2_HISTORICAL
_LiorAnalyticsV2HistoricalBase = HistoricalPerformanceAnalyzer


class HistoricalPerformanceAnalyzer(_LiorAnalyticsV2HistoricalBase):
    """Adds reserve reconciliation without changing primary analytics."""

    @staticmethod
    def _lior_v2_datetime(value):
        if isinstance(value, datetime):
            return value
        if value is None:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _lior_v2_identifier(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            value = str(value).strip()
            return value or None

    def _lior_v2_reserve_reconciliation(self, primary_payload):
        baseline = self._payload(self.baseline) or {}
        run_id = int(baseline["analysis_run_id"])
        period = baseline.get("analysis_period", {}) or {}
        period_from = self._parse_date(period.get("from")) if period.get("from") else None
        period_to = self._parse_date(period.get("to")) if period.get("to") else None
        excluded_dates = self._excluded_dates(baseline)
        excluded_intervals = self._excluded_intervals(baseline)
        regular_segment = (baseline.get("segment", {}) or {}).get(
            "regular_segment_minutes"
        ) or 15

        primary_visit_ids = {
            self._lior_v2_identifier(row.get("visit_id"))
            for row in (primary_payload.get("match_records") or [])
            if isinstance(row, dict) and row.get("visit_id") is not None
        }

        with get_cached_engine(self._db_url()).connect() as conn:
            appointment_rows = conn.execute(
                text(
                    """
                    SELECT appointment_id, member_id, member_identity_code,
                           appointment_date, appointment_time, appointment_type_code,
                           visit_duration, calendar_status
                    FROM doctor_schedule_analysis_demo.appointments
                    WHERE analysis_run_id = :run_id
                    ORDER BY appointment_date, appointment_time, appointment_id
                    """
                ),
                {"run_id": run_id},
            ).mappings().all()
            visit_rows = conn.execute(
                text(
                    """
                    SELECT visit_id, customer_id, encounter_start_datetime
                    FROM doctor_schedule_analysis_demo.visits
                    WHERE analysis_run_id = :run_id
                      AND encounter_start_datetime IS NOT NULL
                    ORDER BY encounter_start_datetime, visit_id
                    """
                ),
                {"run_id": run_id},
            ).mappings().all()

        reserve_by_key = defaultdict(list)
        for row in appointment_rows:
            status = self._normalize_calendar_status(row.get("calendar_status"))
            if "עתודה" not in str(status or ""):
                continue
            member = self._norm_id(row.get("member_id")) or self._norm_id(
                row.get("member_identity_code")
            )
            scheduled = self._combine(
                row.get("appointment_date"), row.get("appointment_time")
            )
            if not member or not scheduled:
                continue
            if (
                (period_from and scheduled.date() < period_from)
                or (period_to and scheduled.date() > period_to)
                or scheduled.date().isoformat() in excluded_dates
                or self._inside_exclusion(scheduled, excluded_intervals)
            ):
                continue
            appointment_id = self._lior_v2_identifier(row.get("appointment_id"))
            if appointment_id is None:
                continue
            reserve_by_key[(member, scheduled.date().isoformat())].append(
                {
                    "appointment_id": appointment_id,
                    "scheduled_start": scheduled,
                    "is_urgent": bool(self._urgent(row.get("appointment_type_code"))),
                    "segment_units": round(
                        float(self._segment_units(row, regular_segment)), 3
                    ),
                }
            )

        visits_by_key = defaultdict(list)
        for row in visit_rows:
            visit_id = self._lior_v2_identifier(row.get("visit_id"))
            if visit_id is None or visit_id in primary_visit_ids:
                continue
            member = self._norm_id(row.get("customer_id"))
            actual = self._lior_v2_datetime(row.get("encounter_start_datetime"))
            if not member or not actual:
                continue
            if (
                (period_from and actual.date() < period_from)
                or (period_to and actual.date() > period_to)
                or actual.date().isoformat() in excluded_dates
                or self._inside_exclusion(actual, excluded_intervals)
            ):
                continue
            visits_by_key[(member, actual.date().isoformat())].append(
                {"visit_id": visit_id, "actual_start": actual}
            )

        matches = []
        for key in sorted(set(reserve_by_key) & set(visits_by_key)):
            reserve_rows = reserve_by_key[key]
            visits = visits_by_key[key]
            candidates = []
            for appointment_index, appointment in enumerate(reserve_rows):
                for visit_index, visit in enumerate(visits):
                    distance = abs(
                        (
                            visit["actual_start"] - appointment["scheduled_start"]
                        ).total_seconds()
                        / 60.0
                    )
                    if distance > 90:
                        continue
                    candidates.append(
                        (
                            distance,
                            str(appointment["appointment_id"]),
                            str(visit["visit_id"]),
                            appointment_index,
                            visit_index,
                        )
                    )
            used_appointments = set()
            used_visits = set()
            for distance, _, _, appointment_index, visit_index in sorted(candidates):
                if (
                    appointment_index in used_appointments
                    or visit_index in used_visits
                ):
                    continue
                used_appointments.add(appointment_index)
                used_visits.add(visit_index)
                appointment = reserve_rows[appointment_index]
                visit = visits[visit_index]
                matches.append(
                    {
                        "member_token": hashlib.sha256(
                            key[0].encode("utf-8")
                        ).hexdigest()[:16],
                        "appointment_ids": [appointment["appointment_id"]],
                        "visit_id": visit["visit_id"],
                        "scheduled_start": appointment["scheduled_start"].isoformat(),
                        "actual_start": visit["actual_start"].isoformat(),
                        "time_distance_minutes": round(distance, 3),
                        "match_confidence": (
                            "high" if distance <= 30 else "medium"
                        ),
                        "segment_units": appointment["segment_units"],
                        "is_urgent": appointment["is_urgent"],
                        "reconciliation_method": (
                            "one_to_one_same_member_same_date_nearest_time_"
                            "excluding_primary_matched_visits"
                        ),
                    }
                )

        matches.sort(
            key=lambda row: (
                row["scheduled_start"],
                str(row["appointment_ids"][0]),
                str(row["visit_id"]),
            )
        )
        matched_ids = sorted(
            {
                appointment_id
                for match in matches
                for appointment_id in match["appointment_ids"]
            },
            key=str,
        )
        matched_urgent_ids = sorted(
            {
                appointment_id
                for match in matches
                if match["is_urgent"]
                for appointment_id in match["appointment_ids"]
            },
            key=str,
        )
        return {
            "contract_version": "v1",
            "measurement_status": "available",
            "matching_scope": "reserve_calendar_rows_only",
            "same_member_same_date_required": True,
            "primary_matched_visits_excluded": True,
            "matched_reserve_appointment_ids": matched_ids,
            "matched_urgent_reserve_appointment_ids": matched_urgent_ids,
            "matched_visit_ids": sorted(
                {match["visit_id"] for match in matches}, key=str
            ),
            "summary": {
                "booked_reserve_events": sum(
                    len(rows) for rows in reserve_by_key.values()
                ),
                "matched_reserve_events": len(matches),
                "unmatched_booked_reserve_events": (
                    sum(len(rows) for rows in reserve_by_key.values())
                    - len(matches)
                ),
                "maximum_match_distance_minutes": 90,
            },
            "matches": matches,
            "interpretation": (
                "Reserve reconciliation is separate from primary appointment "
                "matching and does not affect match_records, no-show, delay, or capacity."
            ),
        }

    def analyze(self) -> Data:
        result = super().analyze()
        payload = self._payload(result)
        try:
            payload["reserve_to_visit_reconciliation"] = (
                self._lior_v2_reserve_reconciliation(payload)
            )
        except Exception:
            payload["reserve_to_visit_reconciliation"] = {
                "contract_version": "v1",
                "measurement_status": "unavailable",
                "matching_scope": "reserve_calendar_rows_only",
                "same_member_same_date_required": True,
                "primary_matched_visits_excluded": True,
                "matched_reserve_appointment_ids": [],
                "matched_urgent_reserve_appointment_ids": [],
                "matched_visit_ids": [],
                "matches": [],
                "unavailable_reason": "reserve_to_visit_reconciliation_failed",
            }
            payload.setdefault("warnings", []).append(
                "Reserve-to-visit reconciliation is unavailable; primary analytics remain valid."
            )
        return result
'''


DECISION_METHOD_TEMPLATE = r'''
# LIOR_ANALYTICS_V2_DECISION
_LiorAnalyticsV2DecisionBase = DecisionKPIAnalyzer


class DecisionKPIAnalyzer(_LiorAnalyticsV2DecisionBase):
    """Normalizes setting labels and consumes reserve-only reconciliation."""

    @staticmethod
    def _lior_v2_normalize_occurrence_dates(values):
        normalized = set()
        for value in values or []:
            try:
                if hasattr(value, "isoformat"):
                    text = value.isoformat()
                else:
                    text = str(value or "").strip()
                normalized.add(date.fromisoformat(text[:10]).isoformat())
            except (TypeError, ValueError):
                continue
        return sorted(normalized)

    @classmethod
    def _lior_v2_normalize_occurrence_contract(cls, value):
        if isinstance(value, list):
            for item in value:
                cls._lior_v2_normalize_occurrence_contract(item)
            return
        if not isinstance(value, dict):
            return
        if "occurrence_dates" in value:
            dates = cls._lior_v2_normalize_occurrence_dates(
                value.get("occurrence_dates")
            )
            value["occurrence_dates"] = dates
            value["first_occurrence_date"] = dates[0] if dates else None
            value["last_occurrence_date"] = dates[-1] if dates else None
            value["active_date_count"] = len(dates)
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                cls._lior_v2_normalize_occurrence_contract(nested)

    @staticmethod
    def _lior_v2_datetime(value):
        if isinstance(value, datetime):
            return value
        if value is None:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    def _lior_v2_visit_type_names(self):
        with get_cached_engine(self._db_url()).connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT visit_type_code, visit_type_name, calendar_short_name,
                           source_description, source_short_description
                    FROM doctor_schedule_analysis_demo.visit_types
                    """
                )
            ).mappings().all()
        names = {}
        for row in rows:
            code = str(row.get("visit_type_code") or "").strip()
            if not code:
                continue
            for field in (
                "visit_type_name",
                "calendar_short_name",
                "source_description",
                "source_short_description",
            ):
                value = str(row.get(field) or "").strip()
                if value:
                    names[code] = value
                    break
        return names

    def _lior_v2_resolve_preferences(self, inventory, visit_type_names):
        preferences = inventory.get("preferences")
        if not isinstance(preferences, list):
            preferences = []
        for setting in preferences:
            if not isinstance(setting, dict):
                continue
            for preferred in setting.get("preferred_visit_types") or []:
                if not isinstance(preferred, dict):
                    continue
                raw_code = str(
                    preferred.get("preferred_code")
                    or preferred.get("preferred_label")
                    or preferred.get("preferred_name")
                    or ""
                ).strip()
                if not raw_code:
                    continue
                resolved_name = (
                    visit_type_names.get(raw_code)
                    or str(preferred.get("preferred_name") or "").strip()
                    or raw_code
                )
                preferred["preferred_visit_type_code"] = raw_code
                preferred["preferred_visit_type_name"] = resolved_name
                preferred["preferred_code"] = raw_code
                preferred["preferred_name"] = resolved_name
                preferred["preferred_label"] = resolved_name

    def _lior_v2_measure_reserves(self, payload, inventory, historical):
        reconciliation = (
            historical.get("reserve_to_visit_reconciliation")
            or historical.get("reserve_reconciliation")
            or {}
        )
        if not isinstance(reconciliation, dict):
            reconciliation = {}
        measurement_status = str(
            reconciliation.get("measurement_status") or "unavailable"
        )
        matched_ids = {
            str(value)
            for value in (
                reconciliation.get("matched_reserve_appointment_ids") or []
            )
        }
        matched_urgent_ids = {
            str(value)
            for value in (
                reconciliation.get("matched_urgent_reserve_appointment_ids") or []
            )
        }
        by_window = defaultdict(
            lambda: {"matched_actual": 0.0, "matched_urgent": 0.0}
        )
        matches = reconciliation.get("matches")
        if not isinstance(matches, list):
            matches = []
        for match in matches:
            if not isinstance(match, dict):
                continue
            match_ids = {
                str(value) for value in (match.get("appointment_ids") or [])
            }
            eligible_ids = match_ids & matched_ids
            if not eligible_ids:
                continue
            scheduled = self._lior_v2_datetime(match.get("scheduled_start"))
            if not scheduled:
                continue
            weekday = self.WEEKDAY_NAMES[scheduled.weekday()]
            time_from = f"{scheduled.hour:02d}:00"
            time_to = f"{scheduled.hour + 1:02d}:00"
            units = float(match.get("segment_units") or 1.0)
            values = by_window[(weekday, time_from, time_to)]
            values["matched_actual"] += units
            if eligible_ids & matched_urgent_ids:
                values["matched_urgent"] += units

        reserves = inventory.get("reserves")
        if not isinstance(reserves, list):
            reserves = []
        for setting in reserves:
            if not isinstance(setting, dict):
                continue
            key = (
                setting.get("weekday"),
                setting.get("time_from"),
                setting.get("time_to"),
            )
            values = by_window.get(key, {})
            matched = (
                round(float(values.get("matched_actual") or 0.0), 3)
                if measurement_status == "available"
                else None
            )
            matched_urgent = (
                round(float(values.get("matched_urgent") or 0.0), 3)
                if measurement_status == "available"
                else None
            )
            booked = float(setting.get("booked_segment_units") or 0.0)
            actualization = (
                matched / booked
                if measurement_status == "available" and booked and matched is not None
                else None
            )
            urgent_share = (
                matched_urgent / matched
                if (
                    measurement_status == "available"
                    and matched
                    and matched_urgent is not None
                )
                else None
            )
            setting["matched_actual_segment_units"] = matched
            setting["matched_urgent_segment_units"] = matched_urgent
            setting["measurement_status"] = measurement_status
            setting["actualization"] = {
                "status": (
                    "available"
                    if measurement_status == "available" and booked
                    else "unavailable"
                ),
                "value": (
                    round(actualization, 4)
                    if actualization is not None
                    else None
                ),
                "urgent_share": (
                    round(urgent_share, 4) if urgent_share is not None else None
                ),
                "unavailable_reason": (
                    None
                    if measurement_status == "available" and booked
                    else (
                        reconciliation.get("unavailable_reason")
                        or "no booked reserve segment units"
                    )
                ),
            }

        findings = payload.get("findings")
        if not isinstance(findings, dict):
            findings = {}
            payload["findings"] = findings
        reserve_findings = findings.get("reserves")
        if not isinstance(reserve_findings, dict):
            reserve_findings = {}
            findings["reserves"] = reserve_findings
        inventory_by_window = {
            (
                setting.get("weekday"),
                setting.get("time_from"),
                setting.get("time_to"),
            ): setting
            for setting in reserves
            if isinstance(setting, dict)
        }
        for row in reserve_findings.get("by_60_minute_window") or []:
            if not isinstance(row, dict):
                continue
            setting = inventory_by_window.get(
                (row.get("weekday"), row.get("time_from"), row.get("time_to"))
            )
            if not setting:
                continue
            actualization = setting.get("actualization")
            if not isinstance(actualization, dict):
                actualization = {}
            row["matched_actual_reserve_segment_units"] = setting.get(
                "matched_actual_segment_units"
            )
            row["matched_urgent_reserve_segment_units"] = setting.get(
                "matched_urgent_segment_units"
            )
            row["reserve_actualization_measurement_status"] = actualization.get(
                "status"
            )
            row["reserve_actualization_rate"] = actualization.get("value")
            row["urgent_share_of_matched_reserve"] = actualization.get(
                "urgent_share"
            )
            row["reserve_actualization_unavailable_reason"] = actualization.get(
                "unavailable_reason"
            )
        reserve_findings[
            "reserve_to_visit_reconciliation_measurement_status"
        ] = measurement_status
        reserve_findings["matched_reserve_appointment_ids"] = list(
            reconciliation.get("matched_reserve_appointment_ids") or []
        )
        reserve_findings["matched_urgent_reserve_appointment_ids"] = list(
            reconciliation.get("matched_urgent_reserve_appointment_ids") or []
        )

    def analyze(self) -> Data:
        result = super().analyze()
        payload = self._payload(result)
        if not isinstance(payload, dict):
            return result
        self._lior_v2_normalize_occurrence_contract(payload)
        inventory = payload.get("existing_calendar_settings")
        if not isinstance(inventory, dict):
            return result
        warnings = payload.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
            payload["warnings"] = warnings
        try:
            visit_type_names = self._lior_v2_visit_type_names()
        except Exception:
            visit_type_names = {}
        try:
            self._lior_v2_resolve_preferences(inventory, visit_type_names)
        except (AttributeError, TypeError, ValueError):
            warnings.append("Preference labels could not be enriched; raw settings were retained.")
        historical = self._payload(self.historical)
        if not isinstance(historical, dict):
            historical = {}
        try:
            self._lior_v2_measure_reserves(payload, inventory, historical)
        except (AttributeError, TypeError, ValueError):
            warnings.append("Reserve measurement enrichment was unavailable; base analytics remain valid.")
        return result
'''


REQUIRED_ANALYSIS_DECISION_TEMPLATE = r'''
class DecisionKPIAnalyzer(Component):
    _LIOR_REQUIRED_DIRECT_DURATION_COLUMNS = (
        "actual_visit_duration_minutes",
        "encounter_duration_minutes",
        "visit_duration_minutes",
        "duration_minutes",
        "actual_visit_duration",
        "encounter_duration",
    )
    _LIOR_REQUIRED_END_COLUMNS = (
        "encounter_end_datetime",
        "actual_visit_end_datetime",
        "visit_end_datetime",
        "encounter_end_date_time",
        "visit_end_date_time",
        "encounter_end_time",
        "visit_end_time",
    )

    @staticmethod
    def _lior_required_identifier(value):
        if value in (None, ""):
            return None
        return str(value).strip()

    @staticmethod
    def _lior_required_number(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number

    @staticmethod
    def _lior_required_percentile(values, numerator, denominator):
        ordered = sorted(float(value) for value in values)
        if not ordered:
            return None
        index = max(
            0,
            min(
                len(ordered) - 1,
                (len(ordered) * int(numerator) + int(denominator) - 1)
                // int(denominator)
                - 1,
            ),
        )
        return ordered[index]

    @classmethod
    def _lior_required_duration_minutes(cls, start_value, duration_value, mode):
        if duration_value is None:
            return None
        if mode == "direct_duration":
            if hasattr(duration_value, "total_seconds"):
                minutes = duration_value.total_seconds() / 60.0
            else:
                minutes = cls._lior_required_number(duration_value)
                if minutes is None:
                    text_value = str(duration_value or "").strip()
                    try:
                        pieces = [float(piece) for piece in text_value.split(":")]
                    except (TypeError, ValueError):
                        return None
                    if len(pieces) == 3:
                        minutes = pieces[0] * 60.0 + pieces[1] + pieces[2] / 60.0
                    elif len(pieces) == 2:
                        minutes = pieces[0] * 60.0 + pieces[1]
                    else:
                        return None
        else:
            start = cls._lior_v2_datetime(start_value)
            if start is None:
                return None
            end = duration_value if isinstance(duration_value, datetime) else None
            if end is None and isinstance(duration_value, time):
                end = datetime.combine(start.date(), duration_value)
            if end is None:
                raw = str(duration_value or "").strip()
                try:
                    end = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    try:
                        end = datetime.combine(start.date(), time.fromisoformat(raw))
                    except (TypeError, ValueError):
                        return None
            try:
                minutes = (end - start).total_seconds() / 60.0
            except (TypeError, ValueError):
                return None
            if minutes < 0:
                minutes += 24.0 * 60.0
        if minutes is None or minutes <= 0 or minutes > 8.0 * 60.0:
            return None
        return round(float(minutes), 4)

    def _lior_required_visit_duration_rows(self, run_id):
        with get_cached_engine(self._db_url()).connect() as conn:
            probe = conn.execute(
                text(
                    """
                    SELECT *
                    FROM doctor_schedule_analysis_demo.visits
                    WHERE 1 = 0
                    """
                )
            )
            keys_method = getattr(probe, "keys", None)
            columns = {
                str(value)
                for value in (keys_method() if callable(keys_method) else [])
            }
            direct_duration_columns = (
                "actual_visit_duration_minutes",
                "encounter_duration_minutes",
                "visit_duration_minutes",
                "duration_minutes",
                "actual_visit_duration",
                "encounter_duration",
                "actual_duration_minutes",
                "visit_actual_duration_minutes",
            )
            end_columns = (
                "encounter_end_datetime",
                "actual_visit_end_datetime",
                "visit_end_datetime",
                "encounter_end_date_time",
                "visit_end_date_time",
                "encounter_end_time",
                "visit_end_time",
                "actual_end_datetime",
                "actual_end_date_time",
                "actual_end_time",
            )
            selected = next(
                (
                    value
                    for value in direct_duration_columns
                    if value in columns
                ),
                None,
            )
            mode = "direct_duration"
            if selected is None:
                selected = next(
                    (
                        value
                        for value in end_columns
                        if value in columns
                    ),
                    None,
                )
                mode = "end_timestamp"
            if selected is None:
                return [], None, None
            # selected is constrained to a fixed whitelist above.
            rows = conn.execute(
                text(
                    f"""
                    SELECT visit_id, encounter_start_datetime,
                           {selected} AS actual_duration_value
                    FROM doctor_schedule_analysis_demo.visits
                    WHERE analysis_run_id = :run_id
                      AND encounter_start_datetime IS NOT NULL
                    ORDER BY encounter_start_datetime, visit_id
                    """
                ),
                {"run_id": run_id},
            ).mappings().all()
        return list(rows), selected, mode

    def _lior_required_actual_duration_analysis(
        self, payload, historical, visit_type_names
    ):
        baseline = self._payload(getattr(self, "baseline", None)) or {}
        current_segment = self._lior_required_number(
            ((baseline.get("segment") or {}).get("regular_segment_minutes"))
        )
        if current_segment is None:
            current_segment = self._lior_required_number(
                (((payload.get("findings") or {}).get("segment_fit") or {}).get(
                    "current_regular_segment_minutes"
                ))
            )
        base = {
            "measurement_status": "unavailable",
            "measurement_source": "documented_actual_duration",
            "uses_start_to_next_start_proxy": False,
            "current_regular_segment_minutes": (
                round(current_segment, 3) if current_segment is not None else None
            ),
            "duration_source_field": None,
            "by_visit_type": [],
            "unavailable_reason": None,
        }
        run_id = payload.get("analysis_run_id") or baseline.get("analysis_run_id")
        if run_id in (None, ""):
            base["unavailable_reason"] = "analysis_run_id_missing"
            return base
        try:
            rows, source_field, mode = self._lior_required_visit_duration_rows(
                int(run_id)
            )
        except Exception:
            base["unavailable_reason"] = "actual_visit_duration_source_unavailable"
            return base
        if not source_field:
            base["unavailable_reason"] = "actual_visit_duration_field_not_found"
            return base

        matches = {}
        for match in historical.get("match_records") or []:
            if not isinstance(match, dict):
                continue
            visit_id = self._lior_required_identifier(match.get("visit_id"))
            if visit_id:
                matches[visit_id] = match
        grouped = defaultdict(list)
        for row in rows:
            if not isinstance(row, dict):
                continue
            visit_id = self._lior_required_identifier(row.get("visit_id"))
            match = matches.get(visit_id)
            if not match:
                continue
            visit_type_code = str(match.get("visit_type_code") or "").strip() or None
            visit_type_name = (
                visit_type_names.get(visit_type_code)
                if visit_type_code is not None
                else None
            )
            duration = self._lior_required_duration_minutes(
                row.get("encounter_start_datetime"),
                row.get("actual_duration_value"),
                mode,
            )
            if duration is None:
                continue
            grouped[(visit_type_code, visit_type_name)].append(duration)

        output = []
        for (visit_type_code, visit_type_name), values in grouped.items():
            ordered = sorted(values)
            count = len(ordered)
            if count % 2:
                median_value = ordered[count // 2]
            else:
                median_value = (
                    ordered[count // 2 - 1] + ordered[count // 2]
                ) / 2.0
            p75_value = self._lior_required_percentile(ordered, 3, 4)
            output.append(
                {
                    "visit_type_code": visit_type_code,
                    "visit_type_name": visit_type_name,
                    "matched_visit_count": count,
                    "average_actual_duration_minutes": round(
                        sum(ordered) / count, 3
                    ),
                    "median_actual_duration_minutes": round(median_value, 3),
                    "p75_actual_duration_minutes": (
                        round(p75_value, 3) if p75_value is not None else None
                    ),
                    "median_difference_from_segment_minutes": (
                        round(median_value - current_segment, 3)
                        if current_segment is not None
                        else None
                    ),
                }
            )
        output.sort(
            key=lambda row: (
                -int(row.get("matched_visit_count") or 0),
                str(row.get("visit_type_name") or row.get("visit_type_code") or ""),
            )
        )
        base["duration_source_field"] = source_field
        base["by_visit_type"] = output
        if output:
            base["measurement_status"] = "available"
        else:
            base["unavailable_reason"] = (
                "no_matched_visits_with_valid_actual_duration"
            )
        return base

    @staticmethod
    def _lior_required_modality(*values):
        normalized = " ".join(str(value or "") for value in values)
        normalized = (
            normalized.lower()
            .replace(" ", "")
            .replace("-", "")
            .replace("_", "")
            .replace("/", "")
        )
        explicit_mapping = {
            "ביקוררגיל": "face_to_face",
            "תוררגיל": "face_to_face",
            "ביקורפרונטלי": "face_to_face",
            "תורפרונטלי": "face_to_face",
            "ביקורפניםאלפנים": "face_to_face",
            "000gh": "telephone_video",
        }
        for value in values:
            exact = (
                str(value or "")
                .strip()
                .lower()
                .replace(" ", "")
                .replace("-", "")
                .replace("_", "")
                .replace("/", "")
            )
            if exact in explicit_mapping:
                return explicit_mapping[exact]
        if (
            "טלפ" in normalized
            or "וידאו" in normalized
            or "וידיאו" in normalized
            or "telephone" in normalized
            or "video" in normalized
            or "virtual" in normalized
        ):
            return "telephone_video"
        if (
            "פרונט" in normalized
            or "פנים" in normalized
            or "facetoface" in normalized
            or "inperson" in normalized
        ):
            return "face_to_face"
        return "unknown"

    def _lior_required_no_show_modality(
        self, payload, historical, visit_type_names
    ):
        findings = payload.get("findings") or {}
        visit_type_rows = (
            (findings.get("visit_type_allocation") or {}).get(
                "by_visit_type_capacity"
            )
            or []
        )
        historical_no_show = historical.get("no_show")
        result = {
            "measurement_status": "available",
            "classification_basis": "scheduled_visit_type",
            "classification_mapping_version": "business_approved_v2",
            "population": "regular_non_pushed_planned_appointments",
            "minimum_classified_coverage_rate": 0.8,
            "modalities": {
                "face_to_face": {
                    "logical_appointment_count": 0,
                    "confirmed_no_show_count": 0,
                    "probable_no_show_count": 0,
                    "no_show_count": 0,
                    "no_show_rate": None,
                },
                "telephone_video": {
                    "logical_appointment_count": 0,
                    "confirmed_no_show_count": 0,
                    "probable_no_show_count": 0,
                    "no_show_count": 0,
                    "no_show_rate": None,
                },
                "unknown": {
                    "logical_appointment_count": 0,
                    "confirmed_no_show_count": 0,
                    "probable_no_show_count": 0,
                    "no_show_count": 0,
                    "no_show_rate": None,
                },
            },
            "comparison": {
                "measurement_status": "available",
                "rate_difference_percentage_points": None,
                "higher_no_show_modality": None,
            },
            "classification_coverage": {
                "classified_appointment_count": 0,
                "unknown_appointment_count": 0,
                "total_appointment_count": 0,
                "rate": None,
                "minimum_required_rate": 0.8,
            },
            "no_show_classification_coverage": {
                "total_no_show_signal_count": 0,
                "excluded_pushed_no_show_count": 0,
                "eligible_no_show_signal_count": 0,
                "classified_no_show_signal_count": 0,
                "unknown_no_show_signal_count": 0,
                "rate": 1.0,
                "minimum_required_rate": 0.8,
            },
            "comparison_unavailable_reasons": [],
            "unavailable_reason": None,
        }
        if not isinstance(historical_no_show, dict):
            result["measurement_status"] = "unavailable"
            result["comparison"]["measurement_status"] = "unavailable"
            result["unavailable_reason"] = "no_show_classification_unavailable"
            return result

        for row in visit_type_rows:
            if not isinstance(row, dict):
                continue
            modality = self._lior_required_modality(
                row.get("visit_type_name"), row.get("visit_type_code")
            )
            result["modalities"][modality]["logical_appointment_count"] += int(
                row.get("logical_appointment_count") or 0
            )

        baseline = self._payload(getattr(self, "baseline", None)) or {}
        schedule = self._schedule_windows(baseline)
        period = payload.get("analysis_period") or {}
        period_from = self._parse_date(period.get("from")) if period.get("from") else None
        period_to = self._parse_date(period.get("to")) if period.get("to") else None
        total_no_show_count = 0
        excluded_pushed_count = 0
        eligible_no_show_count = 0
        classified_no_show_count = 0
        unknown_no_show_count = 0
        for record in historical_no_show.get("classification_records") or []:
            if not isinstance(record, dict):
                continue
            classification = str(record.get("classification") or "")
            if classification not in {"confirmed_no_show", "probable_no_show"}:
                continue
            scheduled = self._dt(record.get("scheduled_start"))
            if scheduled is None:
                continue
            if period_from and scheduled.date() < period_from:
                continue
            if period_to and scheduled.date() > period_to:
                continue
            if schedule and not self._inside_schedule(scheduled, schedule):
                continue
            total_no_show_count += 1
            if str(record.get("calendar_source_kind") or "") == "pushed":
                excluded_pushed_count += 1
                continue
            eligible_no_show_count += 1
            code = str(record.get("visit_type_code") or "").strip() or None
            modality = self._lior_required_modality(
                visit_type_names.get(code), code, record.get("appointment_type_code")
            )
            if modality == "unknown":
                unknown_no_show_count += 1
            else:
                classified_no_show_count += 1
            bucket = result["modalities"][modality]
            bucket[f"{classification.replace('_no_show', '')}_no_show_count"] += 1
            bucket["no_show_count"] += 1

        for bucket in result["modalities"].values():
            denominator = int(bucket.get("logical_appointment_count") or 0)
            bucket["no_show_rate"] = (
                round(float(bucket.get("no_show_count") or 0) / denominator, 4)
                if denominator
                else None
            )
        face_count = int(
            result["modalities"]["face_to_face"]["logical_appointment_count"]
            or 0
        )
        virtual_count = int(
            result["modalities"]["telephone_video"]["logical_appointment_count"]
            or 0
        )
        unknown_count = int(
            result["modalities"]["unknown"]["logical_appointment_count"] or 0
        )
        classified_count = face_count + virtual_count
        total_count = classified_count + unknown_count
        coverage_rate = (
            round(float(classified_count) / float(total_count), 4)
            if total_count
            else None
        )
        result["classification_coverage"] = {
            "classified_appointment_count": classified_count,
            "unknown_appointment_count": unknown_count,
            "total_appointment_count": total_count,
            "rate": coverage_rate,
            "minimum_required_rate": 0.8,
        }
        no_show_coverage_rate = (
            round(
                float(classified_no_show_count) / float(eligible_no_show_count),
                4,
            )
            if eligible_no_show_count
            else 1.0
        )
        result["no_show_classification_coverage"] = {
            "total_no_show_signal_count": total_no_show_count,
            "excluded_pushed_no_show_count": excluded_pushed_count,
            "eligible_no_show_signal_count": eligible_no_show_count,
            "classified_no_show_signal_count": classified_no_show_count,
            "unknown_no_show_signal_count": unknown_no_show_count,
            "rate": no_show_coverage_rate,
            "minimum_required_rate": 0.8,
        }
        unavailable_reasons = []
        if face_count <= 0:
            unavailable_reasons.append("face_to_face_group_empty")
        if virtual_count <= 0:
            unavailable_reasons.append("telephone_video_group_empty")
        if coverage_rate is None:
            unavailable_reasons.append("classification_population_empty")
        elif coverage_rate < 0.8:
            unavailable_reasons.append("classified_coverage_below_minimum")
        if no_show_coverage_rate < 0.8:
            unavailable_reasons.append(
                "no_show_classified_coverage_below_minimum"
            )
        if unavailable_reasons:
            result["measurement_status"] = "unavailable"
            result["comparison"]["measurement_status"] = "unavailable"
            result["comparison_unavailable_reasons"] = unavailable_reasons
            result["unavailable_reason"] = "modality_comparison_incomplete"
            return result

        face_rate = result["modalities"]["face_to_face"]["no_show_rate"]
        virtual_rate = result["modalities"]["telephone_video"]["no_show_rate"]
        if face_rate is not None and virtual_rate is not None:
            result["comparison"]["rate_difference_percentage_points"] = round(
                abs(float(face_rate) - float(virtual_rate)) * 100.0, 2
            )
            if face_rate > virtual_rate:
                result["comparison"]["higher_no_show_modality"] = "face_to_face"
            elif virtual_rate > face_rate:
                result["comparison"]["higher_no_show_modality"] = "telephone_video"
            else:
                result["comparison"]["higher_no_show_modality"] = "equal"
        return result

    def analyze(self) -> Data:
        result = self._lior_required_analysis_base_analyze()
        payload = self._payload(result)
        if not isinstance(payload, dict):
            return result
        historical = self._payload(getattr(self, "historical", None)) or {}
        try:
            visit_type_names = self._lior_v2_visit_type_names()
        except Exception:
            visit_type_names = {}
        payload["required_analysis_inputs"] = {
            "segment_duration_by_visit_type": (
                self._lior_required_actual_duration_analysis(
                    payload, historical, visit_type_names
                )
            ),
            "no_show_by_modality": self._lior_required_no_show_modality(
                payload, historical, visit_type_names
            ),
        }
        return result
'''


def _patch_required_analysis_decision(code: str) -> str:
    code = _wrap_class_method(
        code,
        "DecisionKPIAnalyzer",
        "analyze",
        "_lior_required_analysis_base_analyze",
        REQUIRED_ANALYSIS_DECISION_TEMPLATE,
        "LIOR_REQUIRED_ANALYSIS_DECISION_V1_ACTIVE",
    )
    code = _replace_class_methods(
        code,
        "DecisionKPIAnalyzer",
        REQUIRED_ANALYSIS_DECISION_TEMPLATE,
        (
            "_lior_required_visit_duration_rows",
            "_lior_required_modality",
            "_lior_required_no_show_modality",
        ),
        "LIOR_REQUIRED_ANALYSIS_SOURCE_AND_MODALITY_V2_ACTIVE",
        {},
    )
    return _replace_class_methods(
        code,
        "DecisionKPIAnalyzer",
        REQUIRED_ANALYSIS_DECISION_TEMPLATE,
        ("_lior_required_no_show_modality",),
        "LIOR_REQUIRED_ANALYSIS_MODALITY_NUMERATOR_V3_ACTIVE",
        {},
    )


def _patch_decision_occurrence_sources(code: str) -> str:
    """Serialize the date sets already calculated by the Decision analyzer."""

    marker = "LIOR_ANALYTICS_OCCURRENCE_DATES_V2"
    if marker in code:
        return code
    # Small unit-test doubles do not contain the production aggregations. The
    # wrapper still normalizes any occurrence_dates they return.
    if "urgent_by_date_window = defaultdict(float)" not in code:
        return code

    replacements = (
        (
            '            row = {\n'
            '                "weekday": wd_name,\n'
            '                "time_from": tf,\n'
            '                "time_to": tt,\n'
            '                "eligible_occurrence_count": eligible_count,\n'
            '                "scheduled_segment_units_per_occurrence":',
            '            row = {\n'
            '                # LIOR_ANALYTICS_OCCURRENCE_DATES_V2\n'
            '                "weekday": wd_name,\n'
            '                "time_from": tf,\n'
            '                "time_to": tt,\n'
            '                "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                "eligible_occurrence_count": eligible_count,\n'
            '                "scheduled_segment_units_per_occurrence":',
        ),
        (
            '                        "action": "review_capacity_mix_within_existing_hours",\n'
            '                        "weekday": wd_name,',
            '                        "action": "review_capacity_mix_within_existing_hours",\n'
            '                        "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                        "weekday": wd_name,',
        ),
        (
            '                            "action": "prioritize_capacity_reallocation_for_access",\n'
            '                            "weekday": wd_name,',
            '                            "action": "prioritize_capacity_reallocation_for_access",\n'
            '                            "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                            "weekday": wd_name,',
        ),
        (
            '                        "action": "review_repurposing_within_existing_hours",\n'
            '                        "weekday": wd_name,',
            '                        "action": "review_repurposing_within_existing_hours",\n'
            '                        "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                        "weekday": wd_name,',
        ),
        (
            '            row = {\n'
            '                "visit_type_code": vt,\n'
            '                "visit_type_name": visit_type_names.get(vt),',
            '            row = {\n'
            '                "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                "visit_type_code": vt,\n'
            '                "visit_type_name": visit_type_names.get(vt),',
        ),
        (
            '                    "action": "allocate_visit_type_window",\n'
            '                    "visit_type_code": vt,',
            '                    "action": "allocate_visit_type_window",\n'
            '                    "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                    "visit_type_code": vt,',
        ),
        (
            '                row = {\n'
            '                    "weekday": wd_name,\n'
            '                    "time_from": tf,\n'
            '                    "time_to": tt,\n'
            '                    "confirmed_visit_without_prior_appointment_count":',
            '                row = {\n'
            '                    "weekday": wd_name,\n'
            '                    "time_from": tf,\n'
            '                    "time_to": tt,\n'
            '                    "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                    "confirmed_visit_without_prior_appointment_count":',
        ),
        (
            '            row = {\n'
            '                "modality": modality,\n'
            '                "weekday": wd_name,',
            '            row = {\n'
            '                "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                "modality": modality,\n'
            '                "weekday": wd_name,',
        ),
        (
            '            workload_rows.append({\n'
            '                "weekday": wd_name,\n'
            '                "time_from": tf,\n'
            '                "time_to": tt,',
            '            workload_rows.append({\n'
            '                "weekday": wd_name,\n'
            '                "time_from": tf,\n'
            '                "time_to": tt,\n'
            '                "occurrence_dates": sorted(g.get("dates") or set()),',
        ),
        (
            '                    "time_to": row["time_to"],\n'
            '                    "actual_encounter_count": row["actual_encounter_count"],',
            '                    "time_to": row["time_to"],\n'
            '                    "occurrence_dates": list(row.get("occurrence_dates") or []),\n'
            '                    "actual_encounter_count": row["actual_encounter_count"],',
        ),
        (
            '                "eligible_occurrence_count": eligible_count,\n'
            '                "after_scheduled_end_encounter_count":',
            '                "eligible_occurrence_count": eligible_count,\n'
            '                "occurrence_dates": sorted(after.get("dates") or set()),\n'
            '                "after_scheduled_end_encounter_count":',
        ),
        (
            '                "combined_no_show_signal_count": combined_count,\n'
            '                "weeks_with_no_show_signal": weeks,',
            '                "combined_no_show_signal_count": combined_count,\n'
            '                "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                "weeks_with_no_show_signal": weeks,',
        ),
        (
            '                "delay_minutes": summary,\n'
            '                "weeks_with_delay_evidence": weeks,',
            '                "delay_minutes": summary,\n'
            '                "occurrence_dates": sorted(data.get("dates") or set()),\n'
            '                "weeks_with_delay_evidence": weeks,',
        ),
        (
            '                "defined_preference_segment_units": round(g["defined_units"], 3),',
            '                "occurrence_dates": sorted(g.get("dates") or set()),\n'
            '                "defined_preference_segment_units": round(g["defined_units"], 3),',
        ),
        (
            '                "defined_reserve_segment_units": round(g["defined_units"], 3),',
            '                "occurrence_dates": sorted(g.get("dates") or set()),\n'
            '                "defined_reserve_segment_units": round(g["defined_units"], 3),',
        ),
        (
            '                "occurrences_with_confirmed_urgent_actual": nonzero_dates,\n'
            '                "weeks_with_confirmed_urgent_actual": weeks,',
            '                "occurrences_with_confirmed_urgent_actual": nonzero_dates,\n'
            '                "occurrence_dates": sorted(\n'
            '                    d.isoformat() for d, value in zip(dates, values) if value > 0\n'
            '                ),\n'
            '                "weeks_with_confirmed_urgent_actual": weeks,',
        ),
    )
    patched = code
    for old, new in replacements:
        count = patched.count(old)
        if count != 1:
            raise ValueError(
                "Occurrence dates: expected one Decision source anchor, "
                f"found {count}: {old.splitlines()[0]!r}"
            )
        patched = patched.replace(old, new, 1)
    ast.parse(patched)
    return patched


def _patch_pressure_occurrence_sources(code: str) -> str:
    marker = "LIOR_ANALYTICS_PUSHED_OCCURRENCE_DATES_V2"
    if marker in code:
        return code
    if "def _format_patterns(" not in code or "def _candidates(" not in code:
        return code
    replacements = (
        (
            '                "active_day_count": len(g["dates"]),\n'
            '                "weeks_with_activity": weeks,',
            '                # LIOR_ANALYTICS_PUSHED_OCCURRENCE_DATES_V2\n'
            '                "occurrence_dates": sorted(g["dates"]),\n'
            '                "first_occurrence_date": min(g["dates"]) if g["dates"] else None,\n'
            '                "last_occurrence_date": max(g["dates"]) if g["dates"] else None,\n'
            '                "active_date_count": len(g["dates"]),\n'
            '                "active_day_count": len(g["dates"]),\n'
            '                "weeks_with_activity": weeks,',
        ),
        (
            '                    "active_day_count": p["active_day_count"],\n'
            '                    "weeks_with_activity": p["weeks_with_activity"],',
            '                    "occurrence_dates": list(p.get("occurrence_dates") or []),\n'
            '                    "first_occurrence_date": p.get("first_occurrence_date"),\n'
            '                    "last_occurrence_date": p.get("last_occurrence_date"),\n'
            '                    "active_date_count": p.get("active_date_count"),\n'
            '                    "active_day_count": p["active_day_count"],\n'
            '                    "weeks_with_activity": p["weeks_with_activity"],',
        ),
    )
    patched = code
    for old, new in replacements:
        count = patched.count(old)
        if count != 1:
            raise ValueError(
                "Pushed occurrence dates: expected one pressure source anchor, "
                f"found {count}"
            )
        patched = patched.replace(old, new, 1)
    ast.parse(patched)
    return patched


def _patch_builder_pushed_occurrence_sources(code: str) -> str:
    marker = "LIOR_ANALYTICS_PUSHED_OCCURRENCE_PROPAGATION_V2"
    if marker in code:
        return code
    if "def _classify_pushed(" not in code:
        return code
    old = (
        '                "pushed_segment_row_count": count,\n'
        '                "support_occurrence_count": support,'
    )
    new = (
        '                # LIOR_ANALYTICS_PUSHED_OCCURRENCE_PROPAGATION_V2\n'
        '                "pushed_segment_row_count": count,\n'
        '                "occurrence_dates": list(row.get("occurrence_dates") or []),\n'
        '                "first_occurrence_date": row.get("first_occurrence_date"),\n'
        '                "last_occurrence_date": row.get("last_occurrence_date"),\n'
        '                "active_date_count": row.get("active_date_count"),\n'
        '                "support_occurrence_count": support,'
    )
    if code.count(old) != 1:
        raise ValueError(
            "Pushed occurrence propagation: expected one builder source anchor, "
            f"found {code.count(old)}"
        )
    patched = code.replace(old, new, 1)
    ast.parse(patched)
    return patched


def _upgrade_decision_occurrence_contract(code: str) -> str:
    code = _insert_class_methods(
        code,
        "DecisionKPIAnalyzer",
        DECISION_METHOD_TEMPLATE,
        (
            "_lior_v2_normalize_occurrence_dates",
            "_lior_v2_normalize_occurrence_contract",
        ),
        "LIOR_ANALYTICS_OCCURRENCE_NORMALIZERS_ACTIVE",
    )
    return _replace_class_methods(
        code,
        "DecisionKPIAnalyzer",
        DECISION_METHOD_TEMPLATE,
        ("analyze",),
        "LIOR_ANALYTICS_OCCURRENCE_OUTPUT_V2_ACTIVE",
        {"super().analyze()": "self._lior_v2_original_analyze()"},
    )


BUILDER_METHOD_TEMPLATE = r'''
# LIOR_ANALYTICS_V2_BUILDER
_LiorAnalyticsV2BuilderBase = AnalyticsFeatureBuilder


class AnalyticsFeatureBuilder(_LiorAnalyticsV2BuilderBase):
    """Applies the baseline clipping contract to late-created insights."""

    def build(self) -> Data:
        return super().build()
'''


FACTUAL_BASIS_METHOD_TEMPLATE = r'''
class AnalyticsFeatureBuilder(Component):
    @staticmethod
    def _lior_grounding_number(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return int(number) if number.is_integer() else round(number, 4)

    @classmethod
    def _lior_grounding_first_number(cls, source, keys):
        if not isinstance(source, dict):
            return None, None
        for key in keys:
            number = cls._lior_grounding_number(source.get(key))
            if number is not None:
                return number, key
        return None, None

    @classmethod
    def _lior_grounding_required_support(cls, thresholds, tier):
        if not isinstance(thresholds, dict):
            return None, None
        preferred = (
            ("required_support_for_recommendation", "source_required_support")
            if tier == "recommendation"
            else ("required_support_for_insight",)
        )
        fallback = (
            "required_support_for_recommendation",
            "required_support_for_insight",
            "source_required_support",
            "target_required_support",
        )
        for keys in (preferred, fallback):
            stack = [thresholds]
            while stack:
                current = stack.pop()
                if not isinstance(current, dict):
                    continue
                for key in keys:
                    number = cls._lior_grounding_number(current.get(key))
                    if number is not None:
                        return number, key
                stack.extend(
                    value for value in current.values() if isinstance(value, dict)
                )
        return None, None

    @staticmethod
    def _lior_grounding_period(analysis_context):
        if not isinstance(analysis_context, dict):
            analysis_context = {}
        for key in (
            "decision_period",
            "analysis_period",
            "source_analysis_period",
        ):
            period = analysis_context.get(key)
            if isinstance(period, dict) and (
                period.get("from") or period.get("to")
            ):
                return {
                    "from": period.get("from"),
                    "to": period.get("to"),
                    "scope": key,
                }
        return {"from": None, "to": None, "scope": "unavailable"}

    @staticmethod
    def _lior_grounding_occurrence_dates(values):
        normalized = set()
        for value in values or []:
            try:
                if hasattr(value, "isoformat"):
                    text = value.isoformat()
                else:
                    text = str(value or "").strip()
                normalized.add(date.fromisoformat(text[:10]).isoformat())
            except (TypeError, ValueError):
                continue
        return sorted(normalized)

    @classmethod
    def _lior_grounding_occurrence_source(cls, item, decision):
        item = item if isinstance(item, dict) else {}
        own_dates = cls._lior_grounding_occurrence_dates(
            item.get("occurrence_dates")
        )
        if own_dates:
            return own_dates
        # Pushed-pressure evidence is calculated by a separate analyzer. Never
        # borrow dates from a Decision row merely because its window matches.
        if item.get("source_kind") == "pushed":
            return []
        sources = []

        def collect(value):
            if isinstance(value, list):
                for nested in value:
                    collect(nested)
                return
            if not isinstance(value, dict):
                return
            dates = cls._lior_grounding_occurrence_dates(
                value.get("occurrence_dates")
            )
            if dates:
                sources.append((value, dates))
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    collect(nested)

        collect(decision)
        scored = []
        identity_keys = (
            "weekday",
            "time_from",
            "time_to",
            "candidate_type",
            "action",
            "modality",
            "visit_type_code",
            "visit_type_name",
        )
        required_window_keys = ("weekday", "time_from", "time_to")
        for source, dates in sources:
            rejected = False
            score = 0
            for key in identity_keys:
                expected = item.get(key)
                actual = source.get(key)
                if expected in (None, "") or actual in (None, ""):
                    continue
                if str(expected) != str(actual):
                    if key in required_window_keys:
                        rejected = True
                        break
                    continue
                score += 10 if key in ("candidate_type", "action") else 2
            if not rejected and score:
                scored.append((score, len(dates), dates))
        if not scored:
            return []
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return scored[0][2]

    @classmethod
    def _lior_grounding_observed_span(
        cls, item, decision, period, expected_support=None
    ):
        dates = cls._lior_grounding_occurrence_source(item, decision)
        first = dates[0] if dates else None
        last = dates[-1] if dates else None
        reported_count = cls._lior_grounding_number(
            item.get("active_date_count")
            if item.get("active_date_count") is not None
            else item.get("active_day_count")
        )
        expected_count = (
            reported_count
            if reported_count is not None
            else cls._lior_grounding_number(expected_support)
        )
        dates_complete = bool(
            dates
            and (
                expected_count is None
                or len(dates) >= int(expected_count)
            )
        )
        analysis_from = None
        analysis_to = None
        try:
            analysis_from = date.fromisoformat(str(period.get("from") or "")[:10])
            analysis_to = date.fromisoformat(str(period.get("to") or "")[:10])
        except (TypeError, ValueError):
            pass

        coverage = None
        leading_gap = None
        trailing_gap = None
        occupied_quarters = 0
        distributed = False
        if (
            dates_complete
            and analysis_from
            and analysis_to
            and analysis_to > analysis_from
        ):
            parsed = [date.fromisoformat(value) for value in dates]
            if all(analysis_from <= value <= analysis_to for value in parsed):
                analysis_days = (analysis_to - analysis_from).days
                coverage = round(
                    (parsed[-1] - parsed[0]).days / analysis_days, 4
                )
                leading_gap = round(
                    (parsed[0] - analysis_from).days / analysis_days, 4
                )
                trailing_gap = round(
                    (analysis_to - parsed[-1]).days / analysis_days, 4
                )
                quarters = {
                    min(
                        3,
                        int(
                            ((value - analysis_from).days * 4)
                            / (analysis_days + 1)
                        ),
                    )
                    for value in parsed
                }
                occupied_quarters = len(quarters)
                distributed = bool(
                    len(parsed) >= 3
                    and coverage >= 0.70
                    and leading_gap <= 0.15
                    and trailing_gap <= 0.15
                    and occupied_quarters >= 3
                )
        return {
            "first_occurrence_date": first,
            "last_occurrence_date": last,
            "occurrence_dates": dates,
            "active_date_count": len(dates),
            "reported_active_date_count": reported_count,
            "occurrence_dates_complete": dates_complete,
            "analysis_window_coverage_rate": coverage,
            "leading_gap_rate": leading_gap,
            "trailing_gap_rate": trailing_gap,
            "occupied_analysis_quarters": occupied_quarters,
            "distributed_across_analysis_window": distributed,
            "distribution_rule": (
                "at_least_3_dates_covering_70_percent_of_window_with_"
                "first_and_last_in_outer_15_percent_and_3_quarters_occupied"
            ),
        }

    @classmethod
    def _lior_grounding_factual_basis(cls, item, metrics, decision=None):
        item = item if isinstance(item, dict) else {}
        metrics = metrics if isinstance(metrics, dict) else {}
        analysis_context = metrics.get("analysis_context") or {}
        performance = metrics.get("performance_summary") or {}
        patient_visits = performance.get("weekly_patient_visits") or {}
        period = cls._lior_grounding_period(analysis_context)

        numerator, numerator_field = cls._lior_grounding_first_number(
            item,
            (
                "support_occurrence_count",
                "active_date_count",
                "weeks_with_activity",
                "weeks_with_confirmed_urgent_actual",
                "measurable_occurrence_count",
                "pair_count",
            ),
        )
        denominator, denominator_field = cls._lior_grounding_first_number(
            item,
            (
                "eligible_occurrence_count",
                "scheduled_eligible_occurrence_count",
                "observed_week_count",
                "analysis_calendar_week_count",
            ),
        )
        rate, rate_field = cls._lior_grounding_first_number(
            item, ("support_rate", "week_coverage_rate")
        )
        if rate is None and numerator is not None and denominator:
            rate = round(float(numerator) / float(denominator), 4)
            rate_field = "computed_from_numerator_and_denominator"
        observed_span = cls._lior_grounding_observed_span(
            item, decision, period, numerator
        )

        counts = {}
        for key in (
            "encounter_count",
            "actual_encounter_count",
            "logical_appointment_count",
            "active_date_count",
            "weeks_with_activity",
            "weeks_with_confirmed_urgent_actual",
            "confirmed_no_show_count",
            "combined_no_show_signal_count",
            "matched_visit_count",
            "pair_count",
            "measurable_occurrence_count",
            "recommended_reserve_slots",
            "recommended_reserve_minutes",
        ):
            value = cls._lior_grounding_number(item.get(key))
            if value is not None:
                counts[key] = value
        delay = item.get("delay_minutes")
        if isinstance(delay, dict):
            value = cls._lior_grounding_number(delay.get("count"))
            if value is not None:
                counts["delay_measurement_count"] = value

        observed_weeks, observed_weeks_field = cls._lior_grounding_first_number(
            item, ("observed_week_count", "analysis_calendar_week_count")
        )
        if observed_weeks is None:
            observed_weeks, observed_weeks_field = (
                cls._lior_grounding_first_number(
                    patient_visits, ("observed_week_count",)
                )
            )

        thresholds = item.get("threshold_evaluation")
        if not isinstance(thresholds, dict):
            thresholds = {}
        tier = str(item.get("decision_tier") or "")
        required, required_field = cls._lior_grounding_required_support(
            thresholds, tier
        )
        wording_allowed = bool(
            numerator is not None
            and required is not None
            and float(numerator) >= float(required)
        )
        minimum_encounters, _ = cls._lior_grounding_first_number(
            thresholds, ("min_encounters", "minimum_encounters")
        )
        encounter_count, _ = cls._lior_grounding_first_number(
            item, ("encounter_count", "actual_encounter_count")
        )
        if (
            wording_allowed
            and minimum_encounters is not None
            and (
                encounter_count is None
                or float(encounter_count) < float(minimum_encounters)
            )
        ):
            wording_allowed = False

        attributes = {}
        for key in (
            "visit_type_name",
            "visit_type",
            "modality",
            "reserve_type",
            "target",
        ):
            value = str(item.get(key) or "").strip()
            if value:
                attributes[key] = value

        window = {
            "weekday": item.get("weekday"),
            "time_from": item.get("time_from"),
            "time_to": item.get("time_to"),
        }
        target_window = {
            "weekday": item.get("target_weekday"),
            "time_from": item.get("target_time_from"),
            "time_to": item.get("target_time_to"),
        }
        if not any(target_window.values()):
            target_window = None

        has_specific_basis = bool(
            numerator is not None
            or counts
            or observed_weeks is not None
            or attributes
            or any(window.values())
        )
        return {
            "contract_version": "v2",
            "complete": bool(
                period.get("from") and period.get("to") and has_specific_basis
            ),
            "period": {
                **period,
                "observed_weeks": observed_weeks,
                "observed_weeks_field": observed_weeks_field,
            },
            "analysis_window": dict(period),
            "observed_pattern_span": observed_span,
            "window": window,
            "target_window": target_window,
            "support": {
                "numerator": numerator,
                "numerator_field": numerator_field,
                "denominator": denominator,
                "denominator_field": denominator_field,
                "rate": rate,
                "rate_field": rate_field,
                "required": required,
                "required_field": required_field,
            },
            "counts": counts,
            "attributes": attributes,
            "threshold_evaluation": thresholds,
            "recurrence": {
                "wording_allowed": wording_allowed,
                "throughout_period_wording_allowed": bool(
                    wording_allowed
                    and observed_span.get(
                        "distributed_across_analysis_window"
                    )
                ),
                "isolated": bool(numerator is not None and float(numerator) <= 1),
                "tier": tier or None,
                "evidence_type": (
                    item.get("candidate_type") or item.get("insight_type")
                ),
            },
        }

    def _lior_grounding_attach_factual_basis(self, metrics):
        if not isinstance(metrics, dict):
            return
        baseline = self._payload(self.baseline) or {}
        decision = self._payload(getattr(self, "decision_kpis", None)) or {}
        recommendation_evidence = metrics.get("recommendation_evidence")
        if not isinstance(recommendation_evidence, dict):
            recommendation_evidence = {}
        for items in recommendation_evidence.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item["factual_basis"] = self._lior_grounding_factual_basis(
                    item, metrics, decision
                )
        insights = metrics.get("insight_candidates")
        if not isinstance(insights, list):
            insights = []
        for item in insights:
            if not isinstance(item, dict):
                continue
            self._apply_effective_window(baseline, item)
            item["factual_basis"] = self._lior_grounding_factual_basis(
                item, metrics, decision
            )
        metrics["factual_basis_contract"] = {
            "contract_version": "v2",
            "required_on_recommendations_and_insights": True,
            "period": self._lior_grounding_period(
                metrics.get("analysis_context") or {}
            ),
            "recurrence_language_requires_verified_support": True,
            "isolated_events_must_not_be_described_as_recurring": True,
            "analysis_window_is_distinct_from_observed_pattern_span": True,
            "throughout_period_wording_requires_distributed_occurrences": True,
        }
'''


REQUIRED_ANALYSIS_BUILDER_TEMPLATE = r'''
class AnalyticsFeatureBuilder(Component):
    @staticmethod
    def _lior_required_recommendation_count(metrics, family):
        evidence = metrics.get("recommendation_evidence") or {}
        values = evidence.get(family)
        return len(values) if isinstance(values, list) else 0

    @staticmethod
    def _lior_required_domain(source, recommendation_count):
        source = dict(source) if isinstance(source, dict) else {}
        measurement_status = str(
            source.pop("measurement_status", source.pop("status", "unavailable"))
            or "unavailable"
        )
        status = (
            "checked"
            if measurement_status in {"available", "checked"}
            else "unavailable"
        )
        comparison_incomplete = bool(
            source.get("comparison_unavailable_reasons")
        )
        recommendation_found = bool(recommendation_count)
        if comparison_incomplete:
            outcome = "comparison_incomplete"
        elif status != "checked":
            outcome = "data_unavailable"
        elif recommendation_found:
            outcome = "recommendation_found"
        else:
            outcome = "no_change_recommended"
        return {
            "contract_version": "v1",
            "status": status,
            "checked": status == "checked",
            "recommendation_found": recommendation_found,
            "recommendation_count": int(recommendation_count),
            "outcome": outcome,
            "no_recommendation_reason": (
                "comparison_incomplete"
                if comparison_incomplete
                else (
                    "no_candidate_passed_recommendation_thresholds"
                    if status == "checked" and not recommendation_found
                    else None
                )
            ),
            **source,
        }

    def _lior_required_analysis_domains(self, metrics):
        decision = self._payload(getattr(self, "decision_kpis", None)) or {}
        required_inputs = decision.get("required_analysis_inputs") or {}
        findings = decision.get("findings") or {}
        no_show = findings.get("no_show")
        no_show_source = {
            "measurement_status": (
                "available" if isinstance(no_show, dict) else "unavailable"
            ),
            "combined_no_show_signal_count": (
                no_show.get("combined_no_show_signal_count")
                if isinstance(no_show, dict)
                else None
            ),
            "by_weekday": (
                list(no_show.get("by_weekday") or [])
                if isinstance(no_show, dict)
                else []
            ),
            "by_60_minute_window": (
                list(no_show.get("by_60_minute_window") or [])
                if isinstance(no_show, dict)
                else []
            ),
            "unavailable_reason": (
                None if isinstance(no_show, dict) else "no_show_analysis_unavailable"
            ),
        }

        inventory = decision.get("existing_calendar_settings")
        if not isinstance(inventory, dict):
            inventory = metrics.get("existing_calendar_settings")
        inventory = inventory if isinstance(inventory, dict) else {}
        inventory_complete = bool(inventory.get("complete"))
        inventory_status = str(inventory.get("inventory_status") or "")
        reserves = [
            dict(setting)
            for setting in (inventory.get("reserves") or [])
            if isinstance(setting, dict)
        ]
        reserve_source = {
            "measurement_status": (
                "available"
                if inventory_complete
                and inventory_status not in {"unavailable", "incomplete"}
                else "unavailable"
            ),
            "inventory_complete": inventory_complete,
            "reserve_found": bool(reserves),
            "reserve_count": len(reserves),
            "reserves": reserves,
            "unavailable_reason": (
                None
                if inventory_complete
                and inventory_status not in {"unavailable", "incomplete"}
                else (
                    inventory.get("unavailable_reason")
                    or "reserve_inventory_unavailable_or_incomplete"
                )
            ),
        }

        segment_source = required_inputs.get("segment_duration_by_visit_type")
        modality_source = required_inputs.get("no_show_by_modality")
        return {
            "segment_duration_by_visit_type": self._lior_required_domain(
                segment_source,
                self._lior_required_recommendation_count(
                    metrics, "segment_adjustment_candidates"
                ),
            ),
            "no_show_by_weekday_hour": self._lior_required_domain(
                no_show_source,
                self._lior_required_recommendation_count(
                    metrics, "no_show_pattern_candidates"
                ),
            ),
            "no_show_by_modality": self._lior_required_domain(
                modality_source,
                0,
            ),
            "reserve_utilization": self._lior_required_domain(
                reserve_source,
                self._lior_required_recommendation_count(
                    metrics, "reserve_utilization_candidates"
                ),
            ),
        }

    def _lior_required_attach_analysis_domains(self, metrics):
        if not isinstance(metrics, dict):
            return
        metrics["required_analysis_domains"] = (
            self._lior_required_analysis_domains(metrics)
        )
        metrics["required_analysis_domains_contract"] = {
            "contract_version": "v1",
            "all_required_domains_always_present": True,
            "no_recommendation_is_explicit": True,
            "unavailable_data_is_not_interpreted_as_no_change": True,
        }
'''


def _patch_required_analysis_builder(code: str) -> str:
    code = _insert_class_methods(
        code,
        "AnalyticsFeatureBuilder",
        REQUIRED_ANALYSIS_BUILDER_TEMPLATE,
        (
            "_lior_required_recommendation_count",
            "_lior_required_domain",
            "_lior_required_analysis_domains",
            "_lior_required_attach_analysis_domains",
        ),
        "LIOR_REQUIRED_ANALYSIS_BUILDER_V1_ACTIVE",
    )
    call = "        self._lior_required_attach_analysis_domains(metrics)\n"
    if call not in code:
        anchor = "        self._lior_grounding_attach_factual_basis(metrics)\n"
        if code.count(anchor) != 1:
            raise ValueError(
                "Required analysis domains: expected one pre-persistence grounding anchor"
            )
        code = code.replace(anchor, call + "\n" + anchor, 1)
    return _replace_class_methods(
        code,
        "AnalyticsFeatureBuilder",
        REQUIRED_ANALYSIS_BUILDER_TEMPLATE,
        ("_lior_required_domain",),
        "LIOR_REQUIRED_ANALYSIS_STATUS_NORMALIZATION_V2_ACTIVE",
        {},
    )


def _patch_builder_factual_basis(code: str) -> str:
    marker = "LIOR_ANALYTICS_FACTUAL_BASIS_V1_ACTIVE"
    if marker in code:
        return code
    call = "        self._lior_grounding_attach_factual_basis(metrics)\n"
    persistence_anchor = (
        '        persistence = {"requested": bool(self.persist_metrics), '
        '"saved": False, "analysis_metric_id": None, "error": None}\n'
    )
    if call not in code:
        if code.count(persistence_anchor) != 1:
            raise ValueError(
                "Factual basis: expected one Analytics persistence anchor, "
                f"found {code.count(persistence_anchor)}"
            )
        code = code.replace(
            persistence_anchor,
            call + "\n" + persistence_anchor,
            1,
        )

    tree = ast.parse(code)
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "AnalyticsFeatureBuilder"
    ]
    if len(definitions) != 1:
        raise ValueError(
            "Factual basis: expected one AnalyticsFeatureBuilder, "
            f"found {len(definitions)}"
        )
    definition = definitions[0]
    existing_methods = {
        node.name
        for node in definition.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    template_class = next(
        node
        for node in ast.parse(FACTUAL_BASIS_METHOD_TEMPLATE).body
        if isinstance(node, ast.ClassDef)
    )
    methods = [
        node
        for node in template_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    conflicts = sorted(node.name for node in methods if node.name in existing_methods)
    if conflicts:
        raise ValueError(
            f"Factual basis helper methods already exist without marker: {conflicts}"
        )
    rendered = [
        textwrap.indent(ast.unparse(node), "    ")
        for node in methods
    ]
    lines = code.splitlines()
    lines[definition.end_lineno : definition.end_lineno] = [
        "",
        f"    {marker} = True",
        "",
        *("\n\n".join(rendered).splitlines()),
    ]
    patched = "\n".join(lines).rstrip() + "\n"
    ast.parse(patched)
    return patched


def _upgrade_builder_occurrence_basis(code: str) -> str:
    code = _insert_class_methods(
        code,
        "AnalyticsFeatureBuilder",
        FACTUAL_BASIS_METHOD_TEMPLATE,
        (
            "_lior_grounding_occurrence_dates",
            "_lior_grounding_occurrence_source",
            "_lior_grounding_observed_span",
        ),
        "LIOR_ANALYTICS_OCCURRENCE_BASIS_HELPERS_ACTIVE",
    )
    code = _replace_class_methods(
        code,
        "AnalyticsFeatureBuilder",
        FACTUAL_BASIS_METHOD_TEMPLATE,
        (
            "_lior_grounding_factual_basis",
            "_lior_grounding_attach_factual_basis",
        ),
        "LIOR_ANALYTICS_OCCURRENCE_BASIS_V2_ACTIVE",
        {},
    )
    return _replace_class_methods(
        code,
        "AnalyticsFeatureBuilder",
        FACTUAL_BASIS_METHOD_TEMPLATE,
        (
            "_lior_grounding_occurrence_source",
            "_lior_grounding_observed_span",
            "_lior_grounding_factual_basis",
        ),
        "LIOR_ANALYTICS_OCCURRENCE_COMPLETENESS_V3_ACTIVE",
        {},
    )


def patch_analytics_v2(flow: dict[str, Any]) -> dict[str, Any]:
    """Patch Analytics in place and return the same flow for composition."""

    historical = _node_by_id(flow, HISTORICAL_NODE_ID)
    decision = _node_by_id(flow, DECISION_NODE_ID)
    builder = _node_by_id(flow, BUILDER_NODE_ID)
    pressure = _node_by_id(flow, PRESSURE_NODE_ID)

    _set_code(pressure, _patch_pressure_occurrence_sources(_code(pressure)))

    _set_code(
        historical,
        _inject_guarded_methods(
            _code(historical),
            "HistoricalPerformanceAnalyzer",
            "LIOR_ANALYTICS_V2_HISTORICAL",
            HISTORICAL_METHOD_TEMPLATE,
            "analyze",
        ),
    )
    decision_code = _inject_guarded_methods(
        _patch_decision_occurrence_sources(_code(decision)),
            "DecisionKPIAnalyzer",
            "LIOR_ANALYTICS_V2_DECISION",
            DECISION_METHOD_TEMPLATE,
            "analyze",
        )
    decision_code = _upgrade_decision_occurrence_contract(decision_code)
    _set_code(decision, _patch_required_analysis_decision(decision_code))
    builder_code = _inject_guarded_methods(
        _code(builder),
        "AnalyticsFeatureBuilder",
        "LIOR_ANALYTICS_V2_BUILDER",
        BUILDER_METHOD_TEMPLATE,
        "build",
    )
    builder_code = _patch_builder_pushed_occurrence_sources(
        _upgrade_builder_occurrence_basis(
            _patch_builder_factual_basis(builder_code)
        )
    )
    builder_code = _patch_required_analysis_builder(builder_code)
    builder_code = _replace_class_methods(
        builder_code,
        "AnalyticsFeatureBuilder",
        BUILDER_METHOD_TEMPLATE,
        ("build",),
        "LIOR_ANALYTICS_V2_PERSISTED_INSIGHT_CLIP_ACTIVE",
        {"super().build()": "self._lior_v2_original_build()"},
    )
    _set_code(builder, builder_code)
    return flow


def upgrade_analytics_v2_nullsafe(flow: dict[str, Any]) -> dict[str, Any]:
    """Replace the deployed v2 Decision enrichment with null-safe methods."""

    decision = _node_by_id(flow, DECISION_NODE_ID)
    code = _replace_class_methods(
        _code(decision),
        "DecisionKPIAnalyzer",
        DECISION_METHOD_TEMPLATE,
        ("_lior_v2_resolve_preferences", "_lior_v2_measure_reserves"),
        "LIOR_ANALYTICS_V2_DECISION_NULLSAFE_ACTIVE",
        {},
    )
    code = _replace_class_methods(
        code,
        "DecisionKPIAnalyzer",
        REQUIRED_ANALYSIS_DECISION_TEMPLATE,
        ("analyze",),
        "LIOR_ANALYTICS_REQUIRED_DECISION_WRAPPER_V2_ACTIVE",
        {},
    )
    _set_code(decision, code)
    return flow


def upgrade_analytics_v2_diagnostic(flow: dict[str, Any]) -> dict[str, Any]:
    """Expose the exact original Decision method line without logging payloads."""

    decision = _node_by_id(flow, DECISION_NODE_ID)
    _set_code(
        decision,
        _replace_class_methods(
            _code(decision),
            "DecisionKPIAnalyzer",
            DECISION_METHOD_TEMPLATE,
            ("analyze",),
            "LIOR_ANALYTICS_V2_DECISION_DIAGNOSTIC_V2_ACTIVE",
            {"super().analyze()": "self._lior_v2_original_analyze()"},
        ),
    )
    return flow


def upgrade_analytics_v2_return_types(flow: dict[str, Any]) -> dict[str, Any]:
    """Restore Langflow 1.9.2 connector types on overridden output methods."""

    specifications = (
        (
            HISTORICAL_NODE_ID,
            "HistoricalPerformanceAnalyzer",
            HISTORICAL_METHOD_TEMPLATE,
            "analyze",
            {"super().analyze()": "self._lior_v2_original_analyze()"},
        ),
        (
            DECISION_NODE_ID,
            "DecisionKPIAnalyzer",
            REQUIRED_ANALYSIS_DECISION_TEMPLATE,
            "analyze",
            {},
        ),
        (
            BUILDER_NODE_ID,
            "AnalyticsFeatureBuilder",
            BUILDER_METHOD_TEMPLATE,
            "build",
            {"super().build()": "self._lior_v2_original_build()"},
        ),
    )
    for node_id, class_name, template, method_name, replacements in specifications:
        node = _node_by_id(flow, node_id)
        _set_code(
            node,
            _replace_class_methods(
                _code(node),
                class_name,
                template,
                (method_name,),
                "LIOR_LANGFLOW_1_9_2_RETURN_TYPES_ACTIVE",
                replacements,
            ),
        )
    return flow


def remove_analytics_v2_diagnostic(flow: dict[str, Any]) -> dict[str, Any]:
    """Remove temporary Decision diagnostics after the root cause is fixed."""

    decision = _node_by_id(flow, DECISION_NODE_ID)
    code = _code(decision)
    for marker in (
        "    LIOR_ANALYTICS_V2_DECISION_DIAGNOSTIC_ACTIVE = True\n",
        "    LIOR_ANALYTICS_V2_DECISION_DIAGNOSTIC_V2_ACTIVE = True\n",
    ):
        code = code.replace(marker, "")
    code = _replace_class_methods(
        code,
        "DecisionKPIAnalyzer",
        REQUIRED_ANALYSIS_DECISION_TEMPLATE,
        ("analyze",),
        "LIOR_ANALYTICS_V2_DECISION_DIAGNOSTIC_REMOVED_ACTIVE",
        {},
    )
    _set_code(decision, code)
    return flow


__all__ = [
    "patch_analytics_v2",
    "upgrade_analytics_v2_nullsafe",
    "upgrade_analytics_v2_diagnostic",
    "upgrade_analytics_v2_return_types",
    "remove_analytics_v2_diagnostic",
]
