"""Reproducible comparison on declared synthetic examples, not independent validation."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

from .monitor import assess, SCOPE
from .model import MODEL_HASH, POLICY_HASH, SOURCE_FINGERPRINT
from . import __version__
from .scenarios import benchmark_cases


def run_benchmark():
    rows = []
    for case in benchmark_cases():
        result = assess(case)
        rows.append({"id": case.id, "title": case.title, "expected": case.expected,
                     "gridshield": result["status"], "simple_rules": result["simple_status"],
                     "matches_expected": result["status"] == case.expected,
                     "elapsed_ms": result["elapsed_ms"], "reasons": result["reasons"]})
    elapsed = sorted(r["elapsed_ms"] for r in rows)
    def counts(key):
        return {
            "matches": sum(r[key] == r["expected"] for r in rows),
            "missed_alerts": sum(r["expected"] == "ALERT" and r[key] != "ALERT" for r in rows),
            "false_alerts": sum(r["expected"] == "NO_ISSUE_DETECTED" and r[key] == "ALERT" for r in rows),
            "uncertainty_reported_normal": sum(r["expected"] == "INSUFFICIENT_EVIDENCE" and r[key] == "NO_ISSUE_DETECTED" for r in rows),
        }
    return {"cases": rows, "summary": {"total": len(rows), "gridshield": counts("gridshield"),
            "simple_rules": counts("simple_rules"), "class_counts": dict(Counter(r["expected"] for r in rows)),
            "median_ms": round(statistics.median(elapsed), 2),
            "p95_ms": elapsed[min(len(elapsed)-1, int(len(elapsed)*0.95))]},
            "generated_at": datetime.now(timezone.utc).isoformat(), "policy_hash": POLICY_HASH,
            "app_version": __version__, "source_hash": SOURCE_FINGERPRINT,
            "model_hash": MODEL_HASH, "scope": SCOPE,
            "method": "30 declared development regression cases, including 16 seeded variations (seed 20261112). Not held-out, independent, or utility validation. Baseline checks lab identity, action, device and numeric envelope only; it is not a commercial product comparison."}


def main():
    report = run_benchmark()
    folder = Path(__file__).resolve().parent.parent / "reports"
    folder.mkdir(exist_ok=True)
    (folder / "benchmark.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    summary = report["summary"]
    print(json.dumps(summary, indent=2))
    return 0 if summary["gridshield"]["matches"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
