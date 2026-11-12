"""Assess reviewer-authored synthetic records; supplied labels never drive a verdict."""
import json
from pathlib import Path
import sys

from .monitor import assess, finite_number
from .scenarios import Scenario

STATUSES = {"NO_ISSUE_DETECTED", "ALERT", "INSUFFICIENT_EVIDENCE"}
REQUIRED = {"format_version", "name", "initial_load_mw", "proposed_load_mw", "identity_fixture",
            "measurement_age_seconds", "topology_version", "voltages_pu"}


def validate_case(body):
    if not isinstance(body, dict) or set(body) - REQUIRED - {"expected_status"} or REQUIRED - set(body):
        raise ValueError("Use exactly the case template's required fields and optional expected_status.")
    if type(body["format_version"]) is not int or body["format_version"] != 1:
        raise ValueError("format_version must be 1.")
    if not isinstance(body["name"], str) or not 1 <= len(body["name"].strip()) <= 80:
        raise ValueError("name must contain 1 to 80 characters.")
    for name in ("initial_load_mw", "proposed_load_mw"):
        if not finite_number(body[name]) or not 0 <= body[name] <= 15:
            raise ValueError(f"{name} must be a finite number from 0 to 15 MW.")
    actor = body["identity_fixture"]
    if not isinstance(actor, str) or actor not in {"operator", "viewer", "unknown"}:
        raise ValueError("identity_fixture must be operator, viewer, or unknown. These are lab fixtures, not authenticated identities.")
    age = body["measurement_age_seconds"]
    if not finite_number(age) or not -3600 <= age <= 86400:
        raise ValueError("measurement_age_seconds must be finite and between -3600 and 86400.")
    topology = body["topology_version"]
    if not isinstance(topology, str) or topology not in {"demo-v1", "demo-v0"}:
        raise ValueError("topology_version must be demo-v1 or demo-v0.")
    voltages = body["voltages_pu"]
    if not isinstance(voltages, list) or len(voltages) != 6:
        raise ValueError("voltages_pu must have six entries in bus order, each a number or null.")
    if any(v is not None and (not finite_number(v) or not 0 <= v <= 2) for v in voltages):
        raise ValueError("Each voltage must be null or a finite number from 0 to 2 pu.")
    if "expected_status" in body and (not isinstance(body["expected_status"], str) or body["expected_status"] not in STATUSES):
        raise ValueError("expected_status must be one of the three documented outcome labels.")
    return {**body, "name": body["name"].strip(), "voltages_pu": list(voltages)}


def replay_case(body):
    case = validate_case(body)
    scenario = Scenario("replay", case["name"], "Reviewer-supplied synthetic replay", "Imported case", None,
                        target_mw=case["proposed_load_mw"], initial_mw=case["initial_load_mw"],
                        actor=case["identity_fixture"], age_seconds=case["measurement_age_seconds"],
                        topology_version=case["topology_version"])
    result = assess(scenario, observed_voltages=case["voltages_pu"])
    result["input_source"] = "reviewer-supplied synthetic replay"
    result["telemetry"]["source"] = "untrusted synthetic replay file"
    result["replay_case"] = case
    expected = case.get("expected_status")
    result["expected_match"] = result["status"] == expected if expected is not None else None
    return result


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m gridshield.replay <case.json>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    try:
        if path.stat().st_size > 4096:
            raise ValueError("Case exceeds 4096 bytes.")
        result = replay_case(json.loads(path.read_text()))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
