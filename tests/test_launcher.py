from pathlib import Path
import sys

import pytest

from stop import matches_server


@pytest.mark.parametrize("command,cwd,expected", [
    ("/trusted/python/bin/python -m gridshield", "n/lab/gridshield", True),
    ("/trusted/python/Resources/Python.app/Contents/MacOS/Python -m gridshield", "p123\nfcwd\nn/lab/gridshield\n", True),
    ("/trusted/python/bin/python -m another_app", "n/lab/gridshield", False),
    ("/trusted/python/bin/python -m gridshield", "n/another/project", False),
    ("/untrusted/bin/python -m gridshield", "n/lab/gridshield", False),
    ("/trusted/python/bin/python -m gridshield extra", "n/lab/gridshield", False),
])
def test_stop_matches_only_this_project_and_interpreter(command, cwd, expected):
    assert matches_server(command, cwd, Path("/lab/gridshield"), "/trusted/python") is expected
