from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from .models import (
    DependencyError,
    ProcessResult,
    ProcessSpec,
    Toolchain,
    ToolVersions,
)

SUPPORTED_FFMPEG_VERSION = (9, 0, 2)
_VERSION_RE = re.compile(r"^(ffmpeg|ffprobe) version (\d+)\.(\d+)\.(\d+)\b")


def run_process(spec: ProcessSpec) -> ProcessResult:
    if not spec.argv:
        raise ValueError("argv must not be empty")

    environment = os.environ.copy()
    environment.pop("FFREPORT", None)
    environment["AV_LOG_FORCE_NOCOLOR"] = "1"
    started = time.monotonic()
    process = subprocess.Popen(
        spec.argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=environment,
        start_new_session=True,
    )
    stdout = bytearray()
    diagnostic_chunks: deque[bytes] = deque()
    diagnostic_size = 0
    output_limit_exceeded = False
    line_limit_exceeded = False
    lock = threading.Lock()

    def drain_stdout() -> None:
        nonlocal output_limit_exceeded
        assert process.stdout is not None
        while chunk := process.stdout.read(65_536):
            with lock:
                room = spec.stdout_limit_bytes - len(stdout)
                if room > 0:
                    stdout.extend(chunk[:room])
                if len(chunk) > room:
                    output_limit_exceeded = True

    def drain_stderr() -> None:
        nonlocal diagnostic_size, line_limit_exceeded
        assert process.stderr is not None
        pending = bytearray()
        while chunk := process.stderr.read(65_536):
            with lock:
                diagnostic_chunks.append(chunk)
                diagnostic_size += len(chunk)
                while diagnostic_size > spec.diagnostic_limit_bytes and diagnostic_chunks:
                    diagnostic_size -= len(diagnostic_chunks.popleft())
            pending.extend(chunk)
            while (newline := pending.find(b"\n")) >= 0:
                line = bytes(pending[:newline])
                del pending[: newline + 1]
                if len(line) > spec.line_limit_bytes:
                    line_limit_exceeded = True
                elif spec.event_callback is not None:
                    spec.event_callback(line.decode("utf-8", "replace"))
            if len(pending) > spec.line_limit_bytes:
                line_limit_exceeded = True
                pending.clear()
        if pending:
            if len(pending) > spec.line_limit_bytes:
                line_limit_exceeded = True
            elif spec.event_callback is not None:
                spec.event_callback(pending.decode("utf-8", "replace"))

    threads = (
        threading.Thread(target=drain_stdout, daemon=True),
        threading.Thread(target=drain_stderr, daemon=True),
    )
    for thread in threads:
        thread.start()

    timed_out = False
    try:
        while process.poll() is None:
            if time.monotonic() - started >= spec.timeout_seconds:
                timed_out = True
                break
            if output_limit_exceeded or line_limit_exceeded:
                break
            time.sleep(0.01)
    except KeyboardInterrupt:
        _terminate(process)
        for thread in threads:
            thread.join(timeout=2)
        raise

    if process.poll() is None:
        _terminate(process)
    else:
        process.wait()

    for thread in threads:
        thread.join(timeout=2)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("subprocess pipe drain did not finish")

    diagnostic_tail = b"".join(diagnostic_chunks)[-spec.diagnostic_limit_bytes :]
    return ProcessResult(
        returncode=process.returncode,
        stdout=bytes(stdout),
        diagnostic_tail=diagnostic_tail,
        timed_out=timed_out,
        output_limit_exceeded=output_limit_exceeded,
        line_limit_exceeded=line_limit_exceeded,
        elapsed_seconds=time.monotonic() - started,
    )


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _tool_output(argv: list[str], *, stdout_limit: int = 1024 * 1024) -> str:
    result = run_process(
        ProcessSpec(
            argv=argv,
            timeout_seconds=10,
            stdout_limit_bytes=stdout_limit,
            diagnostic_limit_bytes=1024 * 1024,
            line_limit_bytes=64 * 1024,
        )
    )
    if (
        result.returncode != 0
        or result.timed_out
        or result.output_limit_exceeded
        or result.line_limit_exceeded
    ):
        raise DependencyError(f"required capability command failed: {argv[0]}")
    return (result.stdout + result.diagnostic_tail).decode("utf-8", "replace")


def _version_line(executable: Path, expected_tool: str) -> str:
    output = _tool_output([str(executable), "-version"], stdout_limit=64 * 1024)
    line = output.splitlines()[0] if output else ""
    match = _VERSION_RE.match(line)
    if not match or match.group(1) != expected_tool:
        raise DependencyError(f"could not parse {expected_tool} version")
    version = tuple(int(value) for value in match.groups()[1:])
    if version != SUPPORTED_FFMPEG_VERSION:
        expected = ".".join(str(value) for value in SUPPORTED_FFMPEG_VERSION)
        raise DependencyError(f"{expected_tool} {expected} is required; found {version}")
    return line


def discover_tools() -> Toolchain:
    ffmpeg_name = shutil.which("ffmpeg")
    ffprobe_name = shutil.which("ffprobe")
    if not ffmpeg_name:
        raise DependencyError("ffmpeg was not found on PATH")
    if not ffprobe_name:
        raise DependencyError("ffprobe was not found on PATH")

    ffmpeg = Path(ffmpeg_name)
    ffprobe = Path(ffprobe_name)
    ffmpeg_version = _version_line(ffmpeg, "ffmpeg")
    ffprobe_version = _version_line(ffprobe, "ffprobe")
    filters = _tool_output([str(ffmpeg), "-hide_banner", "-filters"])
    for filter_name in ("blackdetect", "silencedetect"):
        if not re.search(rf"\b{filter_name}\b", filters):
            raise DependencyError(f"ffmpeg filter is unavailable: {filter_name}")
    mov_help = _tool_output([str(ffmpeg), "-hide_banner", "-h", "demuxer=mov"])
    for option in ("enable_drefs", "use_absolute_path"):
        if option not in mov_help:
            raise DependencyError(f"MOV demuxer option is unavailable: {option}")

    return Toolchain(
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
        versions=ToolVersions(
            ffmpeg_version=ffmpeg_version,
            ffprobe_version=ffprobe_version,
            capabilities=["blackdetect", "silencedetect", "mov"],
        ),
    )
