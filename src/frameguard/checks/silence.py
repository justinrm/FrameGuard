from __future__ import annotations

import math
import re
from collections.abc import Callable

from ..models import (
    CheckResult,
    Diagnostic,
    Finding,
    Interval,
    MediaMetadata,
    ProcessResult,
    ProcessSpec,
    ScanConfig,
    Timeline,
    Toolchain,
)

Runner = Callable[[ProcessSpec], ProcessResult]
_START = re.compile(r"\[Parsed_silencedetect_\d+ @ \S+\] silence_start:\s*(?P<start>\S+)")
_END = re.compile(
    r"\[Parsed_silencedetect_\d+ @ \S+\] silence_end:\s*(?P<end>\S+)"
    r"\s*\|\s*silence_duration:\s*(?P<duration>\S+)"
)
_DECODE = re.compile(r"error while decoding|invalid data found|corrupt|decode error", re.IGNORECASE)


class SilenceParser:
    def __init__(self) -> None:
        self.events: list[tuple[float, float, float]] = []
        self.errors: list[str] = []
        self.decode_error_detected = False
        self._start: float | None = None

    def feed(self, line: str) -> None:
        if _DECODE.search(line):
            self.decode_error_detected = True
        if "Parsed_silencedetect_" not in line or "silence_" not in line:
            return
        start_match = _START.search(line)
        end_match = _END.search(line)
        if start_match:
            if self._start is not None:
                self.errors.append("duplicate silence start")
                return
            try:
                value = float(start_match.group("start"))
            except ValueError:
                self.errors.append("malformed attributed silence event")
                return
            if not math.isfinite(value):
                self.errors.append("nonfinite silence event")
            else:
                self._start = value
            return
        if end_match is None:
            self.errors.append("malformed attributed silence event")
            return
        try:
            end = float(end_match.group("end"))
            duration = float(end_match.group("duration"))
        except ValueError:
            self.errors.append("malformed attributed silence event")
            return
        if (
            self._start is None
            or not math.isfinite(end)
            or not math.isfinite(duration)
            or end < self._start
            or abs((end - self._start) - duration) > 0.01
        ):
            self.errors.append("invalid silence end")
        else:
            self.events.append((self._start, end, duration))
        self._start = None

    def finish(
        self, process: ProcessResult, timeline: Timeline
    ) -> tuple[list[Interval], list[Diagnostic]]:
        if self._start is not None:
            self.errors.append("unclosed silence")
        failed = _failed(process) or bool(self.errors) or self.decode_error_detected
        diagnostics = (
            [Diagnostic("silence_incomplete", "silence detection did not complete", "silence")]
            if failed
            else []
        )
        origin = timeline.origin_seconds if timeline.basis == "media_relative" else None
        intervals = []
        for start, end, duration in self.events:
            shown_start, shown_end = (
                (start, end) if origin is None else (start - origin, end - origin)
            )
            intervals.append(Interval(shown_start, shown_end, duration, start, end))
        return intervals, diagnostics


def detect_silence(
    path,
    metadata: MediaMetadata,
    config: ScanConfig,
    timeline: Timeline,
    tools: Toolchain,
    runner: Runner,
) -> tuple[CheckResult, list[Finding]]:
    index = metadata.selected_audio_index
    if index is None:
        return (
            CheckResult(
                "silence",
                "skipped",
                reason_code="no_audio",
                reason="selected media has no audio stream",
                required=False,
            ),
            [],
        )
    parser = SilenceParser()
    result = runner(
        ProcessSpec(
            argv=[
                str(tools.ffmpeg_path),
                "-nostdin",
                "-hide_banner",
                "-nostats",
                "-loglevel",
                "info",
                "-xerror",
                "-copyts",
                "-noautorotate",
                "-f",
                "mov",
                "-protocol_whitelist",
                "file",
                "-enable_drefs",
                "0",
                "-use_absolute_path",
                "0",
                "-i",
                str(path),
                "-map",
                f"0:{index}",
                "-vn",
                "-af",
                (
                    f"silencedetect=n={config.silence_noise_db}dB:"
                    f"d={config.silence_min_duration_seconds}:mono=false"
                ),
                "-f",
                "null",
                "-",
            ],
            timeout_seconds=config.analysis_timeout_seconds,
            stdout_limit_bytes=1024 * 1024,
            diagnostic_limit_bytes=1024 * 1024,
            line_limit_bytes=64 * 1024,
            event_callback=parser.feed,
        )
    )
    intervals, diagnostics = parser.finish(result, timeline)
    failed = bool(diagnostics)
    findings = [
        Finding(
            code="SILENCE_INTERVAL",
            severity="warning",
            title="Silence interval",
            explanation="Native silencedetect evidence for all channels collectively.",
            check_id="silence",
            stream_index=index,
            interval=interval,
            provisional=failed,
            human_review_recommended=True,
        )
        for interval in intervals
    ]
    return (
        CheckResult(
            "silence",
            "failed" if failed else "completed",
            reason_code="detector_failed" if failed else None,
            selected_stream_index=index,
            diagnostics=diagnostics,
            required=True,
        ),
        findings,
    )


def _failed(process: ProcessResult) -> bool:
    return (
        process.returncode != 0
        or process.timed_out
        or process.cancelled
        or process.output_limit_exceeded
        or process.line_limit_exceeded
    )
