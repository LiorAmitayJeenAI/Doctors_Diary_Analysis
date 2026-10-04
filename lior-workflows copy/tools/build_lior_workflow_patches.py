#!/usr/bin/env python3
"""Build offline PATCH bodies for the Lior Analytics and Recommendation flows."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools.apply_existing_calendar_settings_ticket import (
    patch_analytics,
    patch_recommendation,
)
from tools.lior_analytics_v2 import (
    patch_analytics_v2,
    upgrade_analytics_v2_nullsafe,
    upgrade_analytics_v2_return_types,
)
from tools.lior_recommendation_v2 import (
    patch_recommendation_v2,
    upgrade_recommendation_v2_return_types,
)


def _node(flow: dict[str, Any], node_id: str) -> dict[str, Any]:
    matches = [item for item in flow["data"]["nodes"] if item.get("id") == node_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one node {node_id}, found {len(matches)}")
    return matches[0]


def _code(flow: dict[str, Any], node_id: str) -> str:
    return _node(flow, node_id)["data"]["node"]["template"]["code"]["value"]


def _normalize_embedded_code(flow: dict[str, Any]) -> None:
    for node in flow["data"]["nodes"]:
        template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
        code = template.get("code")
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            code["value"] = code["value"].replace("\r\n", "\n")


def _ensure_v1_analytics(flow: dict[str, Any]) -> None:
    markers = (
        "existing_calendar_settings" in _code(flow, "decision_kpi_analyzer-IBs8T"),
        "existing_settings_context" in _code(flow, "analytics_feature_builder-f0hrQ"),
    )
    if all(markers):
        return
    if any(markers):
        raise ValueError("Analytics has a partial v1 settings patch; refusing to guess")
    patch_analytics(flow)


def _ensure_v1_recommendation(flow: dict[str, Any]) -> None:
    markers = (
        "existing_calendar_settings"
        in _code(flow, "recommendation_context_splitter-dU9xQ"),
        "calendar_overlap_accounting_complete"
        in _code(flow, "recommendation_business_rule_validator-TvYcq"),
        "def _existing_settings_explanations"
        in _code(flow, "recommendation_presenter-TuUXM"),
    )
    if all(markers):
        return
    if any(markers):
        raise ValueError("Recommendation has a partial v1 settings patch; refusing to guess")
    patch_recommendation(flow)


def _verify(before: dict[str, Any], after: dict[str, Any]) -> None:
    before_nodes = {node["id"] for node in before["data"]["nodes"]}
    after_nodes = {node["id"] for node in after["data"]["nodes"]}
    if before_nodes != after_nodes or before["data"]["edges"] != after["data"]["edges"]:
        raise ValueError("Patch changed workflow topology")
    for node in after["data"]["nodes"]:
        template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
        code = template.get("code")
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            ast.parse(code["value"])


def _hash(data: Any) -> str:
    encoded = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _changed_nodes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    old = {node["id"]: node for node in before["data"]["nodes"]}
    return sorted(
        node["id"]
        for node in after["data"]["nodes"]
        if old.get(node["id"]) != node
    )


def build(
    analytics_source: Path,
    recommendation_source: Path,
    output_dir: Path,
) -> dict[str, Any]:
    analytics = json.loads(analytics_source.read_text())
    recommendation = json.loads(recommendation_source.read_text())
    analytics_before = deepcopy(analytics)
    recommendation_before = deepcopy(recommendation)

    _normalize_embedded_code(analytics)
    _normalize_embedded_code(recommendation)
    _normalize_embedded_code(analytics_before)
    _normalize_embedded_code(recommendation_before)

    _ensure_v1_analytics(analytics)
    _ensure_v1_recommendation(recommendation)
    patch_analytics_v2(analytics)
    upgrade_analytics_v2_nullsafe(analytics)
    upgrade_analytics_v2_return_types(analytics)
    patch_recommendation_v2(recommendation)
    upgrade_recommendation_v2_return_types(recommendation)
    _verify(analytics_before, analytics)
    _verify(recommendation_before, recommendation)

    output_dir.mkdir(parents=True, exist_ok=True)
    analytics_patch = output_dir / "analytics.patch.json"
    recommendation_patch = output_dir / "recommendation.patch.json"
    manifest_path = output_dir / "manifest.json"
    analytics_patch.write_text(
        json.dumps({"data": analytics["data"]}, ensure_ascii=False)
    )
    recommendation_patch.write_text(
        json.dumps({"data": recommendation["data"]}, ensure_ascii=False)
    )
    manifest = {
        "offline_only": True,
        "analytics": {
            "flow_id": analytics.get("id"),
            "source_sha256": _hash(analytics_before),
            "patched_sha256": _hash(analytics),
            "changed_components": _changed_nodes(analytics_before, analytics),
            "patch_file": analytics_patch.name,
        },
        "recommendation": {
            "flow_id": recommendation.get("id"),
            "source_sha256": _hash(recommendation_before),
            "patched_sha256": _hash(recommendation),
            "changed_components": _changed_nodes(
                recommendation_before, recommendation
            ),
            "patch_file": recommendation_patch.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analytics-in", type=Path, required=True)
    parser.add_argument("--recommendation-in", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args.analytics_in, args.recommendation_in, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
