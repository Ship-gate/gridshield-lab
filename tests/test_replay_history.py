from copy import deepcopy
import json
import sqlite3

import pytest

from gridshield.history import RunStore
from gridshield.model import solve, SOURCE_FINGERPRINT
from gridshield.replay import replay_case, validate_case


@pytest.fixture(scope="module")
def sample():
    return {"format_version": 1, "name": "Independent reviewer fixture", "initial_load_mw": .8,
            "proposed_load_mw": .9, "identity_fixture": "operator", "measurement_age_seconds": .2,
            "topology_version": "demo-v1", "voltages_pu": [b["voltage_pu"] for b in solve()["buses"]]}


@pytest.mark.parametrize("field,value", [
    ("format_version", True), ("format_version", 2), ("name", "  "), ("name", "x" * 81),
    ("initial_load_mw", True), ("proposed_load_mw", float("nan")), ("proposed_load_mw", 15.1),
    ("identity_fixture", []), ("identity_fixture", "admin"), ("measurement_age_seconds", float("inf")),
    ("measurement_age_seconds", -3601), ("topology_version", {}), ("topology_version", "actual-grid"),
    ("voltages_pu", [1] * 5), ("voltages_pu", [True] * 6), ("voltages_pu", [2.1] * 6),
    ("expected_status", []), ("expected_status", "SAFE"),
])
def test_invalid_replay_inputs(sample, field, value):
    with pytest.raises(ValueError):
        validate_case({**sample, field: value})


def test_unknown_and_missing_fields_rejected(sample):
    for body in [None, [], {**sample, "authorized": True}, {k: v for k, v in sample.items() if k != "name"}]:
        with pytest.raises(ValueError):
            validate_case(body)


def test_expected_label_cannot_control_the_assessment(sample):
    normal = replay_case({**sample, "expected_status": "ALERT"})
    overload = replay_case({**sample, "proposed_load_mw": 6.5, "expected_status": "NO_ISSUE_DETECTED"})
    assert normal["status"] == "NO_ISSUE_DETECTED" and normal["expected_match"] is False
    assert overload["status"] == "ALERT" and overload["expected_match"] is False
    assert overload["equipment_actions"] == 0
    assert overload["source_hash"] == SOURCE_FINGERPRINT
    assert overload["telemetry"]["source"] == "untrusted synthetic replay file"
    assert replay_case(sample)["expected_match"] is None


@pytest.mark.parametrize("field,value,code", [
    ("voltages_pu", [None] * 6, "MISSING_DATA"),
    ("voltages_pu", [1.2] * 6, "INCONSISTENT_DATA"),
    ("measurement_age_seconds", 6, "STALE_DATA"),
    ("topology_version", "demo-v0", "TOPOLOGY_MISMATCH"),
])
def test_supplied_evidence_is_used(sample, field, value, code):
    result = replay_case({**sample, field: value})
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["predicted"] is None
    assert code in {reason["code"] for reason in result["reasons"]}


def test_replay_does_not_change_input(sample):
    original = deepcopy(sample)
    replay_case(sample)
    assert sample == original


def test_history_survives_reopening_and_preserves_exact_report(sample, tmp_path):
    path = tmp_path / "history.sqlite3"
    store = RunStore(path)
    report = store.save("replay", replay_case(sample))
    reopened = RunStore(path)
    assert reopened.get(report["id"]) == report
    assert reopened.recent()[0]["id"] == report["id"]
    assert report["record_kind"] == "replay"
    assert report["app_version"] == "0.2.0"
    with pytest.raises(sqlite3.IntegrityError):
        store.save("replay", report)
    assert reopened.get(report["id"]) == report
    for identifier in ["' OR 1=1 --", "../../server.json", "bad", None, "0" * 36]:
        assert reopened.get(identifier) is None
    json.dumps(report, allow_nan=False)


def test_history_lists_twenty_but_retains_all(tmp_path):
    store = RunStore(tmp_path / "history.sqlite3")
    records = [store.save("assessment", {"title": f"Run {i}", "status": "ALERT"}) for i in range(23)]
    recent = store.recent()
    assert len(recent) == 20 and recent[0]["id"] == records[-1]["id"]
    assert store.get(records[0]["id"]) == records[0]


def test_benchmark_saved_with_provenance(tmp_path):
    store = RunStore(tmp_path / "history.sqlite3")
    report = store.save("benchmark", {"summary": {"total": 30, "gridshield": {"matches": 30}}})
    assert store.recent()[0]["outcome"] == "30/30 expected labels"
    assert report["source_hash"] == SOURCE_FINGERPRINT
    assert store.get(report["id"]) == report
