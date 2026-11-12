"""Start or reopen this local lab; never kill or replace another service."""
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT.parents[1] / "work/gridshield-runtime"
URL = "http://127.0.0.1:8765"


def health():
    try:
        with urllib.request.urlopen(URL + "/api/health", timeout=1) as response:
            data = json.load(response)
        return data if data.get("app") == "GridShield Lab" and data.get("mode") == "simulation-only" else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def ensure_running():
    if health():
        return URL
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / "server.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, "-m", "gridshield"], cwd=ROOT,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    (RUNTIME / "server.json").write_text(json.dumps({"pid":process.pid,"url":URL,"project":str(ROOT)}, indent=2))
    for _ in range(80):
        if process.poll() is not None:
            raise RuntimeError(f"GridShield could not start. Port 8765 may be occupied. Details: {RUNTIME / 'server.log'}")
        if health():
            return URL
        time.sleep(.25)
    process.terminate()
    raise RuntimeError(f"GridShield did not become ready. Details: {RUNTIME / 'server.log'}")


if __name__ == "__main__":
    try:
        url = ensure_running()
        print("GridShield Lab is running at " + url)
        webbrowser.open(url)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
