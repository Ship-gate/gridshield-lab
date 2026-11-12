"""Declared demonstration cases. These are not real incidents or authenticated identities."""
from dataclasses import dataclass, replace
import random


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    description: str
    category: str
    expected: str | None
    target_mw: float = 0.9
    initial_mw: float = 0.8
    actor: str = "operator"
    device: str = "industry"
    action: str = "set_load_mw"
    age_seconds: float = 0.2
    missing: bool = False
    voltage_offset: float = 0.0
    topology_version: str = "demo-v1"
    disconnected: bool = False
    noisy: bool = False


SCENARIOS = (
    Scenario("routine", "Routine demand change", "A known lab operator raises industry demand from 0.8 to 0.9 MW.", "Normal operations", "NO_ISSUE_DETECTED"),
    Scenario("overload", "Authorized, but overloaded", "The operator is permitted to request this change. The electrical model still needs to check its consequences.", "Physical consequences", "ALERT", target_mw=6.5),
    Scenario("recovery", "Reduce an existing overload", "A legitimate reduction from 6.5 to 0.8 MW relieves the modeled overload.", "Normal operations", "NO_ISSUE_DETECTED", target_mw=0.8, initial_mw=6.5),
    Scenario("unknown_actor", "Unknown operator", "The simulated identity is absent from the local lab's operator registry.", "Permissions", "ALERT", actor="unknown"),
    Scenario("viewer", "Viewer requests a change", "This lab identity has observation permissions only.", "Permissions", "ALERT", actor="viewer"),
    Scenario("unknown_device", "Unknown equipment", "The request names equipment that is not in this synthetic model.", "Permissions", "ALERT", device="unregistered"),
    Scenario("unsupported", "Unsupported operation", "Only synthetic load-change assessments are implemented.", "Permissions", "ALERT", action="change_mode"),
    Scenario("stale", "Outdated measurements", "Measurements are 30 seconds old, exceeding the illustrative five-second limit.", "Data quality", "INSUFFICIENT_EVIDENCE", age_seconds=30),
    Scenario("missing", "Missing measurements", "One voltage measurement is absent. A normal verdict would hide missing evidence.", "Data quality", "INSUFFICIENT_EVIDENCE", missing=True),
    Scenario("conflicting", "Conflicting measurements", "A synthetic sensor differs from the model by 0.08 per unit. This alone does not establish an attack.", "Data quality", "INSUFFICIENT_EVIDENCE", voltage_offset=0.08),
    Scenario("future", "Clock inconsistency", "The measurement timestamp is ten seconds in the future.", "Data quality", "INSUFFICIENT_EVIDENCE", age_seconds=-10),
    Scenario("topology", "Outdated network model", "The incoming topology label does not match the model being used.", "Data quality", "INSUFFICIENT_EVIDENCE", topology_version="demo-v0"),
    Scenario("disconnected", "Disconnected model", "The source feeder is out of service. Islanded operation is outside this model's capabilities.", "Model limits", "INSUFFICIENT_EVIDENCE", disconnected=True),
    Scenario("noise", "Small measurement variation", "Small synthetic sensor variation remains within the configured residual tolerance.", "Normal operations", "NO_ISSUE_DETECTED", noisy=True),
    Scenario("custom", "Explore demand", "Adjust industry demand and assess the proposed state. Nothing is applied to equipment.", "Your experiment", None),
)
BY_ID = {s.id: s for s in SCENARIOS}


def benchmark_cases():
    """Fixed regression examples plus seeded variations, never called independent validation."""
    cases = [s for s in SCENARIOS if s.expected is not None]
    rng = random.Random(20261112)
    for i in range(8):
        cases.append(replace(BY_ID["routine"], id=f"normal_{i}", title=f"Routine variation {i+1}",
                             target_mw=round(rng.uniform(0.1, 1.4), 4)))
        cases.append(replace(BY_ID["overload"], id=f"overload_{i}", title=f"Demand stress {i+1}",
                             target_mw=round(rng.uniform(5.5, 8.0), 4)))
    return cases
