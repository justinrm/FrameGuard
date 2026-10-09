from __future__ import annotations

import os
import subprocess
import sys

import pytest

from frameguard.models import DependencyError, ProcessSpec
from frameguard.process import discover_tools, run_process


def spec(argv: list[str], **overrides: object) -> ProcessSpec:
    values = {
        "argv": argv,
        "timeout_seconds": 5.0,
        "stdout_limit_bytes": 32_768,
        "diagnostic_limit_bytes": 16_384,
        "line_limit_bytes": 1024,
    }
    values.update(overrides)
    return ProcessSpec(**values)


def test_runner_uses_argv_closed_stdin_and_sanitized_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = subprocess.Popen
    observed: dict[str, object] = {}

    def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        observed.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr("frameguard.process.subprocess.Popen", recording_popen)
    monkeypatch.setenv("FFREPORT", "file=must-not-exist.log")
    result = run_process(
        spec(
            [
                sys.executable,
                "-c",
                "import os; print(os.getenv('FFREPORT')); print(os.getenv('AV_LOG_FORCE_NOCOLOR'))",
            ]
        )
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [b"None", b"1"]
    assert observed["shell"] is False
    assert observed["stdin"] is subprocess.DEVNULL
    assert not os.path.exists("must-not-exist.log")


def test_runner_fails_closed_on_flood_long_line_and_nonzero() -> None:
    flood = run_process(
        spec(
            [sys.executable, "-c", "import os; os.write(1,b'x'*200000); os.write(2,b'y'*200000)"],
            stdout_limit_bytes=4096,
        )
    )
    assert flood.output_limit_exceeded
    assert len(flood.stdout) == 4096
    assert len(flood.diagnostic_tail) <= 16_384

    long_line = run_process(
        spec([sys.executable, "-c", "import sys; sys.stderr.write('x'*2000+'\\n')"])
    )
    assert long_line.line_limit_exceeded

    nonzero = run_process(spec([sys.executable, "-c", "raise SystemExit(7)"]))
    assert nonzero.returncode == 7


def test_runner_times_out_kills_and_reaps() -> None:
    result = run_process(
        spec(
            [
                sys.executable,
                "-c",
                "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)",
            ],
            timeout_seconds=0.1,
        )
    )
    assert result.timed_out
    assert result.returncode is not None
    assert 2 <= result.elapsed_seconds < 4


def test_discovery_reports_missing_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("frameguard.process.shutil.which", lambda _: None)
    with pytest.raises(DependencyError, match="ffmpeg"):
        discover_tools()
