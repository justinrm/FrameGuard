from __future__ import annotations

import json
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


def test_installed_cli_prints_metadata_and_pass_exit(
    media_fixtures: dict[str, Path],
) -> None:
    result = run_frameguard("scan", str(media_fixtures["baseline"]))

    assert result.returncode == 0
    assert "Status: pass" in result.stdout
    assert "Video stream: 0" in result.stdout
    assert "not implemented" not in result.stdout
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


def test_installed_cli_writes_both_reports_and_expectation_exits(
    tmp_path: Path, media_fixtures: dict[str, Path]
) -> None:
    json_path = tmp_path / "out.json"
    html_path = tmp_path / "out.html"
    passed = run_frameguard(
        "scan",
        str(media_fixtures["baseline"]),
        "--expect-fps",
        "29.97",
        "--json",
        str(json_path),
        "--html",
        str(html_path),
    )
    assert passed.returncode == 0
    assert "Status: pass" in passed.stdout
    payload = json.loads(json_path.read_text())
    page = html_path.read_text()
    assert payload["overall_status"] == "pass"
    assert payload["schema_version"] == "0.1.0"
    assert "pass" in page
    assert "<script" not in page.lower()

    mismatch = run_frameguard("scan", str(media_fixtures["baseline"]), "--expect-width", "100")
    assert mismatch.returncode == 1
    assert "RESOLUTION_MISMATCH" in mismatch.stdout

    warned = run_frameguard("scan", str(media_fixtures["interior_black"]))
    assert warned.returncode == 0
    assert "BLACK_INTERVAL" in warned.stdout

    kept = tmp_path / "kept.json"
    kept.write_text("keep")
    blocked = run_frameguard("scan", str(media_fixtures["baseline"]), "--json", str(kept))
    assert blocked.returncode == 2
    assert kept.read_text() == "keep"
