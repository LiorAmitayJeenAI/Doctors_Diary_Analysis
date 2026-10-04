#!/usr/bin/env python3
"""Fetch, patch, and verify the two live Lior Langflow workflows."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools.build_lior_workflow_patches import (
    _changed_nodes,
    _ensure_v1_analytics,
    _ensure_v1_recommendation,
    _hash,
    _normalize_embedded_code,
    _verify,
)
from tools.lior_analytics_v2 import (
    remove_analytics_v2_diagnostic,
    patch_analytics_v2,
    upgrade_analytics_v2_nullsafe,
    upgrade_analytics_v2_return_types,
)
from tools.lior_recommendation_v2 import (
    patch_recommendation_v2,
    upgrade_recommendation_v2_return_types,
)


BASE_URL = "https://langflow.dev.jeenai.app/api/v1"
FLOWS = {
    "analytics": "db3bfc7e-572b-4388-9642-1716f094a066",
    "recommendation": "e8e69eb0-6607-4bec-8117-386cb861900e",
}
ALLOWED_CHANGED_NODES = {
    "analytics": {
        "decision_kpi_analyzer-IBs8T",
        "analytics_feature_builder-f0hrQ",
        "urgent_reserve_pressure_analyzer-m0uiz",
    },
    "recommendation": {
        "recommendation_context_splitter-dU9xQ",
        "recommendation_business_rule_validator-TvYcq",
        "recommendation_presenter-TuUXM",
    },
}


def _load_env(path: Path) -> None:
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _request(api_key: str, method: str, path: str, payload=None) -> Any:
    body = None
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{BASE_URL}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {error.code}: {detail}") from error


def _display_name(node: dict[str, Any]) -> str:
    data = node.get("data") or {}
    definition = data.get("node") or {}
    return str(data.get("display_name") or definition.get("display_name") or node["id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    _load_env(args.env_file)
    api_key = os.environ.get("LANGFLOW_API_KEY")
    if not api_key:
        raise SystemExit("LANGFLOW_API_KEY is missing")

    current = {
        name: _request(api_key, "GET", f"/flows/{flow_id}")
        for name, flow_id in FLOWS.items()
    }
    patched = deepcopy(current)
    for flow in patched.values():
        _normalize_embedded_code(flow)
    normalized_current = deepcopy(current)
    for flow in normalized_current.values():
        _normalize_embedded_code(flow)

    _ensure_v1_analytics(patched["analytics"])
    patch_analytics_v2(patched["analytics"])
    upgrade_analytics_v2_nullsafe(patched["analytics"])
    upgrade_analytics_v2_return_types(patched["analytics"])
    remove_analytics_v2_diagnostic(patched["analytics"])
    _ensure_v1_recommendation(patched["recommendation"])
    patch_recommendation_v2(patched["recommendation"])
    upgrade_recommendation_v2_return_types(patched["recommendation"])

    for name in FLOWS:
        _verify(normalized_current[name], patched[name])

    changed = {
        name: _changed_nodes(normalized_current[name], patched[name])
        for name in FLOWS
    }
    for name, node_ids in changed.items():
        unexpected = set(node_ids) - ALLOWED_CHANGED_NODES[name]
        if unexpected:
            raise RuntimeError(
                f"{name} patch would change out-of-scope nodes: "
                f"{sorted(unexpected)}"
            )
    if not any(changed.values()):
        print(json.dumps({"status": "already_current", "changed": changed}, indent=2))
        return

    deployed = {}
    for name, flow_id in FLOWS.items():
        if not changed[name]:
            deployed[name] = {"status": "already_current", "components": []}
            continue
        latest = _request(api_key, "GET", f"/flows/{flow_id}")
        _normalize_embedded_code(latest)
        if _hash(latest["data"]) != _hash(normalized_current[name]["data"]):
            raise RuntimeError(
                f"{name} changed after the initial fetch; aborting before PATCH"
            )
        expected_data_hash = _hash(patched[name]["data"])
        _request(
            api_key,
            "PATCH",
            f"/flows/{flow_id}",
            {"data": patched[name]["data"]},
        )
        fresh = _request(api_key, "GET", f"/flows/{flow_id}")
        _normalize_embedded_code(fresh)
        actual_data_hash = _hash(fresh["data"])
        if actual_data_hash != expected_data_hash:
            raise RuntimeError(f"{name} verification hash mismatch after PATCH")
        by_id = {node["id"]: node for node in fresh["data"]["nodes"]}
        deployed[name] = {
            "status": "updated_and_verified",
            "components": [
                {"id": node_id, "display_name": _display_name(by_id[node_id])}
                for node_id in changed[name]
            ],
        }
    print(json.dumps(deployed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
