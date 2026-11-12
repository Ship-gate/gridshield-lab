"""Balanced AC load flow; all values and networks are synthetic."""
from hashlib import sha256
import json
import math
from pathlib import Path

import pandapower as pp

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config/network.json").read_text())
POLICY = json.loads((ROOT / "config/policy.json").read_text())


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


MODEL_HASH = digest({"network": CONFIG, "solver": "Newton-Raphson AC", "pandapower": pp.__version__})
POLICY_HASH = digest(POLICY)


def source_fingerprint():
    """Unsigned identifier of executable source/config; not an independent receipt."""
    files = [*ROOT.joinpath("gridshield").glob("*.py"), *ROOT.joinpath("web").glob("*"),
             *ROOT.joinpath("config").glob("*.json"), ROOT / "requirements.lock"]
    return digest({str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
                   for p in sorted(files) if p.is_file()})


SOURCE_FINGERPRINT = source_fingerprint()


class ModelUnavailable(RuntimeError):
    """An incomplete/nonconvergent model cannot establish a normal result."""


def build_network(industry_mw=0.8, disconnected=False):
    if type(industry_mw) not in (int, float) or not math.isfinite(industry_mw) or not 0 <= industry_mw <= 15:
        raise ValueError("Synthetic industry demand must be finite and between 0 and 15 MW.")
    net = pp.create_empty_network(name=CONFIG["name"], f_hz=60.0)
    for bus in CONFIG["buses"]:
        pp.create_bus(net, vn_kv=CONFIG["nominal_kv"], name=bus["name"], index=bus["id"])
    pp.create_ext_grid(net, bus=0, vm_pu=CONFIG["source_voltage_pu"])
    for line in CONFIG["lines"]:
        pp.create_line_from_parameters(
            net, line["from"], line["to"], length_km=line["length_km"],
            name=line["name"], index=line["id"], **CONFIG["line_parameters"],
        )
    for load in CONFIG["loads"]:
        power = industry_mw if load["id"] == "industry" else load["p_mw"]
        pp.create_load(net, load["bus"], p_mw=power,
                       q_mvar=power * CONFIG["reactive_to_active_ratio"], name=load["id"])
    if disconnected:
        net.line.at[0, "in_service"] = False
    return net


def solve(industry_mw=0.8, disconnected=False):
    net = build_network(industry_mw, disconnected)
    try:
        pp.runpp(net, algorithm="nr", numba=False, init="flat", max_iteration=30,
                 tolerance_mva=1e-8, check_connectivity=True)
    except Exception as exc:
        raise ModelUnavailable("The AC solver could not produce a complete result.") from exc
    if not net.converged:
        raise ModelUnavailable("The AC solver did not converge.")
    values = [*net.res_bus.vm_pu, *net.res_line.loading_percent, *net.res_ext_grid.p_mw]
    if not all(math.isfinite(float(v)) for v in values):
        raise ModelUnavailable("Some buses or lines have no finite result; the grid may be disconnected.")
    buses = [{**b, "voltage_pu": float(net.res_bus.at[b["id"], "vm_pu"])} for b in CONFIG["buses"]]
    lines = [{**line, "loading_percent": float(net.res_line.at[line["id"], "loading_percent"]),
              "power_mw": float(net.res_line.at[line["id"], "p_from_mw"])} for line in CONFIG["lines"]]
    return {
        "buses": buses, "lines": lines,
        "min_voltage_pu": min(b["voltage_pu"] for b in buses),
        "max_voltage_pu": max(b["voltage_pu"] for b in buses),
        "max_loading_percent": max(line["loading_percent"] for line in lines),
        "demand_mw": float(net.load.p_mw.sum()),
        "source_mw": float(net.res_ext_grid.p_mw.sum()),
        "losses_mw": float(net.res_line.pl_mw.sum()),
        "industry_mw": industry_mw,
    }
