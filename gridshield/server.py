"""Loopback-only demonstration server; explicit routes, no file or equipment API."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading

from . import __version__
from .benchmark import run_benchmark
from .model import CONFIG, POLICY, ROOT, MODEL_HASH, POLICY_HASH
from .monitor import assess, finite_number
from .scenarios import SCENARIOS, BY_ID
from .replay import replay_case
from .history import RunStore

HOST, PORT = "127.0.0.1", 8765
STATIC = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"),
          "/app.js": ("app.js", "text/javascript")}
COMPUTE = threading.Lock()


def evaluate_request(body):
    if not isinstance(body, dict) or not set(body) <= {"scenario_id", "load_mw"}:
        raise ValueError("Use a scenario_id and, for Explore demand only, an optional load_mw.")
    identifier = body.get("scenario_id")
    if not isinstance(identifier, str) or identifier not in BY_ID:
        raise ValueError("Choose a scenario from the catalog.")
    case = BY_ID[identifier]
    if "load_mw" in body:
        value = body["load_mw"]
        if identifier != "custom" or not finite_number(value) or not 0 <= value <= 15:
            raise ValueError("Explore demand accepts a finite number from 0 to 15 MW.")
        case = replace(case, target_mw=value)
    return assess(case)


class Handler(BaseHTTPRequestHandler):
    server_version = "GridShieldLab/0.2"

    def history(self):
        return self.server.run_store

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def send_bytes(self, code, data, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, code, body):
        self.send_bytes(code, json.dumps(body, allow_nan=False).encode(), "application/json")

    def error(self, code, name, message):
        self.send_json(code, {"error": name, "message": message})

    def local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts:
            self.error(403, "LOCAL_ONLY", "This lab accepts requests to its local address only.")
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{h}" for h in hosts}:
            self.error(403, "LOCAL_ONLY", "Cross-site requests are not accepted.")
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        if self.path in STATIC:
            filename, kind = STATIC[self.path]
            self.send_bytes(200, (ROOT / "web" / filename).read_bytes(), kind)
        elif self.path == "/api/health":
            self.send_json(200, {"app": "GridShield Lab", "version": __version__, "mode": "simulation-only",
                                 "model_hash": MODEL_HASH, "policy_hash": POLICY_HASH})
        elif self.path == "/api/catalog":
            self.send_json(200, {"network": CONFIG, "policy": POLICY, "scenarios": [
                {"id": s.id, "title": s.title, "description": s.description, "category": s.category}
                for s in SCENARIOS]})
        elif self.path == "/api/runs":
            self.send_json(200, {"runs": self.history().recent(), "scope": "Local editable records; not signed receipts."})
        elif self.path.startswith("/api/runs/"):
            report = self.history().get(self.path.removeprefix("/api/runs/"))
            if report is None:
                self.error(404, "NOT_FOUND", "This saved run does not exist.")
            else:
                self.send_json(200, report)
        else:
            self.error(404, "NOT_FOUND", "This route does not exist.")

    def do_POST(self):
        if not self.local_request():
            return
        if self.path not in {"/api/evaluate", "/api/benchmark", "/api/replay"}:
            self.error(404, "NOT_FOUND", "This route does not exist.")
            return
        if self.headers.get_content_type() != "application/json":
            self.error(415, "JSON_REQUIRED", "Send a JSON request.")
            return
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked requests are not supported.")
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4096:
                self.error(413, "BODY_TOO_LARGE", "Request exceeds the lab's 4096-byte limit.")
                return
            if length <= 0:
                raise ValueError("A JSON body is required.")
            def reject_constant(value):
                raise ValueError("JSON numbers must be finite.")
            body = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            if self.path == "/api/benchmark" and body != {}:
                raise ValueError("The benchmark takes an empty JSON object.")
            with COMPUTE:
                if self.path == "/api/evaluate":
                    kind, result = "assessment", evaluate_request(body)
                elif self.path == "/api/replay":
                    kind, result = "replay", replay_case(body)
                else:
                    kind, result = "benchmark", run_benchmark()
                result = self.history().save(kind, result)
        except (ValueError, UnicodeError) as exc:
            self.error(400, "INVALID_REQUEST", str(exc))
            return
        except Exception:
            logging.exception("Local assessment failed")
            self.error(500, "INTERNAL_ERROR", "The assessment could not finish. No equipment action was performed.")
            return
        self.send_json(200, result)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.run_store = RunStore()
    print(f"GridShield Lab is running at http://{HOST}:{PORT} — simulation only", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
