# GridShield Lab

An open research prototype for checking what a grid control command would physically do before anyone trusts it. It runs locally on a fictional six-bus feeder and never communicates with equipment.

## Thesis

**Authorization is not safety.** Grid control systems mostly decide whether to accept a command by asking who sent it. A stolen credential, a malicious insider and an honest operator mistake all pass that test. The command is authorized, and it can still overload a line or push voltage out of range.

The missing check is physical. Before a command takes effect, predict its consequence on the network, and report one of three things: no issue detected, alert, or insufficient evidence. The third verdict matters as much as the first two. A monitor that issues a confident answer on stale, missing or inconsistent measurements is worse than no monitor.

This idea is not new. Universities, national laboratories and vendors have demonstrated physics-aware command checking for about a decade, and it still is not standard practice. The reason is practical: utility network models are often wrong, sensors are sparse, and false alarms destroy operator trust.

So the question this project exists to answer is narrower than the idea:

> How wrong can the network model be, and how few sensors can you have, before physics-aware command checking stops being useful?

This repository does not answer that yet. It is a small, honest starting point: a working three-verdict monitor, a declared regression corpus, and a list of what has to change for the results to mean something. See [Roadmap](#roadmap). If you work at a utility, a co-op, a power systems lab or an OT security team and can tell us where this is wrong, that is the most useful contribution you can make.

## What it does today

- Solves a balanced, steady-state AC power flow with [pandapower](https://pandapower.readthedocs.io/) for six buses, five lines and four loads.
- Assesses one kind of proposed change: a new demand value for the industrial load.
- Compares baseline measurements with the model and declines to give a normal verdict when data is stale, missing, future-dated, inconsistent or tied to a different topology.
- Compares its verdict with a deliberately simple permission-and-range baseline.
- Replays reviewer-supplied synthetic cases from JSON and keeps a local run history.

It has no equipment control, protocol integration, network discovery, real authentication or real utility data.

## Run it

Requires Python 3.11 or newer.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python -m gridshield
```

Then open <http://127.0.0.1:8765>. The server binds to the loopback interface only. Ctrl-C stops it. No cloud account, API key or network access is used once dependencies are installed.

The `*.command` files are macOS launchers from the original packaging. They expect this folder at `outputs/gridshield` with a sibling `work` folder and use [uv](https://docs.astral.sh/uv/); the commands above are the portable route.

## Try these first

1. **Routine demand change**: a small increase that stays within limits.
2. **Authorized, but overloaded**: the permission-only baseline accepts the request; GridShield reports the simulated line overloads (about 185.7% maximum line loading).
3. **Reduce an existing overload**: switch Current / Proposed to see a legitimate reduction relieve the overload.
4. **Outdated measurements**, **Conflicting measurements** or **Disconnected model**: see why no normal verdict is issued.
5. **Explore demand**: move the slider, then press **Assess new demand**.
6. **Run all 30 cases**: compare outcomes against the declared expectations and export the report.
7. **Evaluate your own synthetic case**: import a file from `samples/`. `deliberately-wrong-label.json` shows that expected labels do not control findings.

## Replay format

Each JSON case has `format_version: 1`, a `name` (up to 80 characters), `initial_load_mw` and `proposed_load_mw` (0–15), `identity_fixture` (`operator`, `viewer` or `unknown`), `measurement_age_seconds` (-3600–86400), `topology_version` (`demo-v1` or `demo-v0`) and exactly six `voltages_pu` entries (0–2 or null) in bus order. The optional `expected_status` is compared only after the verdict is computed. Extra fields and nonfinite numbers are rejected. The file limit is 4 KB.

```sh
.venv/bin/python -m gridshield.replay samples/overload.json
```

The local API exposes `POST /api/replay`, `GET /api/runs` and `GET /api/runs/{run_id}` alongside the built-in evaluation routes.

## Configuration

Illustrative limits live in `config/policy.json`: voltage 0.95–1.05 pu, line loading 100%, measurement age at most five seconds, clock skew tolerance 0.5 seconds and voltage residual at most 0.02 pu. These are lab parameters, not approved operating limits. Network parameters are in `config/network.json`. Reports include the app version and hashes of the model configuration, policy and source snapshot. Hashes identify content; they do not authenticate its origin.

Actor identities and permissions are fixed server-side fixtures. This is not an identity system for utility operators.

## Reproduce the checks

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m gridshield.benchmark
```

The benchmark writes `reports/benchmark.json`. Tests cover all 30 declared cases, electrical conservation, scenario isolation, solver failures, freshness boundaries, denied identities, input validation and local HTTP restrictions.

## What the results establish

The corpus has 30 declared development cases: 11 normal, 13 alerts and six insufficient-evidence cases. Sixteen are seeded demand variations (seed 20261112). GridShield matches 30/30 expected labels and the simple baseline matches 15/30.

Read that result narrowly. The expected labels were authored with the prototype and come from the same solver, and the baseline has no physics by construction. The numbers show the intended behavior on these examples. They do not show real-world detection rates, superiority to existing tools or suitability for a live grid.

## Known limits

- Built-in measurements are synthesized from the same model they are compared against, so the residual check only catches injected offsets. A wrong-but-consistent model or coordinated false measurements escape it.
- The assessed command, changing an industrial customer's demand, is not a real control action. Real commands are breaker and switch operations, tap changes, capacitor banks and DER setpoints.
- Unauthorized requests are rejected before the proposed state is simulated, so the tool cannot yet report "unauthorized and would overload the feeder".
- No transient stability, frequency dynamics, protection coordination or unbalanced feeder behavior.
- No packet capture, industrial protocol parsing, authentication or tamper-resistant audit record. Exported JSON is editable.
- Six buses. Timing figures are local computation, not a real-time guarantee.

## Roadmap

In priority order. The third item is the centerpiece.

1. **Standard feeders and real commands.** IEEE 13- and 123-bus test feeders with an unbalanced solver such as OpenDSS; switching, regulator and DER commands.
2. **Always simulate.** Report authority and physical consequence as two independent axes.
3. **Separate truth from the model.** Generate measurements from a second simulator with deliberate parameter error and noise, add state estimation, and publish false and missed alerts against model error and sensor coverage.
4. **Cases where physics is needed.** Command sequences that are individually acceptable, loop closing, volt/VAR manipulation and aggregated DER setpoints.
5. **Read commands from a real protocol**, starting with DNP3 from simulated captures.
6. **An open benchmark**: public feeders, a labeled command corpus and a runnable harness that others can cite and extend.

## Contributing

Issues and pull requests are welcome. Corrections from people who operate or study real distribution systems are especially valuable, including "this already exists, see X". Use synthetic data only; do not post real utility models, measurements or credentials.

## References

- [pandapower line model and creation API](https://pandapower.readthedocs.io/en/stable/elements/line.html)
- [pandapower power-flow documentation](https://pandapower.readthedocs.io/en/stable/powerflow.html)
- [NIST guidance for operational technology security](https://csrc.nist.gov/pubs/sp/800/82/r3/final)
- [Berkeley Lab prior work combining cyber and physical monitoring](https://secpriv.lbl.gov/project/ceds-cps-security)

## License

Apache License 2.0. See [LICENSE](LICENSE).

The `.vibecheck/truthpack` files are a hand-declared contract for this project's routes and report shape; the test suite checks the application against them.
