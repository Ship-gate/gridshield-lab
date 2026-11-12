from dataclasses import replace
import json
import math

import pytest

from gridshield import model
from gridshield.monitor import assess
from gridshield.scenarios import BY_ID, benchmark_cases
from gridshield.server import evaluate_request


@pytest.mark.parametrize("case", benchmark_cases(), ids=lambda s: s.id)
def test_declared_cases(case):
    result = assess(case)
    assert result["status"] == case.expected
    assert result["equipment_actions"] == 0
    assert len(result["model_hash"]) == len(result["policy_hash"]) == 64
    if result["status"] == "NO_ISSUE_DETECTED":
        assert result["predicted"] is not None
        assert result["telemetry"]["quality"] == "sufficient_for_lab"
    json.dumps(result, allow_nan=False)


def test_authorized_change_can_still_overload_network():
    result = assess(BY_ID["overload"])
    assert result["simple_status"] == "NO_ISSUE_DETECTED"
    assert result["status"] == "ALERT"
    assert result["predicted"]["max_loading_percent"] > 100
    assert any(r["code"] == "LINE_OVERLOAD" for r in result["reasons"])


def test_recovery_assesses_proposed_state_not_just_existing_alarm():
    result = assess(BY_ID["recovery"])
    assert result["baseline"]["max_loading_percent"] > 100
    assert result["predicted"]["max_loading_percent"] < 100
    assert result["status"] == "NO_ISSUE_DETECTED"


def test_physical_conservation_and_voltage_drop():
    result = model.solve()
    assert math.isclose(result["source_mw"], result["demand_mw"] + result["losses_mw"], abs_tol=1e-7)
    assert result["losses_mw"] > 0
    assert result["buses"][4]["voltage_pu"] < result["buses"][0]["voltage_pu"]
    assert model.solve(2)["max_loading_percent"] > result["max_loading_percent"]


def test_assessments_do_not_mutate_the_baseline():
    before = model.solve()
    assess(BY_ID["overload"])
    assert model.solve() == before


@pytest.mark.parametrize("id", ["stale", "missing", "conflicting", "future", "topology", "unknown_actor", "viewer"])
def test_ineligible_evidence_or_identity_prevents_prediction(id):
    calls = []
    def solver(*args):
        calls.append(args)
        return model.solve(*args)
    result = assess(BY_ID[id], solver=solver)
    assert result["predicted"] is None
    assert len(calls) == 1


@pytest.mark.parametrize("fail_at", [1, 2])
def test_solver_failures_never_look_normal(fail_at):
    calls = 0
    def solver(*args):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            raise model.ModelUnavailable("deliberate test failure")
        return model.solve(*args)
    result = assess(BY_ID["routine"], solver=solver)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["predicted"] is None


def test_denied_identity_stays_an_alert_even_when_data_missing():
    result = assess(replace(BY_ID["unknown_actor"], missing=True))
    assert result["status"] == "ALERT"
    assert {r["code"] for r in result["reasons"]} >= {"UNKNOWN_ACTOR", "MISSING_DATA"}


@pytest.mark.parametrize("age,expected", [(5,"NO_ISSUE_DETECTED"),(5.001,"INSUFFICIENT_EVIDENCE"),(-.5,"NO_ISSUE_DETECTED"),(-.501,"INSUFFICIENT_EVIDENCE")])
def test_freshness_boundaries(age, expected):
    assert assess(replace(BY_ID["routine"], age_seconds=age))["status"] == expected


@pytest.mark.parametrize("value", [True, False, "3", None, [], {}, float("nan"), float("inf"), -1, 15.001])
def test_bad_custom_values_rejected(value):
    with pytest.raises(ValueError):
        evaluate_request({"scenario_id":"custom", "load_mw":value})


@pytest.mark.parametrize("body", [None, [], {}, {"scenario_id":[]}, {"scenario_id":"missing-id"},
    {"scenario_id":"routine", "authorized":True}, {"scenario_id":"routine", "actor":"operator"},
    {"scenario_id":"routine", "load_mw":10}])
def test_request_cannot_supply_authority_or_override_fixed_cases(body):
    with pytest.raises(ValueError):
        evaluate_request(body)


def test_zero_load_is_valid_and_data_remains_serializable():
    result = evaluate_request({"scenario_id":"custom", "load_mw":0})
    assert result["status"] == "NO_ISSUE_DETECTED"
    json.dumps(result, allow_nan=False)


def test_truthpack_matches_policy_and_response():
    truth = json.loads((model.ROOT / ".vibecheck/truthpack/contracts.json").read_text())
    assert truth["policy"] == model.POLICY
    result = assess(BY_ID["routine"])
    assert set(truth["evaluate"]["response_fields"]) <= result.keys()
    assert result["status"] in truth["statuses"]
