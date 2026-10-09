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
_EVENT = re.compile(
    r"\[Parsed_blackdetect_\d+ @ \S+\] black_start:(?P<start>\S+) "
    r"black_end:(?P<end>\S+) black_duration:(?P<duration>\S+)"
)
_DECODE = re.compile(r"error while decoding|invalid data found|corrupt|decode error", re.IGNORECASE)
_EOF = (
    "blackdetect closes trailing black at the last picture PTS and can miss "
    "a threshold-edge interval at end of file"
)


class BlackParser:
    def __init__(self) -> None:
        self.events: list[tuple[float, float, float]] = []
        self.errors: list[str] = []
        self.decode_error_detected = False

    def feed(self, line: str) -> None:
        if _DECODE.search(line):
            self.decode_error_detected = True
        if "Parsed_blackdetect_" not in line or "black_" not in line:
            return
        match = _EVENT.search(line)
        if match is None:
            self.errors.append("malformed attributed black event")
            return
        try:
            values = tuple(float(match.group(name)) for name in ("start", "end", "duration"))
        except ValueError:
            self.errors.append("malformed attributed black event")
            return
        start, end, duration = values
        if not all(math.isfinite(value) for value in values):
            self.errors.append("nonfinite black event")
        elif end < start or abs((end - start) - duration) > 0.01:
            self.errors.append("inconsistent black event")
        else:
            self.events.append((start, end, duration))

    def finish(
        self, process: ProcessResult, timeline: Timeline
    ) -> tuple[list[Interval], list[Diagnostic]]:
        failed = _failed(process) or bool(self.errors) or self.decode_error_detected
        diagnostics = (
            [Diagnostic("black_incomplete", "black detection did not complete", "black")]
            if failed
            else []
        )
        return [_interval(*event, timeline) for event in self.events], diagnostics


def detect_black(
    path,
    metadata: MediaMetadata,
    config: ScanConfig,
    timeline: Timeline,
    tools: Toolchain,
    runner: Runner,
) -> tuple[CheckResult, list[Finding]]:
    index = metadata.selected_video_index
    parser = BlackParser()
    result = runner(
        ProcessSpec(
            argv=_argv(path, index, config, tools),
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
            code="BLACK_INTERVAL",
            severity="warning",
            title="Black interval",
            explanation="Native blackdetect evidence. This is not an editorial judgment.",
            check_id="black",
            stream_index=index,
            interval=interval,
            provisional=failed,
            human_review_recommended=True,
        )
        for interval in intervals
    ]
    return (
        CheckResult(
            "black",
            "failed" if failed else "completed",
            reason_code="detector_failed" if failed else None,
            selected_stream_index=index,
            diagnostics=diagnostics,
            limitations=[] if failed else [_EOF],
        ),
        findings,
    )


def _argv(path, index: int | None, config: ScanConfig, tools: Toolchain) -> list[str]:
    filt = (
        "blackdetect="
        f"d={config.black_min_duration_seconds}:pic_th={config.black_picture_ratio}"
        f":pix_th={config.black_pixel_threshold}"
    )
    return [
        str(tools.ffmpeg_path),
        "-nostdin",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-xerror",
        "-copyts",
        "-noautorotate",
        *_input(path),
        "-map",
        f"0:{index}",
        "-an",
        "-vf",
        filt,
        "-fps_mode",
        "passthrough",
        "-f",
        "null",
        "-",
    ]


def _input(path) -> list[str]:
    return [
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
    ]


def _failed(process: ProcessResult) -> bool:
    return (
        process.returncode != 0
        or process.timed_out
        or process.cancelled
        or process.output_limit_exceeded
        or process.line_limit_exceeded
    )


def _interval(start: float, end: float, duration: float, timeline: Timeline) -> Interval:
    origin = timeline.origin_seconds if timeline.basis == "media_relative" else None
    if origin is None:
        shown_start, shown_end = start, end
    else:
        shown_start, shown_end = start - origin, end - origin
    return Interval(shown_start, shown_end, duration, start, end)
