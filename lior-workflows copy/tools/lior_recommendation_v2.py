#!/usr/bin/env python3
"""Offline, composable Recommendation v2 patch for the Lior Langflow flow."""

from __future__ import annotations

import ast
import hashlib
from typing import Any


SPLITTER_NODE_ID = "recommendation_context_splitter-dU9xQ"
BUSINESS_NODE_ID = "recommendation_business_rule_validator-TvYcq"
PRESENTER_NODE_ID = "recommendation_presenter-TuUXM"

PROMPT_AGENT_PAIRS = {
    "TextInput-enwvR": "Agent-nw0eZ",
    "TextInput-CsN8n": "Agent-1q7hm",
    "TextInput-t85tX": "Agent-N1co0",
}


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


def _patch_original_class(
    code: str,
    class_name: str,
    prerequisite_anchor: str,
    marker: str,
    wrapper: str,
    renamed_methods: dict[str, str],
    wrapper_replacements: dict[str, str],
) -> str:
    if marker in code:
        definitions = [
            node
            for node in ast.parse(code).body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if len(definitions) != 1:
            raise ValueError(
                f"{marker}: expected one top-level {class_name}, "
                f"found {len(definitions)}"
            )
        return code
    if code.count(prerequisite_anchor) != 1:
        raise ValueError(
            f"{marker}: expected one v1 prerequisite anchor "
            f"{prerequisite_anchor!r}, found {code.count(prerequisite_anchor)}"
        )
    tree = ast.parse(code)
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(definitions) != 1:
        raise ValueError(
            f"{marker}: expected one top-level {class_name}, found {len(definitions)}"
        )
    definition = definitions[0]
    lines = code.splitlines()
    for old_name, new_name in renamed_methods.items():
        methods = [
            node
            for node in definition.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == old_name
        ]
        if len(methods) != 1:
            raise ValueError(
                f"{marker}: expected one method {old_name}, found {len(methods)}"
            )
        method = methods[0]
        line = lines[method.lineno - 1]
        suffix = line[method.col_offset :]
        anchor = f"def {old_name}"
        if suffix.count(anchor) != 1:
            raise ValueError(f"{marker}: unstable definition anchor for {old_name}")
        lines[method.lineno - 1] = (
            line[: method.col_offset]
            + suffix.replace(anchor, f"def {new_name}", 1)
        )

    wrapper_tree = ast.parse(wrapper)
    wrapper_classes = [
        node
        for node in wrapper_tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(wrapper_classes) != 1:
        raise ValueError(
            f"{marker}: expected one template {class_name}, "
            f"found {len(wrapper_classes)}"
        )
    wrapper_class = wrapper_classes[0]
    wrapper_lines = wrapper.splitlines()
    first_body_line = wrapper_class.body[0].lineno
    body = "\n".join(
        wrapper_lines[first_body_line - 1 : wrapper_class.end_lineno]
    )
    for old, new in wrapper_replacements.items():
        count = body.count(old)
        if count != 1:
            raise ValueError(
                f"{marker}: expected one wrapper anchor {old!r}, found {count}"
            )
        body = body.replace(old, new, 1)

    insertion = ["", f"    # {marker}", *body.rstrip().splitlines()]
    lines[definition.end_lineno : definition.end_lineno] = insertion
    patched = "\n".join(lines).rstrip() + "\n"
    ast.parse(patched)
    final_definitions = [
        node
        for node in ast.parse(patched).body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(final_definitions) != 1:
        raise ValueError(
            f"{marker}: direct patch produced {len(final_definitions)} definitions"
        )
    return patched


def _patch_required_analysis_splitter(code: str) -> str:
    marker = "LIOR_REQUIRED_ANALYSIS_SPLITTER_V1_ACTIVE"
    if marker in code:
        return code
    anchor = '            "data_quality": metrics.get("data_quality") or {},\n'
    if code.count(anchor) != 1:
        raise ValueError(
            f"{marker}: expected one data-quality context anchor"
        )
    addition = (
        '            "required_analysis_domains": {\n'
        '                "metric_path": "required_analysis_domains",\n'
        '                "value": metrics.get("required_analysis_domains") or {},\n'
        '                "actionable": False,\n'
        '            },\n'
    )
    code = code.replace(anchor, addition + anchor, 1)
    tree = ast.parse(code)
    definition = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "RecommendationContextSplitter"
    )
    lines = code.splitlines()
    lines.insert(definition.end_lineno, f"    {marker} = True")
    patched = "\n".join(lines).rstrip() + "\n"
    ast.parse(patched)
    return patched


BUSINESS_WRAPPER = r'''
# LIOR_RECOMMENDATION_V2_BUSINESS
_LiorRecommendationV2BusinessBase = RecommendationBusinessRuleValidator


class RecommendationBusinessRuleValidator(_LiorRecommendationV2BusinessBase):
    """Deterministically resolves settings and exact-window minute ownership."""

    _LIOR_V2_ALLOCATION_ACTIONS = {
        "allocate_digital_window",
        "allocate_telephone_video_visit_window",
        "allocate_visit_type_window",
    }

    @classmethod
    def _cluster_paths(cls, paths, candidate_values):
        """Never merge candidates across distinct Analytics evidence families."""
        by_family = {}
        for path in paths:
            path = str(path)
            prefix = "recommendation_evidence."
            family = (
                path[len(prefix):].split("[", 1)[0]
                if path.startswith(prefix)
                else path.split("[", 1)[0]
            )
            by_family.setdefault(family, []).append(path)
        clusters = []
        for family in sorted(by_family):
            clusters.extend(
                super()._cluster_paths(by_family[family], candidate_values)
            )
        return clusters

    @staticmethod
    def _lior_v2_family(rec):
        for evidence in rec.get("evidence") or []:
            if not isinstance(evidence, dict) or evidence.get("verified") is not True:
                continue
            path = str(evidence.get("metric_path") or "")
            prefix = "recommendation_evidence."
            if path.startswith(prefix):
                return path[len(prefix):].split("[", 1)[0]
        return ""

    @staticmethod
    def _lior_v2_names(setting):
        names = []
        for item in setting.get("preferred_visit_types") or []:
            if not isinstance(item, dict):
                continue
            value = (
                item.get("preferred_visit_type_name")
                or item.get("preferred_name")
                or item.get("resolved_preference_name")
                or item.get("visit_type_name")
                or item.get("preferred_label")
                or item.get("name")
            )
            value = str(value or "").strip()
            if value and value not in names:
                names.append(value)
        return names

    @staticmethod
    def _lior_v2_action_matches_preference(action, names):
        action_name = str(action.get("action") or "")
        normalized_names = [
            str(name or "").strip().replace("־", " ") for name in names
        ]
        if action_name == "allocate_telephone_video_visit_window":
            return any(
                "טלפון" in name or "טלפוני" in name or "וידאו" in name
                for name in normalized_names
            )
        target = str(action.get("target") or "").strip()
        if not target:
            return True
        return any(
            target == name or target in name or name in target
            for name in normalized_names
        )

    @staticmethod
    def _lior_v2_inventory_index(inventory):
        index = {}
        if not isinstance(inventory, dict):
            return index
        for key in ("preferences", "reserves"):
            for setting in inventory.get(key) or []:
                if isinstance(setting, dict) and setting.get("setting_id"):
                    index[str(setting["setting_id"])] = setting
        return index

    @classmethod
    def _lior_v2_enrich_context(cls, rec, inventory):
        context = rec.get("existing_settings_context") or {}
        index = cls._lior_v2_inventory_index(inventory)
        for requirement in context.get("requirements") or []:
            if not isinstance(requirement, dict):
                continue
            source = index.get(str(requirement.get("setting_id") or ""))
            if not isinstance(source, dict):
                continue
            merged = dict(source)
            merged.update(requirement.get("setting") or {})
            for key in (
                "booked_segment_units",
                "matched_actual_segment_units",
                "matched_urgent_segment_units",
                "measurement_status",
            ):
                if key in source:
                    merged[key] = source.get(key)
            requirement["setting"] = merged
        rec["existing_settings_context"] = context

    @classmethod
    def _lior_v2_preference_resolution(cls, rec):
        action = rec.get("calendar_action") or {}
        requirements = [
            requirement
            for requirement in (
                (rec.get("existing_settings_context") or {}).get("requirements") or []
            )
            if isinstance(requirement, dict)
            and requirement.get("setting_type") == "preference"
        ]
        if not requirements:
            return {
                "state": "not_applicable",
                "overlaps": False,
                "resolved_preference_names": [],
            }

        names = []
        states = []
        full_compliance_seen = False
        comparable_booked_segments = 0
        target = str(action.get("target") or "").strip()
        for requirement in requirements:
            setting = requirement.get("setting") or {}
            setting_names = cls._lior_v2_names(setting)
            for name in setting_names:
                if name not in names:
                    names.append(name)
            compliance = setting.get("compliance") or {}
            try:
                full_compliance = (
                    compliance.get("status") == "available"
                    and abs(float(compliance.get("value")) - 1.0) <= 1e-9
                )
            except Exception:
                full_compliance = False
            try:
                comparable_booked_segments += int(
                    compliance.get("comparable_booked_segments") or 0
                )
            except (TypeError, ValueError):
                pass
            full_compliance_seen = full_compliance_seen or full_compliance
            if (
                setting_names
                and not cls._lior_v2_action_matches_preference(
                    action, setting_names
                )
            ):
                states.append("conflict")
            elif full_compliance:
                states.append("preserve")
            else:
                states.append("change")

        state = (
            "conflict"
            if "conflict" in states
            else "change"
            if "change" in states
            else "preserve"
        )
        if (
            full_compliance_seen
            and str(action.get("action") or "") in cls._LIOR_V2_ALLOCATION_ACTIONS
        ):
            action["recommendation_mode"] = (
                "keep_current"
                if state == "preserve"
                else "keep_current_pending_conflict_resolution"
            )
        return {
            "state": state,
            "overlaps": True,
            "resolved_preference_names": names,
            "full_compliance_100": full_compliance_seen,
            "comparable_booked_segments": comparable_booked_segments,
        }

    @staticmethod
    def _lior_v2_reserve_overlap(rec):
        requirements = [
            requirement
            for requirement in (
                (rec.get("existing_settings_context") or {}).get("requirements") or []
            )
            if isinstance(requirement, dict)
            and requirement.get("setting_type") == "reserve"
        ]
        settings = []
        for requirement in requirements:
            setting = requirement.get("setting") or {}
            quantities = {
                "defined": setting.get("defined_segment_units"),
                "booked": setting.get("booked_segment_units"),
                "matched_actual": setting.get("matched_actual_segment_units"),
                "matched_urgent": setting.get("matched_urgent_segment_units"),
            }
            actualization = setting.get("actualization") or {}
            unavailable = (
                quantities["matched_actual"] is None
                and quantities["matched_urgent"] is None
            ) or actualization.get("status") == "unavailable"
            settings.append(
                {
                    "setting_id": requirement.get("setting_id"),
                    "weekday": setting.get("weekday"),
                    "time_from": setting.get("time_from"),
                    "time_to": setting.get("time_to"),
                    "quantities": quantities,
                    "measurement_status": (
                        "unavailable" if unavailable else "available"
                    ),
                    "unavailable_reason": actualization.get("unavailable_reason"),
                }
            )
        first = settings[0] if settings else {}
        return {
            "overlaps": bool(settings),
            "handling": (
                "adjust_existing_reserve_not_add"
                if settings
                else "create_within_recommended_window"
            ),
            "settings": settings,
            "quantities": first.get(
                "quantities",
                {
                    "defined": None,
                    "booked": None,
                    "matched_actual": None,
                    "matched_urgent": None,
                },
            ),
            "measurement_status": first.get("measurement_status", "not_applicable"),
            "unavailable_reason": first.get("unavailable_reason"),
        }

    @staticmethod
    def _lior_v2_expected_impact(rec):
        action_name = str((rec.get("calendar_action") or {}).get("action") or "")
        qualitative = {
            "allocate_reserve": (
                "שיפור היכולת לתת מענה לביקוש דחוף בתוך שעות העבודה הקיימות."
            ),
            "protect_flexible_capacity": (
                "הפחתת הלחץ שנוצר מתורים הנוספים מעבר לתכנון הרגיל."
            ),
            "allocate_visit_type_window": (
                "שמירה על רצף תפעולי ברור יותר לסוג הביקור הרלוונטי."
            ),
            "allocate_digital_window": (
                "ריכוז תפעולי עקבי יותר של הפעילות הדיגיטלית."
            ),
            "allocate_telephone_video_visit_window": (
                "ריכוז תפעולי עקבי יותר של ביקורי טלפון ווידאו."
            ),
            "reallocate_capacity_between_windows": (
                "איזון העומס בין חלונות היומן בלי לשנות את שעות העבודה."
            ),
        }.get(
            action_name,
            "שיפור ההתאמה בין מבנה היומן לדפוס הפעילות שנצפה.",
        )

        numeric = None
        numeric_source = "no_verified_candidate_impact_quantity"
        allowed_keys = (
            "expected_completed_visits_per_week_change",
            "verified_expected_visit_change",
            "expected_operational_impact_quantity",
        )
        for evidence in rec.get("evidence") or []:
            if not isinstance(evidence, dict) or evidence.get("verified") is not True:
                continue
            candidate = evidence.get("actual_metric_value")
            if not isinstance(candidate, dict):
                continue
            for key in allowed_keys:
                if candidate.get(key) is not None:
                    numeric = candidate.get(key)
                    numeric_source = f"verified_candidate.{key}"
                    break
            if numeric is not None:
                break
        return {
            "qualitative": qualitative,
            "numeric": numeric,
            "numeric_source": numeric_source,
        }

    @classmethod
    def _lior_v2_planning_window_key(cls, rec):
        action = rec.get("calendar_action") or {}
        values = (
            action.get("weekday"),
            action.get("time_from"),
            action.get("time_to"),
        )
        return tuple(str(value or "").strip() for value in values) if all(values) else None

    def validate(self) -> Data:
        result = super().validate()
        payload = self._payload(result)
        business = self._payload(self.business_context)
        inventory = (
            (business.get("existing_calendar_settings") or {}).get("value") or {}
        )

        recommendations = [
            rec
            for rec in payload.get("recommendations") or []
            if isinstance(rec, dict)
        ]
        for rec in recommendations:
            self._lior_v2_enrich_context(rec, inventory)
            rec["evidence_family"] = self._lior_v2_family(rec)
            rec["preference_resolution"] = self._lior_v2_preference_resolution(rec)
            rec["expected_operational_impact"] = self._lior_v2_expected_impact(rec)
            action = rec.get("calendar_action") or {}
            if action.get("action") == "allocate_reserve":
                rec["reserve_overlap"] = self._lior_v2_reserve_overlap(rec)
                if rec["reserve_overlap"]["overlaps"]:
                    action["reserve_handling"] = "adjust_existing_reserve_not_add"
                    action["existing_reserve_checked"] = True

        quantified_urgent_keys = {
            self._lior_v2_planning_window_key(rec)
            for rec in recommendations
            if (rec.get("calendar_action") or {}).get("action") == "allocate_reserve"
            and self._lior_v2_planning_window_key(rec) is not None
            and (
                (rec.get("calendar_action") or {}).get("recommended_minutes") is not None
                or (rec.get("calendar_action") or {}).get("recommended_slots") is not None
            )
        }
        kept = []
        suppressed = []
        for rec in recommendations:
            action = rec.get("calendar_action") or {}
            if (
                action.get("action") == "protect_flexible_capacity"
                and self._lior_v2_planning_window_key(rec)
                in quantified_urgent_keys
            ):
                rec["disposition"] = "supporting_evidence"
                rec["disposition_reason"] = (
                    "same_planning_window_quantified_urgent_reserve_preferred_no_double_allocation"
                )
                suppressed.append(rec)
                continue
            kept.append(rec)
        payload["recommendations"] = kept
        payload["supporting_evidence"] = list(payload.get("supporting_evidence") or [])
        payload["supporting_evidence"].extend(suppressed)

        suppressed_paths = {
            str(evidence.get("metric_path"))
            for rec in suppressed
            for evidence in rec.get("evidence") or []
            if isinstance(evidence, dict) and evidence.get("metric_path")
        }
        for disposition in payload.get("candidate_dispositions") or []:
            if (
                isinstance(disposition, dict)
                and str(disposition.get("metric_path") or "") in suppressed_paths
            ):
                disposition["disposition"] = "supporting_evidence"
                disposition["reason"] = (
                    "same_planning_window_quantified_urgent_reserve_preferred_no_double_allocation"
                )

        reserve_keys = {
            self._lior_v2_planning_window_key(rec)
            for rec in kept
            if (rec.get("calendar_action") or {}).get("action") == "allocate_reserve"
        }
        buffer_keys = {
            self._lior_v2_planning_window_key(rec)
            for rec in kept
            if (rec.get("calendar_action") or {}).get("action")
            == "protect_flexible_capacity"
        }
        double_allocated = bool((reserve_keys & buffer_keys) - {None})
        validation = payload.setdefault("validation", {})
        validation["urgent_buffer_resolution_rule"] = (
            "prefer_quantified_urgent_reserve_for_same_planning_window"
        )
        validation["urgent_buffer_resolution_rechecked"] = True
        validation["planning_window_double_allocation_remaining"] = double_allocated
        validation["exact_window_double_allocation_remaining"] = double_allocated
        validation["suppressed_operational_buffer_count"] = len(suppressed)
        payload["valid"] = bool(payload.get("valid") and not double_allocated)
        return result
'''


GROUNDING_BUSINESS_WRAPPER = r'''
class RecommendationBusinessRuleValidator(Component):
    def validate(self) -> Data:
        result = self._lior_grounding_base_validate()
        payload = self._payload(result)
        if not isinstance(payload, dict):
            return result
        business = self._payload(self.business_context)
        if not isinstance(business, dict):
            business = {}
        analysis_context = business.get("analysis_context") or {}
        if (
            isinstance(analysis_context, dict)
            and isinstance(analysis_context.get("value"), dict)
        ):
            analysis_context = analysis_context["value"]
        if not isinstance(analysis_context, dict):
            analysis_context = {}
        payload["analysis_context"] = analysis_context

        missing = 0
        recommendations = payload.get("recommendations")
        if not isinstance(recommendations, list):
            recommendations = []
        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            factual_basis = rec.get("factual_basis")
            if not isinstance(factual_basis, dict):
                factual_basis = None
                for evidence in rec.get("evidence") or []:
                    if not isinstance(evidence, dict):
                        continue
                    candidate = evidence.get("actual_metric_value")
                    if not isinstance(candidate, dict):
                        continue
                    candidate_basis = candidate.get("factual_basis")
                    if isinstance(candidate_basis, dict):
                        factual_basis = candidate_basis
                        break
            if isinstance(factual_basis, dict):
                rec["factual_basis"] = factual_basis
            else:
                missing += 1

        validation = payload.setdefault("validation", {})
        validation["factual_basis_contract_version"] = "v1"
        validation["recommendations_with_factual_basis"] = (
            len(recommendations) - missing
        )
        validation["recommendations_missing_factual_basis"] = missing
        validation["factual_basis_complete_for_recommendations"] = missing == 0
        return result
'''


GROUNDING_QUALITY_BUSINESS_WRAPPER = r'''
class RecommendationBusinessRuleValidator(Component):
    @staticmethod
    def _lior_quality_candidate_evidence_key(candidate):
        candidate = candidate if isinstance(candidate, dict) else {}
        basis = candidate.get("factual_basis") or {}
        window = basis.get("window") or {}
        target = basis.get("target_window") or {}
        return (
            candidate.get("candidate_type"),
            candidate.get("action") or candidate.get("allowed_action"),
            window.get("weekday") or candidate.get("weekday"),
            window.get("time_from") or candidate.get("time_from"),
            window.get("time_to") or candidate.get("time_to"),
            target.get("weekday") or candidate.get("target_weekday"),
            target.get("time_from") or candidate.get("target_time_from"),
            target.get("time_to") or candidate.get("target_time_to"),
        )

    @classmethod
    def _cluster_paths(cls, paths, candidate_values):
        by_evidence_window = {}
        for path in paths:
            candidate = candidate_values.get(str(path)) or {}
            key = cls._lior_quality_candidate_evidence_key(candidate)
            by_evidence_window.setdefault(key, []).append(path)
        clusters = []
        for key in sorted(
            by_evidence_window,
            key=lambda value: tuple(str(item or "") for item in value),
        ):
            clusters.extend(
                cls._lior_quality_base_cluster_paths(
                    by_evidence_window[key], candidate_values
                )
            )
        return clusters
'''


REQUIRED_ANALYSIS_BUSINESS_WRAPPER = r'''
class RecommendationBusinessRuleValidator(Component):
    def validate(self) -> Data:
        result = self._lior_required_analysis_base_validate()
        payload = self._payload(result)
        if not isinstance(payload, dict):
            return result
        business = self._payload(self.business_context)
        if not isinstance(business, dict):
            business = {}
        wrapped = business.get("required_analysis_domains") or {}
        domains = (
            wrapped.get("value")
            if isinstance(wrapped, dict) and isinstance(wrapped.get("value"), dict)
            else wrapped
        )
        payload["required_analysis_domains"] = (
            domains if isinstance(domains, dict) else {}
        )
        payload.setdefault("validation", {})[
            "required_analysis_domains_propagated"
        ] = bool(payload["required_analysis_domains"])
        return result
'''


PRESENTER_WRAPPER = r'''
# LIOR_RECOMMENDATION_V2_PRESENTER
_LiorRecommendationV2PresenterBase = RecommendationPresenter


class RecommendationPresenter(_LiorRecommendationV2PresenterBase):
    """Renders the deterministic Recommendation v2 structure in Hebrew."""

    _LIOR_V2_FAMILY_LABELS = {
        "urgent_reserve_candidates": "ביקוש דחוף",
        "reserve_utilization_candidates": "ניצול עתודה",
        "operational_buffer_candidates": "לחץ של תורים שנדחפים",
        "visit_type_allocation_candidates": "דפוס סוג ביקור",
        "digital_admin_window_candidates": "פעילות דיגיטלית",
        "telephone_video_window_candidates": "ביקורי טלפון ווידאו",
        "preference_review_candidates": "העדפה קיימת",
        "capacity_reallocation_candidates": "איזון קיבולת",
    }

    @classmethod
    def _lior_v2_family_label(cls, rec):
        family = cls._clean(rec.get("evidence_family"))
        return cls._LIOR_V2_FAMILY_LABELS.get(family, "")

    @classmethod
    def _lior_v2_impact_text(cls, rec):
        impact = rec.get("expected_operational_impact") or {}
        text = cls._clean(impact.get("qualitative"))
        numeric = impact.get("numeric")
        if numeric is not None:
            rendered = cls._fmt_num(numeric)
            if rendered:
                text = f"{text} השפעה כמותית מאומתת: {rendered}."
        return text

    @classmethod
    def _lior_v2_reserve_detail(cls, rec):
        overlap = rec.get("reserve_overlap") or {}
        if overlap.get("overlaps"):
            parts = [
                "ההמלצה חופפת לעתודה קיימת",
                "ולכן יש להתאים את העתודה הקיימת ולא להוסיף עתודה נוספת",
            ]
            labels = (
                ("defined", "מוגדרות"),
                ("booked", "נקבעו"),
                ("matched_actual", "מומשו בפועל"),
                ("matched_urgent", "מהם"),
            )
            settings = overlap.get("settings") or [
                {
                    "quantities": overlap.get("quantities") or {},
                    "measurement_status": overlap.get("measurement_status"),
                }
            ]
            for index, setting in enumerate(settings, 1):
                rendered = []
                quantities = setting.get("quantities") or {}
                for key, label in labels:
                    value = quantities.get(key)
                    if value is None:
                        continue
                    number = cls._fmt_num(value)
                    if key == "matched_urgent":
                        rendered.append(f"{label} {number} דחופים")
                    else:
                        rendered.append(f"{label} {number}")
                prefix = (
                    "הכמויות שנמדדו"
                    if len(settings) == 1
                    else f"הכמויות בעתודה {index}"
                )
                if rendered:
                    parts.append(prefix + ": " + ", ".join(rendered))
                if setting.get("measurement_status") == "unavailable":
                    parts.append(
                        "נתוני המימוש בפועל והדחיפות אינם זמינים ולא פורשו כאפס"
                    )
            return "; ".join(parts) + "."
        return (
            "ההמלצה אינה חופפת לעתודה קיימת; היא מגדירה מקום בתוך "
            "החלון בלי לשכפל עתודה קיימת."
        )

    @classmethod
    def _recommendation_parts(cls, rec):
        action = cls._action(rec)
        name = cls._action_name(rec)
        resolution = rec.get("preference_resolution") or {}
        state = resolution.get("state")
        names = [
            cls._clean(value)
            for value in resolution.get("resolved_preference_names") or []
            if cls._clean(value)
        ]
        family = cls._lior_v2_family_label(rec)

        if (
            state == "preserve"
            and action.get("recommendation_mode") == "keep_current"
        ):
            label = ", ".join(names) or cls._target(rec) or "סוג הביקור הקיים"
            comparable = resolution.get("comparable_booked_segments")
            comparison_text = (
                f"בכל {comparable} המקטעים שניתנו להשוואה"
                if comparable
                else "במקטעים שניתנו להשוואה"
            )
            parts = (
                "שמירה על ההעדפה הקיימת",
                f"ההעדפה ל־{label} נשמרה {comparison_text}.",
                "מומלץ לשמור על ההעדפה הקיימת ועל החלון הנוכחי ללא ריכוז נוסף.",
            )
        elif (
            resolution.get("full_compliance_100")
            and action.get("recommendation_mode")
            == "keep_current_pending_conflict_resolution"
        ):
            label = ", ".join(names) or "ההעדפה הקיימת"
            parts = (
                "יישוב קונפליקט תוך שמירה על ההעדפה הקיימת",
                f"ההעדפה ל־{label} תואמת ב־100% להזמנות שניתנות להשוואה, אך ההמלצה המוצעת מתנגשת בה.",
                "מומלץ לשמור על ההעדפה והחלון הנוכחיים עד ליישוב הקונפליקט, ללא ריכוז נוסף.",
            )
        else:
            parts = super()._recommendation_parts(rec)
        if not parts:
            return None

        title, why, what = parts
        if state == "change":
            label = ", ".join(names)
            detail = (
                f"ההעדפה הקיימת ל־{label} דורשת שינוי מתואם."
                if label
                else "ההעדפה הקיימת דורשת שינוי מתואם."
            )
            why = f"{why} {detail}"
        elif state == "conflict":
            label = ", ".join(names)
            detail = (
                f"קיים קונפליקט עם ההעדפה המוגדרת ל־{label}; יש ליישב אותו לפני שינוי היומן."
                if label
                else "קיים קונפליקט עם ההעדפה המוגדרת; יש ליישב אותו לפני שינוי היומן."
            )
            why = f"{why} {detail}"

        if name == "allocate_reserve":
            reserve_detail = cls._lior_v2_reserve_detail(rec)
            why = f"{why} {reserve_detail}"
            if (rec.get("reserve_overlap") or {}).get("overlaps"):
                what = re.sub(
                    r"מומלץ לשמור",
                    "מומלץ להתאים את העתודה הקיימת ולשמור",
                    what,
                    count=1,
                )

        if family:
            why = f"{why} ההמלצה מבוססת על {family}."
        impact = cls._lior_v2_impact_text(rec)
        if impact:
            what = f"{what}\n- **השפעה תפעולית צפויה:** {impact}"
        return title, why, what

    @classmethod
    def _presentation_signature(cls, rec):
        return super()._presentation_signature(rec) + (
            cls._clean(rec.get("evidence_family")),
            (rec.get("preference_resolution") or {}).get("state"),
        )

    @classmethod
    def _insight_signature(cls, insight):
        kind = cls._clean(
            insight.get("insight_type") or insight.get("candidate_type")
        )
        aliases = {
            "recurring_delay_recommendation_strength": "recurring_delay",
            "recurring_delay_below_action_threshold": "recurring_delay",
            "recurring_delay_below_recommendation_threshold": "recurring_delay",
            "overall_no_show_pressure": "overall_no_show",
            "material_no_show_signal_without_recurring_hour": "overall_no_show",
        }
        return (
            aliases.get(kind, kind),
            cls._clean(insight.get("presentation_target_key")),
            cls._clean(insight.get("visit_type_code")),
            cls._clean(insight.get("visit_type_name")),
            cls._clean(insight.get("reserve_type")),
        )

    @classmethod
    def _collect_insights(cls, payload):
        insights = super()._collect_insights(payload)
        out = []
        seen = set()
        for insight in insights:
            if cls._clean(insight.get("weekday")):
                continue
            sentence = cls._insight_sentence(insight)
            if not sentence:
                continue
            key = (
                cls._clean(insight.get("weekday")),
                cls._clean(insight.get("time_from")),
                cls._clean(insight.get("time_to")),
                cls._insight_signature(insight),
                sentence,
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(insight)
        return out

    @classmethod
    def _insight_sentence(cls, insight):
        kind = cls._clean(insight.get("insight_type"))
        if kind != "forecast_change":
            return super()._insight_sentence(insight)

        direction = cls._clean(
            insight.get("direction")
            or insight.get("forecast_direction")
            or insight.get("change_direction")
        ).lower()
        magnitude = insight.get("magnitude")
        if magnitude is None:
            magnitude = insight.get("forecast_magnitude")
        if magnitude is None:
            magnitude = insight.get("change_magnitude")
        if not direction or magnitude is None:
            return cls._lior_v2_base_insight_sentence(insight)
        direction_he = {
            "increase": "עלייה",
            "up": "עלייה",
            "decrease": "ירידה",
            "down": "ירידה",
            "stable": "יציבות",
        }.get(direction)
        if not direction_he:
            return cls._lior_v2_base_insight_sentence(insight)
        rendered = cls._fmt_num(magnitude)
        if not rendered:
            return ""
        unit = cls._clean(
            insight.get("magnitude_unit") or insight.get("forecast_magnitude_unit")
        ).lower()
        suffix = "%" if unit in {"percent", "percentage", "%"} else (
            f" {unit}" if unit else ""
        )
        return (
            f"התחזית מצביעה על {direction_he} של {rendered}{suffix} "
            "בהיקף הביקורים."
        )

    @classmethod
    def _lior_v2_schedule_label(cls, recs):
        if not recs:
            return ""
        rec = recs[0]
        action = cls._action(rec)
        resolution = rec.get("preference_resolution") or {}
        if (
            resolution.get("state") == "preserve"
            and action.get("recommendation_mode") == "keep_current"
        ):
            return "שמירה על ההעדפה הקיימת"
        return cls._schedule_window_label(recs)

    @staticmethod
    def _lior_v2_hhmm(minutes):
        return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"

    @classmethod
    def _lior_v2_weekly_schedule_table(cls, payload):
        baseline = payload.get("baseline_constraints") or {}
        if isinstance(baseline.get("value"), dict):
            baseline = baseline["value"]
        working_windows = [
            entry
            for entry in baseline.get("working_windows") or []
            if isinstance(entry, dict)
        ]
        if not working_windows:
            return ""

        recs = [
            rec
            for rec in payload.get("recommendations") or []
            if isinstance(rec, dict)
        ]
        rec_groups, global_recs = cls._group_recommendations(recs)
        groups_by_day = defaultdict(list)
        for weekday, time_from, time_to, grouped_recs in rec_groups:
            start = cls._tm(time_from)
            end = cls._tm(time_to)
            label = cls._lior_v2_schedule_label(grouped_recs)
            if start is None or end is None or end <= start or not label:
                continue
            groups_by_day[weekday].append((start, end, label))

        rows = []
        for entry in sorted(
            working_windows,
            key=lambda item: cls._day_rank(item.get("weekday_name")),
        ):
            weekday = cls._clean(entry.get("weekday_name"))
            if not weekday:
                continue
            shifts = []
            for key in ("shift_1", "shift_2"):
                shift = entry.get(key)
                if not isinstance(shift, dict):
                    continue
                start = cls._tm(shift.get("from"))
                end = cls._tm(shift.get("to"))
                if start is not None and end is not None and end > start:
                    shifts.append((start, end))

            for shift_start, shift_end in shifts:
                recommendations = []
                coverage = []
                for rec_start, rec_end, label in groups_by_day.get(weekday, []):
                    start = max(shift_start, rec_start)
                    end = min(shift_end, rec_end)
                    if end <= start:
                        continue
                    recommendations.append((start, end, label, 1))
                    coverage.append((start, end))

                merged_coverage = []
                for start, end in sorted(coverage):
                    if merged_coverage and start <= merged_coverage[-1][1]:
                        merged_coverage[-1] = (
                            merged_coverage[-1][0],
                            max(merged_coverage[-1][1], end),
                        )
                    else:
                        merged_coverage.append((start, end))

                regular = []
                cursor = shift_start
                for start, end in merged_coverage:
                    if start > cursor:
                        regular.append((cursor, start, "פעילות רגילה", 0))
                    cursor = max(cursor, end)
                if cursor < shift_end:
                    regular.append((cursor, shift_end, "פעילות רגילה", 0))

                for start, end, label, kind_order in sorted(
                    regular + recommendations,
                    key=lambda row: (row[0], row[3], row[1], row[2]),
                ):
                    rows.append(
                        (
                            weekday,
                            f"{cls._lior_v2_hhmm(start)}–{cls._lior_v2_hhmm(end)}",
                            label,
                        )
                    )

        if not rows:
            return ""
        lines = [
            "## הלו״ז השבועי עם ההמלצות",
            "",
            "ימי העבודה ושעות העבודה נשארים ללא שינוי.",
        ]
        segment_change = next(
            (
                rec
                for rec in global_recs
                if cls._action_name(rec) == "review_decrease_regular_segment"
            ),
            None,
        )
        if segment_change:
            action = cls._action(segment_change)
            lines.append(
                "הסגמנט הקבוע מומלץ להתעדכן "
                f"מ־{action.get('current_regular_segment_minutes')} "
                f"ל־{action.get('suggested_regular_segment_minutes')} דקות בכל היומן."
            )
        lines.extend(
            [
                "",
                "| יום | שעות | המלצה |",
                "| --- | --- | --- |",
            ]
        )
        for weekday, hours, recommendation in rows:
            safe_recommendation = recommendation.replace("|", "\\|").replace(
                "\n", " "
            )
            lines.append(
                f"| {weekday} | {hours} | {safe_recommendation} |"
            )
        return "\n".join(lines)

    def _text_out(self, payload):
        text = super()._text_out(payload)
        schedule_table = self._lior_v2_weekly_schedule_table(payload)
        if schedule_table:
            text = re.sub(
                r"\n*## הלו״ז השבועי עם ההמלצות.*\Z",
                "",
                text,
                flags=re.S,
            ).rstrip()
            text = f"{text}\n\n{schedule_table}"
        def round_summary(match):
            value = float(match.group(2))
            rendered = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"{match.group(1)}{rendered}"

        for prefix_pattern in (
            r"שעות עבודה שבועיות:\s*\*\*",
            r"ביקורי מטופלים בשבוע:\s*\*\*",
            r"אי־הגעה בשבוע:\s*\*\*",
            r"תחילת הביקור ביחס לשעת התור:\s*\*\*(?:באיחור של\s*)?",
        ):
            text = re.sub(
                rf"({prefix_pattern})(-?\d+(?:\.\d+)?)",
                round_summary,
                text,
            )
        text = re.sub(
            r"(\*\*[^\n]+\*\*)\n(- \*\*למה:\*\*)",
            r"\1\n\n\2",
            text,
        )
        lines = [line.rstrip() for line in text.splitlines()]
        normalized = []
        for line in lines:
            if not line and normalized and not normalized[-1]:
                continue
            normalized.append(line)
        return "\n".join(normalized).strip() + "\n"
'''


GROUNDING_PRESENTER_WRAPPER = r'''
class RecommendationPresenter(Component):
    _LIOR_GROUNDING_COUNT_LABELS = {
        "encounter_count": "ביקורים מתועדים",
        "actual_encounter_count": "ביקורים בפועל",
        "logical_appointment_count": "תורים",
        "active_date_count": "ימים שבהם הממצא הופיע",
        "weeks_with_activity": "שבועות שבהם הממצא הופיע",
        "weeks_with_confirmed_urgent_actual": "שבועות עם ביקוש דחוף מאומת",
        "confirmed_no_show_count": "אי־הגעות מאומתות",
        "combined_no_show_signal_count": "אותות אי־הגעה",
        "matched_visit_count": "ביקורים שניתנו למדידה",
        "pair_count": "זוגות ביקורים שניתנו למדידה",
        "measurable_occurrence_count": "מופעים שניתנו למדידה",
        "delay_measurement_count": "מדידות איחור",
    }

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

    @staticmethod
    def _lior_grounding_date(value):
        text = str(value or "").strip()
        match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
        if not match:
            return text
        return f"{match.group(3)}.{match.group(2)}.{match.group(1)}"

    @classmethod
    def _lior_grounding_period(cls, payload):
        context = payload.get("analysis_context") or {}
        if isinstance(context.get("value"), dict):
            context = context["value"]
        if isinstance(context, dict):
            for key in (
                "decision_period",
                "analysis_period",
                "source_analysis_period",
            ):
                period = context.get(key)
                if isinstance(period, dict) and (
                    period.get("from") or period.get("to")
                ):
                    return {
                        "from": period.get("from"),
                        "to": period.get("to"),
                        "scope": key,
                    }
        for rec in payload.get("recommendations") or []:
            if not isinstance(rec, dict):
                continue
            period = (rec.get("factual_basis") or {}).get("period")
            if isinstance(period, dict) and (
                period.get("from") or period.get("to")
            ):
                return period
        for key in ("analytics_insights", "candidate_insights"):
            for wrapped in payload.get(key) or []:
                item = cls._unwrap_insight(wrapped)
                period = (item.get("factual_basis") or {}).get("period")
                if isinstance(period, dict) and (
                    period.get("from") or period.get("to")
                ):
                    return period
        return {"from": None, "to": None, "scope": "unavailable"}

    @classmethod
    def _lior_grounding_fallback_basis(cls, item, period):
        item = item if isinstance(item, dict) else {}
        numerator = None
        numerator_field = None
        for key in (
            "support_occurrence_count",
            "active_date_count",
            "weeks_with_activity",
            "measurable_occurrence_count",
            "pair_count",
        ):
            value = cls._lior_grounding_number(item.get(key))
            if value is not None:
                numerator, numerator_field = value, key
                break
        denominator = None
        denominator_field = None
        for key in (
            "eligible_occurrence_count",
            "scheduled_eligible_occurrence_count",
            "observed_week_count",
        ):
            value = cls._lior_grounding_number(item.get(key))
            if value is not None:
                denominator, denominator_field = value, key
                break
        rate = cls._lior_grounding_number(
            item.get("support_rate")
            if item.get("support_rate") is not None
            else item.get("week_coverage_rate")
        )
        if rate is None and numerator is not None and denominator:
            rate = round(float(numerator) / float(denominator), 4)
        counts = {}
        for key in cls._LIOR_GROUNDING_COUNT_LABELS:
            value = cls._lior_grounding_number(item.get(key))
            if value is not None:
                counts[key] = value
        return {
            "contract_version": "v1",
            "complete": bool(
                period.get("from")
                and period.get("to")
                and (
                    numerator is not None
                    or counts
                    or item.get("weekday")
                    or item.get("time_from")
                )
            ),
            "period": dict(period),
            "window": {
                "weekday": item.get("weekday"),
                "time_from": item.get("time_from"),
                "time_to": item.get("time_to"),
            },
            "target_window": None,
            "support": {
                "numerator": numerator,
                "numerator_field": numerator_field,
                "denominator": denominator,
                "denominator_field": denominator_field,
                "rate": rate,
                "rate_field": "legacy_candidate_fallback",
                "required": None,
                "required_field": None,
            },
            "counts": counts,
            "attributes": {},
            "threshold_evaluation": item.get("threshold_evaluation") or {},
            "recurrence": {
                "wording_allowed": False,
                "isolated": bool(
                    numerator is not None and float(numerator) <= 1
                ),
                "tier": item.get("decision_tier"),
                "evidence_type": (
                    item.get("candidate_type") or item.get("insight_type")
                ),
            },
        }

    @classmethod
    def _lior_grounding_ensure_payload(cls, payload):
        period = cls._lior_grounding_period(payload)
        recommendations = payload.get("recommendations")
        if not isinstance(recommendations, list):
            recommendations = []
        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            candidate = cls._candidate_from_rec(rec)
            basis = rec.get("factual_basis")
            if not isinstance(basis, dict):
                basis = candidate.get("factual_basis")
            if not isinstance(basis, dict):
                basis = cls._lior_grounding_fallback_basis(candidate, period)
            rec["factual_basis"] = basis
            if isinstance(candidate, dict):
                candidate.setdefault("factual_basis", basis)
        for key in ("analytics_insights", "candidate_insights"):
            items = payload.get(key)
            if not isinstance(items, list):
                continue
            for wrapped in items:
                item = cls._unwrap_insight(wrapped)
                if not isinstance(item.get("factual_basis"), dict):
                    item["factual_basis"] = cls._lior_grounding_fallback_basis(
                        item, period
                    )
        payload["factual_basis_period"] = period

    @classmethod
    def _lior_grounding_basis_text(cls, basis):
        if not isinstance(basis, dict):
            return "בסיס הנתונים המפורט אינו זמין ולכן הממצא אינו מתואר כדפוס חוזר."
        parts = []
        period = basis.get("period") or {}
        date_from = cls._lior_grounding_date(period.get("from"))
        date_to = cls._lior_grounding_date(period.get("to"))
        if date_from and date_to:
            parts.append(f"נתונים מ־{date_from} עד {date_to}")
        elif date_from or date_to:
            parts.append(f"תקופת נתונים: {date_from or date_to}")

        window = basis.get("window") or {}
        weekday = cls._clean(window.get("weekday"))
        time_from = cls._clean(window.get("time_from"))
        time_to = cls._clean(window.get("time_to"))
        if weekday and time_from and time_to:
            parts.append(f"יום {weekday}, {time_from}–{time_to}")
        elif weekday:
            parts.append(f"יום {weekday}")
        elif time_from and time_to:
            parts.append(f"שעות {time_from}–{time_to}")

        support = basis.get("support") or {}
        numerator = cls._lior_grounding_number(support.get("numerator"))
        denominator = cls._lior_grounding_number(support.get("denominator"))
        rate = cls._lior_grounding_number(support.get("rate"))
        wording_allowed = (
            (basis.get("recurrence") or {}).get("wording_allowed") is True
        )
        if numerator is not None and denominator:
            label = "הדפוס חזר" if wording_allowed else "הממצא נצפה"
            support_text = f"{label} ב־{cls._fmt_num(numerator)} מתוך {cls._fmt_num(denominator)} מועדים רלוונטיים"
            if rate is not None:
                support_text += f" ({cls._fmt_num(float(rate) * 100)} אחוזים)"
            parts.append(support_text)
        elif numerator is not None:
            parts.append(f"נמצאו {cls._fmt_num(numerator)} מופעים")

        observed_weeks = cls._lior_grounding_number(
            period.get("observed_weeks")
        )
        if observed_weeks is not None and denominator is None:
            parts.append(f"נבדקו {cls._fmt_num(observed_weeks)} שבועות")

        counts = basis.get("counts") or {}
        count_parts = []
        used_fields = {support.get("numerator_field")}
        for key, label in cls._LIOR_GROUNDING_COUNT_LABELS.items():
            if key in used_fields:
                continue
            value = cls._lior_grounding_number(counts.get(key))
            if value is None:
                continue
            count_parts.append(f"{label}: {cls._fmt_num(value)}")
            if len(count_parts) == 2:
                break
        if count_parts:
            parts.append(", ".join(count_parts))

        attributes = basis.get("attributes") or {}
        visit_type = cls._clean(
            attributes.get("visit_type_name")
            or attributes.get("visit_type")
        )
        modality = cls._clean(attributes.get("modality"))
        if visit_type:
            parts.append(f"סוג ביקור: {visit_type}")
        if modality:
            parts.append(f"מאפיין פעילות: {modality}")
        if not parts:
            return "בסיס הנתונים המפורט אינו זמין ולכן הממצא אינו מתואר כדפוס חוזר."
        return "בסיס הנתונים: " + "; ".join(parts) + "."

    @staticmethod
    def _lior_grounding_neutralize(text, wording_allowed):
        text = str(text or "")
        if wording_allowed:
            return text
        replacements = (
            ("חלק משמעותי", "חלק מתועד"),
            ("משמעותית", "מתועדת"),
            ("משמעותי", "מתועד"),
            ("באופן עקבי", "במקרים שנבדקו"),
            ("עקבי יותר", "מסודר יותר"),
            ("עקבית", "מתועדת"),
            ("עקבי", "מתועד"),
            ("דפוס חוזר", "ממצא שנצפה"),
            ("ריכוז חוזר", "ריכוז שנצפה"),
            ("באופן חוזר", "במקרים שנצפו"),
            ("חוזרות", "שנצפו"),
            ("חוזרים", "שנצפו"),
            ("חוזרת", "שנצפתה"),
            ("חוזר", "שנצפה"),
            ("ניכרת", "נצפתה"),
            ("ניכר", "נצפה"),
        )
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    @classmethod
    def _recommendation_parts(cls, rec):
        parts = cls._lior_grounding_base_recommendation_parts(rec)
        if not parts:
            return None
        basis = rec.get("factual_basis")
        if not isinstance(basis, dict):
            basis = cls._candidate_from_rec(rec).get("factual_basis")
        wording_allowed = bool(
            isinstance(basis, dict)
            and (basis.get("recurrence") or {}).get("wording_allowed") is True
        )
        title, why, what = parts
        title = cls._lior_grounding_neutralize(title, wording_allowed)
        why = cls._lior_grounding_neutralize(why, wording_allowed)
        what = cls._lior_grounding_neutralize(what, wording_allowed)
        basis_text = cls._lior_grounding_basis_text(basis)
        return title, f"{why} {basis_text}".strip(), what

    @classmethod
    def _insight_sentence(cls, insight):
        sentence = cls._lior_grounding_base_insight_sentence(insight)
        if not sentence:
            return ""
        basis = insight.get("factual_basis")
        wording_allowed = bool(
            isinstance(basis, dict)
            and (basis.get("recurrence") or {}).get("wording_allowed") is True
        )
        sentence = cls._lior_grounding_neutralize(
            sentence, wording_allowed
        )
        return (
            f"{sentence} {cls._lior_grounding_basis_text(basis)}"
        ).strip()

    def _text_out(self, payload):
        self._lior_grounding_ensure_payload(payload)
        text = self._lior_grounding_base_text_out(payload)
        period = payload.get("factual_basis_period") or {}
        date_from = self._lior_grounding_date(period.get("from"))
        date_to = self._lior_grounding_date(period.get("to"))
        if date_from and date_to:
            period_line = (
                f"- **תקופת הנתונים:** {date_from}–{date_to}."
            )
            heading = "### תמונת מצב"
            if period_line not in text:
                if heading in text:
                    text = text.replace(
                        heading,
                        f"{heading}\n{period_line}",
                        1,
                    )
                else:
                    report_heading = "## המלצות ליומן הרופא"
                    text = text.replace(
                        report_heading,
                        f"{report_heading}\n\n{period_line}",
                        1,
                    )
        return text
'''


GROUNDING_QUALITY_PRESENTER_WRAPPER = r'''
class RecommendationPresenter(Component):
    @staticmethod
    def _lior_quality_has_hebrew(value):
        return bool(re.search(r"[\u0590-\u05ff]", str(value or "")))

    @classmethod
    def _lior_grounding_basis_text(cls, basis):
        if not isinstance(basis, dict):
            return cls._lior_quality_base_basis_text(basis)
        safe_basis = dict(basis)
        attributes = basis.get("attributes")
        if isinstance(attributes, dict):
            safe_basis["attributes"] = {
                key: value
                for key, value in attributes.items()
                if cls._lior_quality_has_hebrew(value)
            }
        return cls._lior_quality_base_basis_text(safe_basis)

    @classmethod
    def _lior_quality_basis_signature(cls, rec):
        basis = rec.get("factual_basis")
        if not isinstance(basis, dict):
            basis = cls._candidate_from_rec(rec).get("factual_basis")
        if not isinstance(basis, dict):
            return ()
        window = basis.get("window") or {}
        target = basis.get("target_window") or {}
        support = basis.get("support") or {}
        attributes = basis.get("attributes") or {}
        return (
            window.get("weekday"),
            window.get("time_from"),
            window.get("time_to"),
            target.get("weekday"),
            target.get("time_from"),
            target.get("time_to"),
            support.get("numerator"),
            support.get("denominator"),
            support.get("rate"),
            tuple(
                sorted(
                    (str(key), str(value))
                    for key, value in attributes.items()
                    if value not in (None, "")
                )
            ),
        )

    @classmethod
    def _presentation_signature(cls, rec):
        return cls._lior_quality_base_presentation_signature(rec) + (
            cls._lior_quality_basis_signature(rec),
        )

    @classmethod
    def _insight_sentence(cls, insight):
        kind = cls._clean(insight.get("insight_type"))
        if kind == "forecast_change":
            direction = cls._clean(
                insight.get("direction")
                or insight.get("forecast_direction")
                or insight.get("change_direction")
            )
            magnitude = insight.get("magnitude")
            if magnitude is None:
                magnitude = insight.get("forecast_magnitude")
            if magnitude is None:
                magnitude = insight.get("change_magnitude")
            if not direction or magnitude is None:
                return ""
        return cls._lior_quality_base_insight_sentence(insight)

    @classmethod
    def _recommendation_parts(cls, rec):
        parts = cls._lior_quality_base_recommendation_parts(rec)
        if not parts:
            return None
        title, why, what = parts
        action = cls._action(rec)
        if action.get("recommendation_mode") == "keep_current":
            what = re.sub(
                r"(- \*\*השפעה תפעולית צפויה:\*\*)[^\n]*",
                (
                    r"\1 שמירה על ההתאמה בין ההעדפה הקיימת "
                    "לביקורים שנקבעו בפועל."
                ),
                what,
            )
        return title, why, what

    def _text_out(self, payload):
        text = self._lior_quality_base_text_out(payload)
        text = re.sub(
            r"(מאפיין פעילות:)\s*\.(?=\s|$)",
            "",
            text,
        )
        text = re.sub(
            r"(\d{2}:\d{2}–\d{2}:\d{2}\s*\|[^\n]+)\n"
            r"(- \*\*למה:\*\*)",
            r"\1\n\n\2",
            text,
        )
        return text
'''


OCCURRENCE_PRESENTER_WRAPPER = r'''
class RecommendationPresenter(Component):
    @staticmethod
    def _lior_occurrence_date_parts(value):
        match = re.fullmatch(
            r"(\d{4})-(\d{2})-(\d{2})", str(value or "").strip()
        )
        return match.groups() if match else None

    @classmethod
    def _lior_occurrence_date(cls, value, include_year=False):
        parts = cls._lior_occurrence_date_parts(value)
        if not parts:
            return cls._lior_grounding_date(value)
        year, month, day = parts
        return (
            f"{day}.{month}.{year}"
            if include_year
            else f"{day}.{month}"
        )

    @classmethod
    def _lior_occurrence_date_range(cls, date_from, date_to):
        first = cls._lior_occurrence_date_parts(date_from)
        last = cls._lior_occurrence_date_parts(date_to)
        include_year = bool(first and last and first[0] != last[0])
        return (
            cls._lior_occurrence_date(date_from, include_year),
            cls._lior_occurrence_date(date_to, include_year),
        )

    @staticmethod
    def _lior_occurrence_hebrew_list(values):
        values = [str(value) for value in values if value]
        if len(values) < 2:
            return "".join(values)
        if len(values) == 2:
            return f"{values[0]} ו־{values[1]}"
        return f"{', '.join(values[:-1])} ו־{values[-1]}"

    @staticmethod
    def _lior_occurrence_neutralize_throughout(text, allowed):
        text = str(text or "")
        if allowed:
            return text
        return text.replace("לאורך התקופה", "במועדים שנצפו")

    @classmethod
    def _lior_grounding_basis_text(cls, basis):
        if not isinstance(basis, dict):
            return cls._lior_occurrence_base_basis_text(basis)
        span = basis.get("observed_pattern_span")
        if not isinstance(span, dict) or not span.get("occurrence_dates"):
            return cls._lior_occurrence_base_basis_text(basis)

        parts = []
        analysis = basis.get("analysis_window") or basis.get("period") or {}
        analysis_from, analysis_to = cls._lior_occurrence_date_range(
            analysis.get("from"), analysis.get("to")
        )
        if analysis_from and analysis_to:
            parts.append(f"חלון הניתוח: {analysis_from}–{analysis_to}")
        elif analysis_from or analysis_to:
            parts.append(f"חלון הניתוח: {analysis_from or analysis_to}")

        dates = [
            cls._lior_occurrence_date(value)
            for value in span.get("occurrence_dates") or []
        ]
        recurrence = basis.get("recurrence") or {}
        throughout_allowed = (
            recurrence.get("throughout_period_wording_allowed") is True
            and span.get("distributed_across_analysis_window") is True
        )
        if len(dates) <= 5:
            if len(dates) == 1:
                occurrence_text = f"הדפוס הופיע ב־{dates[0]}"
            else:
                occurrence_text = (
                    "הדפוס הופיע בתאריכים: "
                    f"{cls._lior_occurrence_hebrew_list(dates)}"
                )
            if throughout_allowed:
                occurrence_text = occurrence_text.replace(
                    "הדפוס הופיע", "הדפוס הופיע לאורך התקופה", 1
                )
            parts.append(occurrence_text)
        else:
            first, last = cls._lior_occurrence_date_range(
                span.get("first_occurrence_date"),
                span.get("last_occurrence_date"),
            )
            prefix = (
                "הדפוס הופיע לאורך התקופה בין"
                if throughout_allowed
                else "הדפוס הופיע בין"
            )
            parts.append(f"{prefix} {first} ל־{last}")

        window = basis.get("window") or {}
        weekday = cls._clean(window.get("weekday"))
        time_from = cls._clean(window.get("time_from"))
        time_to = cls._clean(window.get("time_to"))
        support = basis.get("support") or {}
        numerator = cls._lior_grounding_number(support.get("numerator"))
        denominator = cls._lior_grounding_number(support.get("denominator"))
        if numerator is not None and denominator:
            occurrence_label = (
                f"ימי {weekday} רלוונטיים"
                if weekday
                else "מועדים רלוונטיים"
            )
            parts.append(
                f"ב־{cls._fmt_num(numerator)} מתוך "
                f"{cls._fmt_num(denominator)} {occurrence_label}"
            )
        elif numerator is not None:
            parts.append(f"נמצאו {cls._fmt_num(numerator)} מופעים")

        if time_from and time_to:
            parts.append(f"בשעות {time_from}–{time_to}")
        elif weekday:
            parts.append(f"יום {weekday}")

        counts = basis.get("counts") or {}
        count_parts = []
        used_fields = {support.get("numerator_field")}
        for key, label in cls._LIOR_GROUNDING_COUNT_LABELS.items():
            if key in used_fields:
                continue
            value = cls._lior_grounding_number(counts.get(key))
            if value is None:
                continue
            count_parts.append(f"{label}: {cls._fmt_num(value)}")
            if len(count_parts) == 2:
                break
        if count_parts:
            parts.append(", ".join(count_parts))

        attributes = basis.get("attributes") or {}
        visit_type = cls._clean(
            attributes.get("visit_type_name")
            or attributes.get("visit_type")
        )
        modality = cls._clean(attributes.get("modality"))
        if visit_type:
            parts.append(f"סוג ביקור: {visit_type}")
        if modality:
            parts.append(f"מאפיין פעילות: {modality}")
        return "בסיס הנתונים: " + "; ".join(parts) + "."

    @classmethod
    def _lior_quality_basis_signature(cls, rec):
        base = cls._lior_occurrence_base_basis_signature(rec)
        basis = rec.get("factual_basis")
        if not isinstance(basis, dict):
            basis = cls._candidate_from_rec(rec).get("factual_basis")
        span = (
            basis.get("observed_pattern_span")
            if isinstance(basis, dict)
            else {}
        ) or {}
        return base + (
            span.get("first_occurrence_date"),
            span.get("last_occurrence_date"),
            tuple(span.get("occurrence_dates") or []),
            span.get("distributed_across_analysis_window"),
        )

    @classmethod
    def _recommendation_parts(cls, rec):
        parts = cls._lior_occurrence_base_recommendation_parts(rec)
        if not parts:
            return None
        basis = rec.get("factual_basis")
        if not isinstance(basis, dict):
            basis = cls._candidate_from_rec(rec).get("factual_basis")
        allowed = bool(
            isinstance(basis, dict)
            and (basis.get("recurrence") or {}).get(
                "throughout_period_wording_allowed"
            ) is True
        )
        return tuple(
            cls._lior_occurrence_neutralize_throughout(value, allowed)
            for value in parts
        )

    @classmethod
    def _insight_sentence(cls, insight):
        sentence = cls._lior_occurrence_base_insight_sentence(insight)
        basis = insight.get("factual_basis")
        allowed = bool(
            isinstance(basis, dict)
            and (basis.get("recurrence") or {}).get(
                "throughout_period_wording_allowed"
            ) is True
        )
        return cls._lior_occurrence_neutralize_throughout(
            sentence, allowed
        )
'''


OCCURRENCE_SAFETY_PRESENTER_WRAPPER = r'''
class RecommendationPresenter(Component):
    _LIOR_OCCURRENCE_SAFETY_V4 = True

    @classmethod
    def _lior_occurrence_dates_complete(cls, basis):
        if not isinstance(basis, dict):
            return False
        span = basis.get("observed_pattern_span")
        if not isinstance(span, dict):
            return False
        dates = span.get("occurrence_dates")
        if not isinstance(dates, list) or not dates:
            return False
        explicit = span.get("occurrence_dates_complete")
        if explicit is False:
            return False
        support = basis.get("support") or {}
        numerator = cls._lior_grounding_number(support.get("numerator"))
        reported = cls._lior_grounding_number(
            span.get("reported_active_date_count")
            if span.get("reported_active_date_count") is not None
            else span.get("active_date_count")
        )
        expected = reported if reported is not None else numerator
        return bool(expected is None or len(dates) >= int(expected))

    @classmethod
    def _lior_grounding_basis_text(cls, basis):
        if cls._lior_occurrence_dates_complete(basis):
            return cls._lior_safety_base_basis_text(basis)
        if not isinstance(basis, dict):
            return cls._lior_safety_base_basis_text(basis)
        safe_basis = dict(basis)
        safe_span = dict(basis.get("observed_pattern_span") or {})
        safe_span["occurrence_dates"] = []
        safe_span["first_occurrence_date"] = None
        safe_span["last_occurrence_date"] = None
        safe_span["distributed_across_analysis_window"] = False
        safe_span["occurrence_dates_complete"] = False
        safe_basis["observed_pattern_span"] = safe_span
        safe_recurrence = dict(basis.get("recurrence") or {})
        safe_recurrence["throughout_period_wording_allowed"] = False
        safe_basis["recurrence"] = safe_recurrence
        return cls._lior_safety_base_basis_text(safe_basis)

    @classmethod
    def _lior_quality_basis_signature(cls, rec):
        base = cls._lior_safety_base_basis_signature(rec)
        basis = rec.get("factual_basis")
        if not isinstance(basis, dict):
            basis = cls._candidate_from_rec(rec).get("factual_basis")
        return base + (cls._lior_occurrence_dates_complete(basis),)

    @classmethod
    def _recommendation_parts(cls, rec):
        parts = cls._lior_safety_base_recommendation_parts(rec)
        if not parts:
            return None
        basis = rec.get("factual_basis")
        if not isinstance(basis, dict):
            basis = cls._candidate_from_rec(rec).get("factual_basis")
        allowed = bool(
            cls._lior_occurrence_dates_complete(basis)
            and isinstance(basis, dict)
            and (basis.get("recurrence") or {}).get(
                "throughout_period_wording_allowed"
            ) is True
        )
        return tuple(
            cls._lior_occurrence_neutralize_throughout(value, allowed)
            for value in parts
        )

    @classmethod
    def _insight_sentence(cls, insight):
        sentence = cls._lior_safety_base_insight_sentence(insight)
        basis = insight.get("factual_basis")
        allowed = bool(
            cls._lior_occurrence_dates_complete(basis)
            and isinstance(basis, dict)
            and (basis.get("recurrence") or {}).get(
                "throughout_period_wording_allowed"
            ) is True
        )
        return cls._lior_occurrence_neutralize_throughout(
            sentence, allowed
        )
'''


COSMETIC_PRESENTER_WRAPPER = r'''
class RecommendationPresenter(Component):
    _LIOR_COSMETIC_PRESENTATION_V5 = True

    @classmethod
    def _lior_grounding_basis_text(cls, basis):
        if not isinstance(basis, dict):
            return cls._lior_cosmetic_base_basis_text(basis)
        safe_basis = dict(basis)
        attributes = basis.get("attributes")
        if isinstance(attributes, dict):
            safe_basis["attributes"] = {
                key: value
                for key, value in attributes.items()
                if cls._lior_quality_has_hebrew(value)
            }
        counts = basis.get("counts")
        support = basis.get("support") or {}
        if isinstance(counts, dict):
            safe_counts = dict(counts)
            active_dates = cls._lior_grounding_number(
                safe_counts.get("active_date_count")
            )
            numerator = cls._lior_grounding_number(
                support.get("numerator")
            )
            if (
                active_dates is not None
                and numerator is not None
                and active_dates == numerator
            ):
                safe_counts.pop("active_date_count", None)
            safe_basis["counts"] = safe_counts
        return cls._lior_cosmetic_base_basis_text(safe_basis)

    def _text_out(self, payload):
        text = self._lior_cosmetic_base_text_out(payload)
        text = re.sub(
            r"^\*\*(\d{2}:\d{2}–\d{2}:\d{2}\s*\|[^\n]+)\*\*$",
            r"#### \1",
            text,
            flags=re.M,
        )
        text = re.sub(
            r"^(#### [^\n]+)\n(?=- \*\*למה:\*\*)",
            r"\1\n",
            text,
            flags=re.M,
        )
        text = re.sub(r";\s*(?=\n|$)", ".", text)
        return text
'''


REQUIRED_ANALYSIS_PRESENTER_WRAPPER = r'''
class RecommendationPresenter(Component):
    _LIOR_REQUIRED_ANALYSIS_TITLES = (
        (
            "segment_duration_by_visit_type",
            "התאמת גודל הסגמנט למשך הביקור בפועל לפי סוג ביקור",
        ),
        ("no_show_by_weekday_hour", "אי־הגעה לפי יום ושעה"),
        (
            "no_show_by_modality",
            "השוואת אי־הגעה בין ביקורים פרונטליים לטלפוניים או בווידאו",
        ),
        ("reserve_utilization", "ניצול עתודות קיימות"),
    )

    @classmethod
    def _lior_required_rate(cls, value):
        try:
            return f"{cls._fmt_num(float(value) * 100.0)}%"
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _lior_required_hebrew_label(value, fallback):
        text_value = str(value or "").strip()
        return text_value if re.search(r"[א-ת]", text_value) else fallback

    @classmethod
    def _lior_required_outcome_line(cls, domain):
        if str(domain.get("status") or "") != "checked":
            return (
                "התחום נכלל בניתוח, אך לא ניתן היה להשלים את הבדיקה "
                "משום שנתוני המקור הנדרשים אינם זמינים."
            )
        if domain.get("recommendation_found") is True:
            return "התחום נבדק ונמצאה המלצה לשינוי."
        return "התחום נבדק ולא נמצאה המלצה לשינוי."

    @classmethod
    def _lior_required_segment_lines(cls, domain):
        if str(domain.get("status") or "") != "checked":
            return []
        segment = domain.get("current_regular_segment_minutes")
        rows = [
            row
            for row in (domain.get("by_visit_type") or [])
            if isinstance(row, dict)
        ]
        if not rows:
            return [
                "לא נמצאו ביקורים מותאמים עם משך ביקור בפועל שניתן למדידה."
            ]
        lines = []
        for index, row in enumerate(rows[:10], start=1):
            label = cls._lior_required_hebrew_label(
                row.get("visit_type_name"), f"סוג ביקור {index}"
            )
            details = []
            if segment is not None:
                details.append(f"גודל הסגמנט {cls._fmt_num(segment)} דקות")
            median_value = row.get("median_actual_duration_minutes")
            if median_value is not None:
                details.append(
                    f"חציון משך הביקור בפועל {cls._fmt_num(median_value)} דקות"
                )
            p75_value = row.get("p75_actual_duration_minutes")
            if p75_value is not None:
                details.append(
                    f"רבעון עליון {cls._fmt_num(p75_value)} דקות"
                )
            count = row.get("matched_visit_count")
            if count is not None:
                details.append(f"{cls._fmt_num(count)} ביקורים שנמדדו")
            lines.append(f"- {label}: {'; '.join(details)}.")
        if len(rows) > 10:
            lines.append(
                f"- מוצגים עשרת סוגי הביקור המרכזיים מתוך {cls._fmt_num(len(rows))}."
            )
        return lines

    @classmethod
    def _lior_required_no_show_time_lines(cls, domain):
        if str(domain.get("status") or "") != "checked":
            return []
        total = int(domain.get("combined_no_show_signal_count") or 0)
        lines = [f"נמצאו {cls._fmt_num(total)} אותות אי־הגעה בתקופה שנבדקה."]
        weekday_rows = [
            row
            for row in (domain.get("by_weekday") or [])
            if isinstance(row, dict)
        ]
        weekday_parts = []
        if weekday_rows:
            weekday_parts = [
                (
                    f"{cls._clean(row.get('weekday'))}: "
                    f"{cls._fmt_num(row.get('combined_no_show_signal_count') or 0)}"
                )
                for row in weekday_rows
                if cls._clean(row.get("weekday"))
            ]
            if weekday_parts:
                lines.append("")
                lines.append("לפי יום:")
                lines.append("")
                lines.extend(f"- {part}." for part in weekday_parts)
        windows = [
            row
            for row in (domain.get("by_60_minute_window") or [])
            if isinstance(row, dict)
        ]
        windows.sort(
            key=lambda row: (
                -int(row.get("combined_no_show_signal_count") or 0),
                str(row.get("weekday") or ""),
                str(row.get("time_from") or ""),
            )
        )
        if windows:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append("מוקדים בולטים:")
            lines.append("")
        for row in windows[:5]:
            weekday = cls._clean(row.get("weekday")) or "יום לא ידוע"
            time_from = cls._clean(row.get("time_from"))
            time_to = cls._clean(row.get("time_to"))
            count = int(row.get("combined_no_show_signal_count") or 0)
            rate = cls._lior_required_rate(
                row.get("combined_no_show_signal_rate_in_window")
            )
            rate_text = f", שהם {rate} מהתורים בחלון" if rate else ""
            lines.append(
                f"- {weekday}, {time_from}–{time_to}: "
                f"{cls._fmt_num(count)} אותות אי־הגעה{rate_text}."
            )
        return lines

    @classmethod
    def _lior_required_no_show_modality_lines(cls, domain):
        modalities = domain.get("modalities") or {}
        labels = (
            ("face_to_face", "ביקורים פרונטליים"),
            ("telephone_video", "ביקורי טלפון או וידאו"),
        )
        lines = []
        coverage = domain.get("classification_coverage") or {}
        classified = coverage.get("classified_appointment_count")
        total = coverage.get("total_appointment_count")
        coverage_rate = cls._lior_required_rate(coverage.get("rate"))
        required_rate = cls._lior_required_rate(
            coverage.get("minimum_required_rate")
        )
        if classified is not None and total is not None:
            coverage_text = (
                f"{cls._fmt_num(classified)} מתוך {cls._fmt_num(total)} "
                "תורים סווגו לאופן ביקור"
            )
            if coverage_rate:
                coverage_text += f" ({coverage_rate})"
            if required_rate:
                coverage_text += f"; נדרשים לפחות {required_rate}"
            lines.append(coverage_text + ".")
            lines.append("")
        for key, label in labels:
            values = modalities.get(key) or {}
            denominator = int(values.get("logical_appointment_count") or 0)
            count = int(values.get("no_show_count") or 0)
            rate = cls._lior_required_rate(values.get("no_show_rate"))
            if denominator:
                lines.append(
                    f"- {label}: {cls._fmt_num(count)} מתוך "
                    f"{cls._fmt_num(denominator)} תורים"
                    + (f" ({rate})." if rate else ".")
                )
            else:
                lines.append(f"- {label}: לא נמצאו תורים שניתנו להשוואה.")
        if lines and lines[-1] != "":
            lines.append("")
        comparison = domain.get("comparison") or {}
        difference = comparison.get("rate_difference_percentage_points")
        higher = comparison.get("higher_no_show_modality")
        if str(domain.get("status") or "") == "checked" and difference is not None:
            higher_label = {
                "face_to_face": "בביקורים הפרונטליים",
                "telephone_video": "בביקורי הטלפון או הווידאו",
                "equal": "ללא הבדל",
            }.get(higher, "")
            if higher_label == "ללא הבדל":
                lines.append("שיעור אי־ההגעה זהה בין אופני הביקור.")
            elif higher_label:
                lines.append(
                    f"שיעור אי־ההגעה גבוה יותר {higher_label} "
                    f"ב־{cls._fmt_num(difference)} נקודות אחוז."
                )
        unknown = modalities.get("unknown") or {}
        unknown_count = int(unknown.get("logical_appointment_count") or 0)
        if unknown_count:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(
                f"{cls._fmt_num(unknown_count)} תורים לא סווגו לאופן ביקור."
            )
        no_show_coverage = domain.get("no_show_classification_coverage") or {}
        total_signals = no_show_coverage.get("total_no_show_signal_count")
        excluded_pushed = no_show_coverage.get(
            "excluded_pushed_no_show_count"
        )
        eligible_signals = no_show_coverage.get(
            "eligible_no_show_signal_count"
        )
        classified_signals = no_show_coverage.get(
            "classified_no_show_signal_count"
        )
        if all(
            value is not None
            for value in (
                total_signals,
                excluded_pushed,
                eligible_signals,
                classified_signals,
            )
        ):
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(
                f"מתוך {cls._fmt_num(total_signals)} אותות אי־הגעה, "
                f"{cls._fmt_num(excluded_pushed)} אותות מתורים שנדחפו הוצאו "
                "מהשוואת אופני הביקור; "
                f"{cls._fmt_num(eligible_signals)} אותות נכללו בהשוואה, "
                f"ומהם {cls._fmt_num(classified_signals)} סווגו לאופן ביקור."
            )
        reasons = set(domain.get("comparison_unavailable_reasons") or [])
        missing_groups = []
        if "face_to_face_group_empty" in reasons:
            missing_groups.append("ביקורים פרונטליים")
        if "telephone_video_group_empty" in reasons:
            missing_groups.append("ביקורי טלפון או וידאו")
        if missing_groups:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(
                "ההשוואה לא הושלמה משום שלא נמצאו תורים בקבוצת "
                + " ובקבוצת ".join(missing_groups)
                + "."
            )
        if "classified_coverage_below_minimum" in reasons:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(
                "ההשוואה לא הושלמה משום ששיעור התורים שסווגו נמוך "
                "מהמינימום הנדרש."
            )
        if "no_show_classified_coverage_below_minimum" in reasons:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(
                "ההשוואה לא הושלמה משום ששיעור אותות אי־ההגעה שסווגו "
                "לאופן ביקור נמוך מהמינימום הנדרש."
            )
        return lines

    @classmethod
    def _lior_required_reserve_lines(cls, domain):
        if str(domain.get("status") or "") != "checked":
            return []
        reserves = [
            row
            for row in (domain.get("reserves") or [])
            if isinstance(row, dict)
        ]
        if not reserves:
            return ["לא נמצאו עתודות מוגדרות ביומן."]
        lines = []
        for row in reserves[:10]:
            weekday = cls._clean(row.get("weekday")) or "יום לא ידוע"
            time_from = cls._clean(row.get("time_from"))
            time_to = cls._clean(row.get("time_to"))
            defined = row.get("defined_segment_units")
            booked = row.get("booked_segment_units")
            matched = row.get("matched_actual_segment_units")
            utilization = cls._lior_required_rate(
                (row.get("utilization") or {}).get("value")
            )
            actualization = row.get("actualization") or {}
            actualization_rate = cls._lior_required_rate(
                actualization.get("value")
            )
            details = []
            if defined is not None and booked is not None:
                details.append(
                    f"{cls._fmt_num(booked)} מתוך "
                    f"{cls._fmt_num(defined)} יחידות עתודה הוזמנו"
                )
            if utilization:
                details.append(f"ניצול בהזמנות {utilization}")
            if matched is not None:
                details.append(
                    f"{cls._fmt_num(matched)} יחידות מומשו בביקורים בפועל"
                )
            if actualization_rate:
                details.append(f"מימוש בפועל {actualization_rate}")
            elif actualization.get("status") == "unavailable":
                details.append("נתון המימוש בפועל אינו זמין")
            lines.append(
                f"- {weekday}, {time_from}–{time_to}: {'; '.join(details)}."
            )
        if len(reserves) > 10:
            lines.append(
                f"- מוצגות עשר עתודות מתוך {cls._fmt_num(len(reserves))}."
            )
        return lines

    @classmethod
    def _lior_required_analysis_section(cls, payload):
        domains = payload.get("required_analysis_domains")
        domains = domains if isinstance(domains, dict) else {}
        detail_builders = {
            "segment_duration_by_visit_type": cls._lior_required_segment_lines,
            "no_show_by_weekday_hour": cls._lior_required_no_show_time_lines,
            "no_show_by_modality": cls._lior_required_no_show_modality_lines,
            "reserve_utilization": cls._lior_required_reserve_lines,
        }
        lines = ["### תחומי הניתוח הנדרשים", ""]
        for key, title in cls._LIOR_REQUIRED_ANALYSIS_TITLES:
            domain = domains.get(key)
            domain = domain if isinstance(domain, dict) else {}
            lines.append(f"#### {title}")
            details = detail_builders[key](domain)
            lines.extend(details)
            if details and lines[-1] != "":
                lines.append("")
            lines.append(cls._lior_required_outcome_line(domain))
            lines.append("")
        return "\n".join(lines).rstrip()

    def _text_out(self, payload):
        text_value = self._lior_required_analysis_base_text_out(payload).rstrip()
        schedule_marker = "\n## הלו״ז השבועי עם ההמלצות"
        if "### תובנות כלליות" not in text_value:
            empty_insights = (
                "### תובנות כלליות\n\n"
                "לא נמצאו תובנות כלליות נוספות להצגה."
            )
            if schedule_marker in text_value:
                text_value = text_value.replace(
                    schedule_marker,
                    f"\n\n{empty_insights}{schedule_marker}",
                    1,
                )
            else:
                text_value = f"{text_value}\n\n{empty_insights}"
        section = self._lior_required_analysis_section(payload)
        if schedule_marker in text_value:
            text_value = text_value.replace(
                schedule_marker,
                f"\n\n{section}{schedule_marker}",
                1,
            )
        else:
            text_value = f"{text_value}\n\n{section}"
        return self._remove_latin(text_value).strip() + "\n"
'''


PROMPT_ADDITION = """

LIOR RECOMMENDATION V2 — MANDATORY:
- Use resolved preference names. Explicitly classify every overlap as preserve, change, or conflict.
- At 100% preference compliance, recommend keeping the current setting; never ask to concentrate more and never impose a minimum sample threshold.
- Every urgent-reserve recommendation must state whether it overlaps an existing reserve. If it overlaps, adjust the existing reserve and do not add another one.
- Preserve defined, booked, matched-actual, and matched-urgent reserve quantities when supplied; state honestly when matching data is unavailable.
- In the same planning weekday/time window, a quantified urgent reserve owns the minutes over a pushed operational buffer even when allocation precision is quantity_within_hour. Keep the buffer only as supporting evidence and never double allocate.
- Suppress semantic duplicate insights and vague forecast_change observations without both direction and magnitude.
- State expected operational impact qualitatively. Copy numeric impact only from a verified candidate field; never calculate or invent it.
- Keep adjacent or different windows separate when they come from distinct evidence families, and name the evidence category.
"""


def _append_prompt(field: dict[str, Any], node_id: str) -> str:
    value = field.get("value")
    if not isinstance(value, str):
        raise ValueError(f"{node_id}: expected a string prompt value")
    marker = "LIOR RECOMMENDATION V2 — MANDATORY:"
    if marker not in value:
        field["value"] = value.rstrip() + PROMPT_ADDITION
    return field["value"]


def _patch_prompt_pair(
    flow: dict[str, Any], text_input_id: str, agent_id: str
) -> None:
    text_template = _node_by_id(flow, text_input_id)["data"]["node"]["template"]
    agent_template = _node_by_id(flow, agent_id)["data"]["node"]["template"]
    text_field = text_template.get("input_value")
    agent_field = agent_template.get("system_prompt")
    if isinstance(text_field, dict) and isinstance(text_field.get("value"), str):
        _append_prompt(text_field, text_input_id)
    if isinstance(agent_field, dict) and isinstance(agent_field.get("value"), str):
        _append_prompt(agent_field, agent_id)


def _hide_weekday_insights(code: str) -> str:
    """Upgrade an already-patched presenter without replacing its v2 wrapper."""

    filter_block = (
        '            if cls._clean(insight.get("weekday")):\n'
        "                continue\n"
    )
    if filter_block in code:
        return code
    anchor = "        for insight in insights:\n            sentence = "
    if code.count(anchor) != 1:
        raise ValueError(
            "Expected one presenter insight loop while hiding weekday insights"
        )
    patched = code.replace(
        anchor,
        "        for insight in insights:\n" + filter_block + "            sentence = ",
        1,
    )
    ast.parse(patched)
    return patched


def _preserve_general_forecast_insights(code: str) -> str:
    """Keep the base generic wording when a general forecast is unquantified."""

    patched = code
    branches = (
        "        if not direction or magnitude is None:\n",
        "        if not direction_he:\n",
    )
    replacement_return = (
        "            return cls._lior_v2_base_insight_sentence(insight)\n"
    )
    for branch in branches:
        replacement = branch + replacement_return
        if replacement in patched:
            continue
        anchor = branch + '            return ""\n'
        if patched.count(anchor) != 1:
            raise ValueError(
                "Expected one presenter forecast-suppression branch while preserving "
                "general insights"
            )
        patched = patched.replace(anchor, replacement, 1)
    ast.parse(patched)
    return patched


def _upgrade_weekly_schedule_table(code: str) -> str:
    """Add the interval table renderer to an existing v2 presenter."""

    patched = code
    method_names = (
        "_lior_v2_schedule_label",
        "_lior_v2_hhmm",
        "_lior_v2_weekly_schedule_table",
    )
    if not all(f"def {name}" in patched for name in method_names):
        wrapper_tree = ast.parse(PRESENTER_WRAPPER)
        wrapper_class = next(
            node
            for node in wrapper_tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "RecommendationPresenter"
        )
        wrapper_lines = PRESENTER_WRAPPER.splitlines()
        blocks = []
        for name in method_names:
            methods = [
                node
                for node in wrapper_class.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name
            ]
            if len(methods) != 1:
                raise ValueError(
                    f"Expected one weekly-table wrapper method {name}"
                )
            method = methods[0]
            start = min(
                [method.lineno]
                + [decorator.lineno for decorator in method.decorator_list]
            )
            blocks.append(
                "\n".join(wrapper_lines[start - 1 : method.end_lineno])
            )

        tree = ast.parse(patched)
        presenter_classes = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "RecommendationPresenter"
        ]
        if len(presenter_classes) != 1:
            raise ValueError(
                "Expected one presenter class while adding weekly table"
            )
        text_methods = [
            node
            for node in presenter_classes[0].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_text_out"
        ]
        if len(text_methods) != 1:
            raise ValueError(
                "Expected one presenter _text_out method while adding weekly table"
            )
        text_method = text_methods[0]
        insertion_line = min(
            [text_method.lineno]
            + [decorator.lineno for decorator in text_method.decorator_list]
        )
        lines = patched.splitlines()
        lines[insertion_line - 1 : insertion_line - 1] = [
            *("\n\n".join(blocks).splitlines()),
            "",
        ]
        patched = "\n".join(lines).rstrip() + "\n"

    call_marker = (
        "        schedule_table = "
        "self._lior_v2_weekly_schedule_table(payload)\n"
    )
    if call_marker not in patched:
        anchor = (
            "        text = self._lior_v2_base_text_out(payload)\n"
        )
        if patched.count(anchor) != 1:
            raise ValueError(
                "Expected one presenter text-output anchor while adding weekly table"
            )
        addition = (
            anchor
            + call_marker
            + "        if schedule_table:\n"
            + "            text = re.sub(\n"
            + '                r"\\n*## הלו״ז השבועי עם ההמלצות.*\\Z",\n'
            + '                "",\n'
            + "                text,\n"
            + "                flags=re.S,\n"
            + "            ).rstrip()\n"
            + '            text = f"{text}\\n\\n{schedule_table}"\n'
        )
        patched = patched.replace(anchor, addition, 1)
    ast.parse(patched)
    return patched


def patch_recommendation_v2(flow: dict[str, Any]) -> dict[str, Any]:
    """Patch Recommendation after the recovered v1 patch and return ``flow``."""

    from tools.lior_analytics_v2 import _replace_class_methods

    splitter = _node_by_id(flow, SPLITTER_NODE_ID)
    business = _node_by_id(flow, BUSINESS_NODE_ID)
    presenter = _node_by_id(flow, PRESENTER_NODE_ID)
    _set_code(splitter, _patch_required_analysis_splitter(_code(splitter)))
    business_code = _patch_original_class(
        _code(business),
        "RecommendationBusinessRuleValidator",
        '"calendar_overlap_accounting_complete"',
        "LIOR_RECOMMENDATION_V2_BUSINESS",
        BUSINESS_WRAPPER,
        {
            "_cluster_paths": "_lior_v2_base_cluster_paths",
            "validate": "_lior_v2_base_validate",
        },
        {
            "super()._cluster_paths(": "cls._lior_v2_base_cluster_paths(",
            "result = super().validate()": (
                "result = self._lior_v2_base_validate()"
            ),
        },
    )
    business_code = _patch_original_class(
        business_code,
        "RecommendationBusinessRuleValidator",
        "LIOR_RECOMMENDATION_V2_BUSINESS",
        "LIOR_RECOMMENDATION_FACTUAL_BASIS_V1",
        GROUNDING_BUSINESS_WRAPPER,
        {"validate": "_lior_grounding_base_validate"},
        {},
    )
    business_code = _patch_original_class(
        business_code,
        "RecommendationBusinessRuleValidator",
        "LIOR_RECOMMENDATION_FACTUAL_BASIS_V1",
        "LIOR_RECOMMENDATION_GROUNDING_QUALITY_V2",
        GROUNDING_QUALITY_BUSINESS_WRAPPER,
        {"_cluster_paths": "_lior_quality_base_cluster_paths"},
        {},
    )
    business_code = _patch_original_class(
        business_code,
        "RecommendationBusinessRuleValidator",
        "LIOR_RECOMMENDATION_GROUNDING_QUALITY_V2",
        "LIOR_REQUIRED_ANALYSIS_BUSINESS_V1",
        REQUIRED_ANALYSIS_BUSINESS_WRAPPER,
        {"validate": "_lior_required_analysis_base_validate"},
        {},
    )
    _set_code(business, business_code)

    presenter_code = _upgrade_weekly_schedule_table(
        _preserve_general_forecast_insights(
            _hide_weekday_insights(
                _patch_original_class(
                    _code(presenter),
                    "RecommendationPresenter",
                    "def _existing_settings_explanations",
                    "LIOR_RECOMMENDATION_V2_PRESENTER",
                    PRESENTER_WRAPPER,
                    {
                        "_recommendation_parts": "_lior_v2_base_recommendation_parts",
                        "_insight_signature": "_lior_v2_base_insight_signature",
                        "_collect_insights": "_lior_v2_base_collect_insights",
                        "_presentation_signature": "_lior_v2_base_presentation_signature",
                        "_insight_sentence": "_lior_v2_base_insight_sentence",
                        "_text_out": "_lior_v2_base_text_out",
                    },
                    {
                        "super()._recommendation_parts(rec)": (
                            "cls._lior_v2_base_recommendation_parts(rec)"
                        ),
                        "super()._presentation_signature(rec)": (
                            "cls._lior_v2_base_presentation_signature(rec)"
                        ),
                        "super()._collect_insights(payload)": (
                            "cls._lior_v2_base_collect_insights(payload)"
                        ),
                        "super()._insight_sentence(insight)": (
                            "cls._lior_v2_base_insight_sentence(insight)"
                        ),
                        "super()._text_out(payload)": (
                            "self._lior_v2_base_text_out(payload)"
                        ),
                    },
                )
            )
        )
    )
    presenter_code = _patch_original_class(
        presenter_code,
        "RecommendationPresenter",
        "LIOR_RECOMMENDATION_V2_PRESENTER",
        "LIOR_RECOMMENDATION_FACTUAL_BASIS_V1",
        GROUNDING_PRESENTER_WRAPPER,
        {
            "_recommendation_parts": "_lior_grounding_base_recommendation_parts",
            "_insight_sentence": "_lior_grounding_base_insight_sentence",
            "_text_out": "_lior_grounding_base_text_out",
        },
        {},
    )
    presenter_code = _patch_original_class(
        presenter_code,
        "RecommendationPresenter",
        "LIOR_RECOMMENDATION_FACTUAL_BASIS_V1",
        "LIOR_RECOMMENDATION_GROUNDING_QUALITY_V2",
        GROUNDING_QUALITY_PRESENTER_WRAPPER,
        {
            "_lior_grounding_basis_text": "_lior_quality_base_basis_text",
            "_presentation_signature": "_lior_quality_base_presentation_signature",
            "_insight_sentence": "_lior_quality_base_insight_sentence",
            "_recommendation_parts": "_lior_quality_base_recommendation_parts",
            "_text_out": "_lior_quality_base_text_out",
        },
        {},
    )
    presenter_code = _patch_original_class(
        presenter_code,
        "RecommendationPresenter",
        "LIOR_RECOMMENDATION_GROUNDING_QUALITY_V2",
        "LIOR_RECOMMENDATION_OCCURRENCE_GROUNDING_V3",
        OCCURRENCE_PRESENTER_WRAPPER,
        {
            "_lior_grounding_basis_text": "_lior_occurrence_base_basis_text",
            "_lior_quality_basis_signature": "_lior_occurrence_base_basis_signature",
            "_recommendation_parts": "_lior_occurrence_base_recommendation_parts",
            "_insight_sentence": "_lior_occurrence_base_insight_sentence",
        },
        {},
    )
    presenter_code = _patch_original_class(
        presenter_code,
        "RecommendationPresenter",
        "LIOR_RECOMMENDATION_OCCURRENCE_GROUNDING_V3",
        "LIOR_RECOMMENDATION_OCCURRENCE_SAFETY_V4",
        OCCURRENCE_SAFETY_PRESENTER_WRAPPER,
        {
            "_lior_grounding_basis_text": "_lior_safety_base_basis_text",
            "_lior_quality_basis_signature": "_lior_safety_base_basis_signature",
            "_recommendation_parts": "_lior_safety_base_recommendation_parts",
            "_insight_sentence": "_lior_safety_base_insight_sentence",
        },
        {},
    )
    presenter_code = _patch_original_class(
        presenter_code,
        "RecommendationPresenter",
        "LIOR_RECOMMENDATION_OCCURRENCE_SAFETY_V4",
        "LIOR_RECOMMENDATION_COSMETIC_PRESENTATION_V5",
        COSMETIC_PRESENTER_WRAPPER,
        {
            "_lior_grounding_basis_text": "_lior_cosmetic_base_basis_text",
            "_text_out": "_lior_cosmetic_base_text_out",
        },
        {},
    )
    presenter_code = _patch_original_class(
        presenter_code,
        "RecommendationPresenter",
        "LIOR_RECOMMENDATION_COSMETIC_PRESENTATION_V5",
        "LIOR_REQUIRED_ANALYSIS_PRESENTER_V1",
        REQUIRED_ANALYSIS_PRESENTER_WRAPPER,
        {"_text_out": "_lior_required_analysis_base_text_out"},
        {},
    )
    presenter_code = _replace_class_methods(
        presenter_code,
        "RecommendationPresenter",
        REQUIRED_ANALYSIS_PRESENTER_WRAPPER,
        (
            "_lior_required_no_show_time_lines",
            "_lior_required_no_show_modality_lines",
        ),
        "LIOR_REQUIRED_ANALYSIS_PRESENTATION_V2_ACTIVE",
        {},
    )
    presenter_code = _replace_class_methods(
        presenter_code,
        "RecommendationPresenter",
        REQUIRED_ANALYSIS_PRESENTER_WRAPPER,
        (
            "_lior_required_no_show_time_lines",
            "_lior_required_no_show_modality_lines",
            "_lior_required_analysis_section",
            "_text_out",
        ),
        "LIOR_REQUIRED_ANALYSIS_RENDERING_V3_ACTIVE",
        {},
    )
    _set_code(presenter, presenter_code)
    for text_input_id, agent_id in PROMPT_AGENT_PAIRS.items():
        _patch_prompt_pair(flow, text_input_id, agent_id)

    for node in flow["data"]["nodes"]:
        template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
        code = template.get("code")
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            ast.parse(code["value"])
    return flow


def upgrade_recommendation_v2_return_types(
    flow: dict[str, Any],
) -> dict[str, Any]:
    """Restore the Langflow 1.9.2 Data connector on the validator output."""

    from tools.lior_analytics_v2 import _replace_class_methods

    business = _node_by_id(flow, BUSINESS_NODE_ID)
    _set_code(
        business,
        _replace_class_methods(
            _code(business),
            "RecommendationBusinessRuleValidator",
            REQUIRED_ANALYSIS_BUSINESS_WRAPPER,
            ("validate",),
            "LIOR_REQUIRED_ANALYSIS_RETURN_TYPE_V2_ACTIVE",
            {},
        ),
    )
    return flow


__all__ = [
    "patch_recommendation_v2",
    "upgrade_recommendation_v2_return_types",
]
