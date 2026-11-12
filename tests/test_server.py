import http.client
from http.server import ThreadingHTTPServer
import json
import threading

import pytest

from gridshield.model import ROOT
from gridshield.server import Handler, STATIC
from gridshield.history import RunStore


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    instance.run_store = RunStore(tmp_path_factory.mktemp("server") / "test.sqlite3")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join()


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=20)
    connection.request(method, path, body, headers or {})
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


@pytest.mark.parametrize("path", ["/", "/style.css", "/app.js", "/api/health", "/api/catalog"])
def test_declared_get_routes(server, path):
    status, headers, content = request(server, "GET", path)
    assert status == 200 and content
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_assessment_route(server):
    status, _, content = request(server, "POST", "/api/evaluate", json.dumps({"scenario_id":"overload"}), {"Content-Type":"application/json"})
    assert status == 200
    assert json.loads(content)["status"] == "ALERT"


def test_benchmark_route_matches_declared_cases(server):
    status, _, content = request(server, "POST", "/api/benchmark", "{}", {"Content-Type":"application/json"})
    report = json.loads(content)
    assert status == 200
    assert report["summary"]["total"] == 30
    assert report["summary"]["gridshield"]["matches"] == 30
    assert report["summary"]["gridshield"]["false_alerts"] == 0


@pytest.mark.parametrize("path", ["/../../config/policy.json", "/config/policy.json", "/api/control", "/api/evaluate?extra=1"])
def test_no_undeclared_file_or_control_routes(server, path):
    assert request(server, "GET", path)[0] == 404


@pytest.mark.parametrize("headers", [{"Host":"foreign.example"}, {"Origin":"https://foreign.example"}, {"Origin":"null"}])
def test_foreign_requests_rejected(server, headers):
    assert request(server, "GET", "/api/health", headers=headers)[0] == 403


@pytest.mark.parametrize("body,headers,expected", [
    ('{"scenario_id":"routine","authorized":true}', {"Content-Type":"application/json"}, 400),
    ('{"scenario_id":"custom","load_mw":NaN}', {"Content-Type":"application/json"}, 400),
    ('{}', {"Content-Type":"text/plain"}, 415),
    ('x'*4097, {"Content-Type":"application/json"}, 413),
    ('broken', {"Content-Type":"application/json"}, 400),
])
def test_invalid_http_input(server, body, headers, expected):
    status, _, content = request(server, "POST", "/api/evaluate", body, headers)
    assert status == expected
    assert "error" in json.loads(content)


def test_route_contract_is_complete():
    truth = json.loads((ROOT / ".vibecheck/truthpack/routes.json").read_text())
    actual = {("GET", p) for p in STATIC} | {("GET", "/api/health"), ("GET", "/api/catalog"),
             ("POST", "/api/evaluate"), ("POST", "/api/benchmark"), ("POST", "/api/replay"),
             ("GET", "/api/runs"), ("GET", "/api/runs/{run_id}")}
    assert {(r["method"], r["path"]) for r in truth["routes"]} == actual


def test_replay_and_saved_report_routes(server):
    from gridshield.model import solve
    case = {"format_version":1, "name":"HTTP replay", "initial_load_mw":.8, "proposed_load_mw":6.5,
            "identity_fixture":"operator", "measurement_age_seconds":.2, "topology_version":"demo-v1",
            "voltages_pu":[b["voltage_pu"] for b in solve()["buses"]], "expected_status":"NO_ISSUE_DETECTED"}
    status, _, content = request(server, "POST", "/api/replay", json.dumps(case), {"Content-Type":"application/json"})
    report = json.loads(content)
    assert status == 200 and report["status"] == "ALERT" and report["expected_match"] is False
    status, _, content = request(server, "GET", "/api/runs/" + report["id"])
    assert status == 200 and json.loads(content) == report
    status, _, content = request(server, "GET", "/api/runs")
    assert status == 200 and json.loads(content)["runs"][0]["id"] == report["id"]
    assert request(server, "GET", "/api/runs/not-a-uuid")[0] == 404
    before = server.run_store.recent()
    case["authorized"] = True
    assert request(server, "POST", "/api/replay", json.dumps(case), {"Content-Type":"application/json"})[0] == 400
    assert server.run_store.recent() == before
