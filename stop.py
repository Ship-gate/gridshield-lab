"""Stop only a process whose recorded PID and command match this lab server."""
import json
from pathlib import Path
import os
import signal
import subprocess
import sys


def matches_server(command, cwd_lines, root, python_prefix):
    suffix = " -m gridshield"
    if not command.endswith(suffix):
        return False
    executable = Path(command[:-len(suffix)]).resolve()
    # On macOS, ps reports the Python.framework executable behind the venv symlink.
    allowed_python = executable.is_relative_to(Path(python_prefix).resolve())
    return allowed_python and f"n{root}" in cwd_lines.splitlines()


def main():
    root = Path(__file__).resolve().parent
    record = root.parents[1] / "work/gridshield-runtime/server.json"
    if not record.exists():
        print("No GridShield process record was found.")
        return
    data = json.loads(record.read_text())
    pid = data.get("pid")
    if type(pid) is not int or pid <= 1 or data.get("project") != str(root):
        raise SystemExit("The process record does not identify this GridShield installation.")
    command = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout.strip()
    cwd_lines = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True).stdout
    if matches_server(command, cwd_lines, root, sys.base_prefix):
        os.kill(pid, signal.SIGTERM)
        record.unlink()
        print("GridShield Lab stopped.")
    elif not command:
        record.unlink()
        print("GridShield Lab was already stopped.")
    else:
        raise SystemExit("The recorded process no longer matches GridShield. Nothing was stopped.")


if __name__ == "__main__":
    main()
