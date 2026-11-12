"""Deterministic observation only. The proposed command is never executed."""
from dataclasses import asdict
import math
import time
from uuid import uuid4
from datetime import datetime, timezone

from . import model
from . import __version__

SCOPE = "Synthetic steady-state model. No real equipment connected. Findings are not a safety certification."
ACTORS = {"operator": {"set_load_mw"}, "viewer": set()}


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def permission_findings(scenario):
    findings = []
    def add(code, detail):
        findings.append({"code": code, "level": "alert", "detail": detail})
    if scenario.actor not in ACTORS:
        add("UNKNOWN_ACTOR", "The simulated identity is not in the lab operator registry.")
    elif scenario.action not in ACTORS[scenario.actor]:
        add("ACTION_NOT_PERMITTED", "The lab registry does not permit this identity to request this operation.")
    if scenario.device != "industry":
        add("UNKNOWN_DEVICE", "The request names equipment outside the supported synthetic load interface.")
    if scenario.action != "set_load_mw":
        add("UNSUPPORTED_ACTION", "Only a proposed industry load change can be assessed.")
    if not finite_number(scenario.target_mw) or not 0 <= scenario.target_mw <= 15:
        add("INVALID_VALUE", "Requested demand must be a finite number from 0 to 15 MW.")
    return findings


def simple_status(scenario):
    """Deliberately limited baseline: identity, action, device, numeric envelope only."""
    return "ALERT" if permission_findings(scenario) else "NO_ISSUE_DETECTED"


def assess(scenario, solver=None, observed_voltages=None):
    started = time.perf_counter()
    solver = solver or model.solve
    reasons = permission_findings(scenario)
    baseline, predicted = None, None
    evidence_ok = True
    telemetry = {"age_seconds": scenario.age_seconds, "topology_version": scenario.topology_version,
                 "measurements": [], "quality": "not_assessed", "source": "synthetic lab fixtures"}

    def unknown(code, detail):
        nonlocal evidence_ok
        evidence_ok = False
        reasons.append({"code": code, "level": "unknown", "detail": detail})

    try:
        baseline = solver(scenario.initial_mw, scenario.disconnected)
    except Exception:
        unknown("MODEL_UNAVAILABLE", "A complete baseline power-flow result is unavailable; no physical assessment is made.")
    if not finite_number(scenario.age_seconds):
        unknown("INVALID_TIME", "Measurement freshness cannot be established.")
    elif scenario.age_seconds > model.POLICY["max_age_seconds"]:
        unknown("STALE_DATA", "Measurements exceed the illustrative five-second freshness limit.")
    elif scenario.age_seconds < -model.POLICY["future_tolerance_seconds"]:
        unknown("CLOCK_INCONSISTENCY", "Measurements appear to come from the future.")
    if scenario.topology_version != model.POLICY["topology_version"]:
        unknown("TOPOLOGY_MISMATCH", "The reported network topology does not match this model.")
    if baseline:
        for bus in baseline["buses"]:
            expected = bus["voltage_pu"]
            observed = expected + (0.002 * (-1 if bus["id"] % 2 else 1) if scenario.noisy else 0)
            if observed_voltages is not None:
                observed = observed_voltages[bus["id"]]
            elif bus["id"] == 4:
                observed = None if scenario.missing else observed + scenario.voltage_offset
            residual = abs(observed - expected) if finite_number(observed) else None
            telemetry["measurements"].append({"bus": bus["name"], "observed_pu": observed,
                                              "model_pu": expected, "residual_pu": residual})
            if residual is None:
                unknown("MISSING_DATA", f"{bus['name']} has no finite voltage measurement.")
            elif residual > model.POLICY["voltage_residual_max_pu"]:
                unknown("INCONSISTENT_DATA", f"{bus['name']} differs from the model by {residual:.3f} pu. A sensor or model issue is possible.")
    telemetry["quality"] = "sufficient_for_lab" if evidence_ok else "insufficient"
    if evidence_ok and not any(r["level"] == "alert" for r in reasons):
        try:
            predicted = solver(scenario.target_mw, False)
        except Exception:
            unknown("PREDICTION_UNAVAILABLE", "The proposed-state solver failed; no normal verdict can be issued.")
        if predicted:
            for line in predicted["lines"]:
                if line["loading_percent"] > model.POLICY["line_loading_max_percent"]:
                    reasons.append({"code": "LINE_OVERLOAD", "level": "alert", "detail":
                                    f"{line['name']} reaches {line['loading_percent']:.1f}% of its illustrative current rating."})
            for bus in predicted["buses"]:
                if not model.POLICY["voltage_min_pu"] <= bus["voltage_pu"] <= model.POLICY["voltage_max_pu"]:
                    reasons.append({"code": "VOLTAGE_LIMIT", "level": "alert", "detail":
                                    f"{bus['name']} reaches {bus['voltage_pu']:.3f} pu, outside the lab's 0.95–1.05 pu band."})
    if any(r["level"] == "alert" for r in reasons):
        status = "ALERT"
    elif not evidence_ok:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "NO_ISSUE_DETECTED"
        reasons.append({"code": "CHECKS_CLEAR", "level": "info", "detail":
                        "The proposed state stays within this model's configured limits. This does not establish real-world safety."})
    return {
        "id": str(uuid4()), "scenario_id": scenario.id, "title": scenario.title,
        "app_version": __version__, "created_at": datetime.now(timezone.utc).isoformat(),
        "input_source": "built-in synthetic scenario", "source_hash": model.SOURCE_FINGERPRINT,
        "status": status, "reasons": reasons, "baseline": baseline, "predicted": predicted,
        "command": {"actor": scenario.actor, "device": scenario.device, "action": scenario.action,
                    "value_mw": scenario.target_mw},
        "telemetry": telemetry, "simple_status": simple_status(scenario), "scope": SCOPE,
        "policy_hash": model.POLICY_HASH, "model_hash": model.MODEL_HASH,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "fixture": asdict(scenario), "equipment_actions": 0,
    }
