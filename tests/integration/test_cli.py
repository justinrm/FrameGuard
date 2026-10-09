from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_frameguard(*args: str) -> subprocess.CompletedProcess[str]:
    executable = Path(sys.executable).parent / "frameguard"
    return subprocess.run(
        [executable, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installed_cli_prints_metadata_and_incomplete_exit(
    media_fixtures: dict[str, Path],
) -> None:
    result = run_frameguard("scan", str(media_fixtures["baseline"]))

    assert result.returncode == 2
    assert "Status: incomplete" in result.stdout
    assert "Video stream: 0" in result.stdout
    assert "Black detection: not implemented in Milestone 1" in result.stdout
    assert "Traceback" not in result.stderr


def test_installed_cli_controls_missing_and_invalid_input(tmp_path: Path) -> None:
    missing = run_frameguard("scan", str(tmp_path / "missing.mp4"))
    assert missing.returncode == 2
    assert "input is unavailable" in missing.stdout
    assert "Traceback" not in missing.stderr

    invalid = tmp_path / "invalid.mp4"
    invalid.write_bytes(b"not media")
    bad = run_frameguard("scan", str(invalid))
    assert bad.returncode == 2
    assert "ffprobe could not inspect" in bad.stdout
    assert "Traceback" not in bad.stderr
