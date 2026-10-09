from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from frameguard.cli import main
from frameguard.models import OutputError

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
    assert "coded width" in scan_help.stdout
    assert "selected video stream" in scan_help.stdout
    assert "Warnings still exit 0." in scan_help.stdout
    assert "--json" in scan_help.stdout
    assert "--expect-width" in scan_help.stdout

    missing = run_cli("scan")
    assert missing.returncode == 2
    assert "Traceback" not in missing.stderr

    unknown = run_cli("not-a-command")
    assert unknown.returncode == 2


def test_existing_output_is_refused_before_scan(tmp_path: Path, monkeypatch) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    dest = tmp_path / "out.json"
    dest.write_bytes(b"keep")

    def refuse_scan(*_args, **_kwargs):
        raise AssertionError("scan")

    monkeypatch.setattr("frameguard.cli.scan", refuse_scan)
    assert main(["scan", str(media), "--json", str(dest)]) == 2
    assert dest.read_bytes() == b"keep"


def test_invalid_expectation_exits_2(tmp_path: Path, monkeypatch) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")

    def refuse_scan(*_args, **_kwargs):
        raise AssertionError("scan")

    monkeypatch.setattr("frameguard.cli.scan", refuse_scan)
    assert main(["scan", str(media), "--expect-fps", "nope"]) == 2


def test_second_output_failure_keeps_the_first(tmp_path: Path, monkeypatch, sample_report) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    json_path = tmp_path / "out.json"
    html_path = tmp_path / "out.html"
    report = sample_report("pass")
    monkeypatch.setattr("frameguard.cli.scan", lambda *_args, **_kwargs: report)

    def flaky(path: Path, content: str) -> None:
        if path == html_path:
            raise OutputError("output already exists: out.html")
        from frameguard.reporting import publish_report

        publish_report(path, content)

    monkeypatch.setattr("frameguard.cli.publish_report", flaky)
    assert main(["scan", str(media), "--json", str(json_path), "--html", str(html_path)]) == 2
    assert json.loads(json_path.read_text())["overall_status"] == "pass"
    assert not html_path.exists()
    assert report.overall_status == "pass"
