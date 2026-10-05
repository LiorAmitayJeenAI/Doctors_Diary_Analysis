#!/usr/bin/env python3
"""Deploy the weekly-hours fix to the live analytics Calendar Context & Baseline."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools.schedule_weekly_hours import patch_baseline_source


BASE_URL = "https://langflow.dev.jeenai.app/api/v1"
FLOW_ID = "cab826db-8f2e-49d7-aedf-346da2ca875d"
BASELINE_NODE_ID = "calendar_context_baseline-mSs0K"
FEATURE_NODE_ID = "analytics_feature_builder-CSzAL"


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
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {path} failed with HTTP {error.code}: {detail[:500]}"
        ) from error


def _code(flow: dict[str, Any], node_id: str) -> str:
    matches = [node for node in flow["data"]["nodes"] if node.get("id") == node_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one node {node_id}, found {len(matches)}")
    return matches[0]["data"]["node"]["template"]["code"]["value"]


def _set_code(flow: dict[str, Any], node_id: str, code: str) -> None:
    matches = [node for node in flow["data"]["nodes"] if node.get("id") == node_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one node {node_id}, found {len(matches)}")
    matches[0]["data"]["node"]["template"]["code"]["value"] = code


def _normalize(flow: dict[str, Any]) -> None:
    for node in flow["data"]["nodes"]:
        template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
        code = template.get("code")
        if isinstance(code, dict) and isinstance(code.get("value"), str):
            code["value"] = code["value"].replace("\r\n", "\n")


def _hash(data: Any) -> str:
    encoded = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _display_name(flow: dict[str, Any], node_id: str) -> str:
    node = next(node for node in flow["data"]["nodes"] if node.get("id") == node_id)
    data = node.get("data") or {}
    definition = data.get("node") or {}
    return str(data.get("display_name") or definition.get("display_name") or node_id)


def _assert_number_preserves_none(feature_code: str) -> None:
    start = feature_code.find("def _number(")
    if start < 0:
        raise ValueError("Feature builder is missing _number")
    body = feature_code[start:feature_code.find("\n    def ", start + 1)]
    if "if value is None:" not in body or "return None" not in body:
        raise ValueError("Feature builder _number does not preserve None")


def main() -> None:
    env_file = Path(__file__).resolve().parents[1] / "langflow.env"
    _load_env(env_file)
    api_key = os.environ.get("LANGFLOW_API_KEY")
    if not api_key:
        raise SystemExit("LANGFLOW_API_KEY is missing")

    current = _request(api_key, "GET", f"/flows/{FLOW_ID}")
    _normalize(current)
    patched = deepcopy(current)
    baseline_code = patch_baseline_source(_code(patched, BASELINE_NODE_ID))
    ast.parse(baseline_code)
    _set_code(patched, BASELINE_NODE_ID, baseline_code)
    _assert_number_preserves_none(_code(patched, FEATURE_NODE_ID))

    before_nodes = {node["id"]: node for node in current["data"]["nodes"]}
    changed = [
        node["id"]
        for node in patched["data"]["nodes"]
        if before_nodes.get(node["id"]) != node
    ]
    if not changed:
        print(json.dumps({"status": "already_current", "workflow": current.get("name")}, indent=2))
        return
    if changed != [BASELINE_NODE_ID]:
        raise RuntimeError(f"Patch would change unexpected nodes: {changed}")
    if current["data"]["edges"] != patched["data"]["edges"]:
        raise RuntimeError("Patch changed workflow edges")

    latest = _request(api_key, "GET", f"/flows/{FLOW_ID}")
    _normalize(latest)
    if _hash(latest["data"]) != _hash(current["data"]):
        raise RuntimeError("analytics changed after the initial fetch; aborting")

    expected_hash = _hash(patched["data"])
    _request(api_key, "PATCH", f"/flows/{FLOW_ID}", {"data": patched["data"]})
    fresh = _request(api_key, "GET", f"/flows/{FLOW_ID}")
    _normalize(fresh)
    actual_hash = _hash(fresh["data"])
    if actual_hash != expected_hash:
        raise RuntimeError("analytics verification hash mismatch after PATCH")
    if "return parse_schedule_time(value)" not in _code(fresh, BASELINE_NODE_ID):
        raise RuntimeError("Deployed baseline is missing the schedule clock parser")

    print(
        json.dumps(
            {
                "status": "updated_and_verified",
                "workflow": fresh.get("name"),
                "flow_id": FLOW_ID,
                "components": [
                    {
                        "id": BASELINE_NODE_ID,
                        "display_name": _display_name(fresh, BASELINE_NODE_ID),
                    }
                ],
                "feature_builder_number_preserves_none": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
