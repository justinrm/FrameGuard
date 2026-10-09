from __future__ import annotations

import time
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

from . import __version__
from .models import (
    CheckResult,
    DependencyError,
    Diagnostic,
    InputInfo,
    ScanConfig,
    ScanReport,
    Timeline,
    Toolchain,
    ToolVersions,
    calculate_status,
    validate_config,
)
from .probe import Runner, choose_timeline, probe_media
from .process import discover_tools, run_process


def _config_projection(config: ScanConfig) -> dict[str, object]:
    projected = asdict(config)
    rate = projected["expect_fps"]
    if isinstance(rate, Fraction):
        projected["expect_fps"] = str(rate)
    return projected


def _skipped_after(check_id: str, reason_code: str = "prerequisite_failed") -> CheckResult:
    return CheckResult(check_id, "skipped", reason_code=reason_code, required=False)


def _failed_report(
    started: float,
    path: Path,
    config: ScanConfig,
    checks: list[CheckResult],
    diagnostics: list[Diagnostic],
    versions: ToolVersions | None = None,
    size: int | None = None,
) -> ScanReport:
    return ScanReport(
        schema_version="0.1.0",
        tool_version=__version__,
        input=InputInfo(path.name, size),
        media_metadata=None,
        configuration=_config_projection(config),
        timeline=Timeline("source_pts", None, "unknown"),
        checks=checks,
        findings=[],
        diagnostics=diagnostics,
        overall_status=calculate_status(checks, []),
        analysis_duration_seconds=time.monotonic() - started,
        tool_versions=versions or ToolVersions(),
    )


def scan(
    path: Path,
    config: ScanConfig,
    *,
    runner: Runner = run_process,
    tools: Toolchain | None = None,
) -> ScanReport:
    started = time.monotonic()
    validate_config(config)
    try:
        resolved = path.resolve(strict=True)
        initial = resolved.stat()
    except OSError:
        diagnostic = Diagnostic(
            "input_unavailable",
            f"input is unavailable: {path.name}",
            "input_validation",
        )
        checks = [
            CheckResult(
                "input_validation",
                "failed",
                reason_code="input_unavailable",
                diagnostics=[diagnostic],
            ),
            *[
                _skipped_after(check_id)
                for check_id in (
                    "dependencies",
                    "probe",
                    "resolution",
                    "frame_rate",
                    "audio_presence",
                    "black",
                    "silence",
                )
            ],
        ]
        return _failed_report(started, path, config, checks, [diagnostic])
    if not resolved.is_file():
        diagnostic = Diagnostic(
            "input_not_regular",
            f"input is not a regular file: {path.name}",
            "input_validation",
        )
        checks = [
            CheckResult(
                "input_validation",
                "failed",
                reason_code="input_not_regular",
                diagnostics=[diagnostic],
            ),
            *[
                _skipped_after(check_id)
                for check_id in (
                    "dependencies",
                    "probe",
                    "resolution",
                    "frame_rate",
                    "audio_presence",
                    "black",
                    "silence",
                )
            ],
        ]
        return _failed_report(started, path, config, checks, [diagnostic], size=initial.st_size)

    checks = [CheckResult("input_validation", "completed")]
    if tools is None:
        try:
            tools = discover_tools()
        except DependencyError as error:
            diagnostic = Diagnostic(error.code, str(error), "dependencies")
            checks.extend(
                [
                    CheckResult(
                        "dependencies",
                        "failed",
                        reason_code=error.code,
                        diagnostics=[diagnostic],
                    ),
                    *[
                        _skipped_after(check_id)
                        for check_id in (
                            "probe",
                            "resolution",
                            "frame_rate",
                            "audio_presence",
                            "black",
                            "silence",
                        )
                    ],
                ]
            )
            return _failed_report(
                started,
                path,
                config,
                checks,
                [diagnostic],
                size=initial.st_size,
            )
    checks.append(CheckResult("dependencies", "completed"))

    probe = probe_media(resolved, tools, runner)
    if probe.metadata is None:
        checks.extend(
            [
                CheckResult(
                    "probe",
                    "failed",
                    reason_code=probe.diagnostics[0].code if probe.diagnostics else "probe_failed",
                    diagnostics=probe.diagnostics,
                ),
                *[
                    _skipped_after(check_id)
                    for check_id in (
                        "resolution",
                        "frame_rate",
                        "audio_presence",
                        "black",
                        "silence",
                    )
                ],
            ]
        )
        return _failed_report(
            started,
            path,
            config,
            checks,
            probe.diagnostics,
            tools.versions,
            initial.st_size,
        )

    checks.append(CheckResult("probe", "completed"))
    metadata = probe.metadata
    checks.append(
        CheckResult(
            "resolution",
            "failed"
            if config.expect_width is not None or config.expect_height is not None
            else "skipped",
            reason_code=(
                "feature_not_implemented"
                if config.expect_width is not None or config.expect_height is not None
                else "not_configured"
            ),
            required=config.expect_width is not None or config.expect_height is not None,
        )
    )
    checks.append(
        CheckResult(
            "frame_rate",
            "failed" if config.expect_fps is not None else "skipped",
            reason_code="feature_not_implemented"
            if config.expect_fps is not None
            else "not_configured",
            required=config.expect_fps is not None,
        )
    )
    checks.append(
        CheckResult(
            "audio_presence",
            "failed" if config.require_audio else "skipped",
            reason_code="feature_not_implemented" if config.require_audio else "not_configured",
            required=config.require_audio,
        )
    )
    checks.append(
        CheckResult(
            "black",
            "failed",
            reason_code="feature_not_implemented",
            reason="black detection is delivered in Milestone 2",
            selected_stream_index=metadata.selected_video_index,
        )
    )
    checks.append(
        CheckResult(
            "silence",
            "failed" if metadata.selected_audio_index is not None else "skipped",
            reason_code=(
                "feature_not_implemented"
                if metadata.selected_audio_index is not None
                else "no_audio"
            ),
            reason=(
                "silence detection is delivered in Milestone 2"
                if metadata.selected_audio_index is not None
                else "selected media has no audio stream"
            ),
            required=metadata.selected_audio_index is not None,
            selected_stream_index=metadata.selected_audio_index,
        )
    )

    diagnostics: list[Diagnostic] = []
    final = resolved.stat()
    if (
        initial.st_dev,
        initial.st_ino,
        initial.st_size,
        initial.st_mtime_ns,
    ) != (
        final.st_dev,
        final.st_ino,
        final.st_size,
        final.st_mtime_ns,
    ):
        diagnostic = Diagnostic(
            "input_changed",
            "input changed during inspection",
            "input_validation",
        )
        checks[0] = CheckResult(
            "input_validation",
            "failed",
            reason_code="input_changed",
            diagnostics=[diagnostic],
        )
        diagnostics.append(diagnostic)

    status = calculate_status(checks, [])
    return ScanReport(
        schema_version="0.1.0",
        tool_version=__version__,
        input=InputInfo(path.name, initial.st_size),
        media_metadata=metadata,
        configuration=_config_projection(config),
        timeline=choose_timeline(metadata),
        checks=checks,
        findings=[],
        diagnostics=diagnostics,
        overall_status=status,
        analysis_duration_seconds=time.monotonic() - started,
        tool_versions=tools.versions,
    )
