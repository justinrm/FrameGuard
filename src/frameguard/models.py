from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path


class FrameGuardError(Exception):
    code = "frameguard_error"


class ConfigError(FrameGuardError):
    code = "invalid_configuration"


class DependencyError(FrameGuardError):
    code = "dependency_error"


class OutputError(FrameGuardError):
    code = "output_error"


@dataclass(slots=True)
class ScanConfig:
    expect_width: int | None = None
    expect_height: int | None = None
    expect_fps: Fraction | None = None
    expect_fps_input: str | None = None
    require_audio: bool = False
    black_min_duration_seconds: float = 0.5
    black_picture_ratio: float = 0.98
    black_pixel_threshold: float = 0.10
    silence_min_duration_seconds: float = 2.0
    silence_noise_db: float = -60.0
    analysis_timeout_seconds: float = 600.0


@dataclass(slots=True)
class InputInfo:
    display_name: str
    size_bytes: int | None = None


@dataclass(slots=True)
class StreamMetadata:
    index: int
    codec_type: str
    codec_name: str | None = None
    disposition_default: bool = False
    attached_pic: bool = False
    width: int | None = None
    height: int | None = None
    pixel_format: str | None = None
    avg_frame_rate: str | None = None
    r_frame_rate: str | None = None
    parsed_avg_frame_rate: Fraction | None = None
    start_time_seconds: float | None = None
    duration_seconds: float | None = None
    time_base: str | None = None
    rotation_degrees: float | None = None
    rotation_source: str | None = None
    sample_aspect_ratio: str | None = None
    display_aspect_ratio: str | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    channel_layout: str | None = None


@dataclass(slots=True)
class MediaMetadata:
    format_name: str | None = None
    duration_seconds: float | None = None
    size_bytes: int | None = None
    bit_rate_bps: int | None = None
    start_time_seconds: float | None = None
    streams: list[StreamMetadata] = field(default_factory=list)
    selected_video_index: int | None = None
    selected_audio_index: int | None = None
    selection_reason: str = ""
    uninspected_stream_indexes: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Timeline:
    basis: str
    origin_seconds: float | None
    origin_source: str
    limitations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolVersions:
    ffmpeg_version: str | None = None
    ffprobe_version: str | None = None
    capabilities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Diagnostic:
    code: str
    message: str
    check_id: str | None = None


@dataclass(slots=True)
class CheckResult:
    check_id: str
    status: str
    reason_code: str | None = None
    reason: str | None = None
    required: bool = True
    selected_stream_index: int | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Interval:
    start_seconds: float
    end_seconds: float | None
    duration_seconds: float | None
    raw_start_seconds: float
    raw_end_seconds: float | None
    endpoint_basis: str = "detector_reported"
    endpoint_precision_note: str | None = None


@dataclass(slots=True)
class Finding:
    code: str
    severity: str
    title: str
    explanation: str
    check_id: str
    stream_index: int | None = None
    interval: Interval | None = None
    actual: object = None
    expected: object = None
    provisional: bool = False
    human_review_recommended: bool = False


@dataclass(slots=True)
class ScanReport:
    schema_version: str
    tool_version: str
    input: InputInfo
    media_metadata: MediaMetadata | None
    configuration: dict[str, object]
    timeline: Timeline
    checks: list[CheckResult]
    findings: list[Finding]
    diagnostics: list[Diagnostic]
    overall_status: str
    analysis_duration_seconds: float
    tool_versions: ToolVersions


@dataclass(slots=True)
class ProcessSpec:
    argv: list[str]
    timeout_seconds: float
    stdout_limit_bytes: int
    diagnostic_limit_bytes: int
    line_limit_bytes: int
    event_callback: Callable[[str], None] | None = field(default=None, repr=False)


@dataclass(slots=True)
class ProcessResult:
    returncode: int | None
    stdout: bytes
    diagnostic_tail: bytes
    timed_out: bool = False
    output_limit_exceeded: bool = False
    elapsed_seconds: float = 0.0
    cancelled: bool = False
    line_limit_exceeded: bool = False


@dataclass(slots=True)
class Toolchain:
    ffmpeg_path: Path
    ffprobe_path: Path
    versions: ToolVersions


@dataclass(slots=True)
class ProbeResult:
    metadata: MediaMetadata | None
    diagnostics: list[Diagnostic] = field(default_factory=list)


def _finite_positive(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def validate_config(config: ScanConfig) -> None:
    for name in ("expect_width", "expect_height"):
        value = getattr(config, name)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
        ):
            raise ConfigError(f"{name} must be a positive integer")
    if config.expect_fps is not None and config.expect_fps <= 0:
        raise ConfigError("expect_fps must be positive")
    for name in (
        "black_min_duration_seconds",
        "silence_min_duration_seconds",
        "analysis_timeout_seconds",
    ):
        if not _finite_positive(getattr(config, name)):
            raise ConfigError(f"{name} must be finite and positive")
    if config.silence_min_duration_seconds > 86_400:
        raise ConfigError("silence_min_duration_seconds must not exceed 86400")
    for name in ("black_picture_ratio", "black_pixel_threshold"):
        value = getattr(config, name)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ConfigError(f"{name} must be finite and between 0 and 1")
    if (
        not isinstance(config.silence_noise_db, (int, float))
        or not math.isfinite(config.silence_noise_db)
        or config.silence_noise_db > 0
    ):
        raise ConfigError("silence_noise_db must be finite and at most 0")


def calculate_status(checks: list[CheckResult], findings: list[Finding]) -> str:
    if any(check.required and check.status != "completed" for check in checks):
        return "incomplete"
    severities = {finding.severity for finding in findings if not finding.provisional}
    if "critical" in severities:
        return "fail"
    if "warning" in severities:
        return "warn"
    return "pass"


def exit_code(
    report_or_status: ScanReport | str | None,
    *,
    execution_error: bool = False,
) -> int:
    if execution_error or report_or_status is None:
        return 2
    status = (
        report_or_status.overall_status
        if isinstance(report_or_status, ScanReport)
        else report_or_status
    )
    if status == "fail":
        return 1
    if status == "incomplete":
        return 2
    return 0


def ensure_finite_json(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite JSON number")
    if isinstance(value, dict):
        for item in value.values():
            ensure_finite_json(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            ensure_finite_json(item)
