from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_wheel_scans_outside_checkout(
    tmp_path: Path, media_fixtures: dict[str, Path]
) -> None:
    dist = tmp_path / "dist"
    built = _run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
        cwd=ROOT,
    )
    assert built.returncode == 0, built.stderr
    wheels = list(dist.glob("frameguard-*.whl"))
    assert len(wheels) == 1

    venv = tmp_path / "venv"
    created = _run([sys.executable, "-m", "venv", str(venv)], cwd=tmp_path)
    assert created.returncode == 0, created.stderr
    installed = _run(
        [str(venv / "bin" / "pip"), "install", "--no-index", str(wheels[0])],
        cwd=tmp_path,
    )
    assert installed.returncode == 0, installed.stderr

    work = tmp_path / "work"
    work.mkdir()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    frameguard = str(venv / "bin" / "frameguard")
    help_run = _run([frameguard, "--help"], cwd=work, env=env)
    version = _run([frameguard, "--version"], cwd=work, env=env)
    scan = _run([frameguard, "scan", str(media_fixtures["baseline"])], cwd=work, env=env)

    assert help_run.returncode == 0
    assert "scan" in help_run.stdout
    assert version.returncode == 0
    assert version.stdout.strip() == "frameguard 0.1.0"
    assert scan.returncode == 0
    assert "Status: pass" in scan.stdout
    assert "Traceback" not in scan.stderr
