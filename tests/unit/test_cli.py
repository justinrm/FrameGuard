from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "frameguard.cli", *args],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_and_version() -> None:
    help_result = run_cli("--help")
    assert help_result.returncode == 0
    assert "scan" in help_result.stdout

    version_result = run_cli("--version")
    assert version_result.returncode == 0
    assert "0.1.0" in version_result.stdout

    scan_help = run_cli("scan", "--help")
    assert scan_help.returncode == 0
    assert "INPUT" in scan_help.stdout

    missing = run_cli("scan")
    assert missing.returncode == 2
    assert "Traceback" not in missing.stderr

    unknown = run_cli("not-a-command")
    assert unknown.returncode == 2
