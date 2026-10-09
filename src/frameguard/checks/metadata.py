from __future__ import annotations

from fractions import Fraction

from ..models import CheckResult, Finding, MediaMetadata, ScanConfig

_FPS_TOLERANCE = Fraction(1, 1000)


def _video(metadata: MediaMetadata):
    return next(
        (stream for stream in metadata.streams if stream.index == metadata.selected_video_index),
        None,
    )


def check_resolution(
    metadata: MediaMetadata, config: ScanConfig
) -> tuple[CheckResult, list[Finding]]:
    if config.expect_width is None and config.expect_height is None:
        return CheckResult(
            "resolution", "skipped", reason_code="not_configured", required=False
        ), []
    video = _video(metadata)
    actual = {
        "width": None if video is None else video.width,
        "height": None if video is None else video.height,
    }
    expected = {
        key: value
        for key, value in (("width", config.expect_width), ("height", config.expect_height))
        if value is not None
    }
    if any(actual[key] is None for key in expected):
        return (
            CheckResult("resolution", "failed", reason_code="unavailable", required=True),
            [],
        )
    if any(actual[key] != value for key, value in expected.items()):
        return CheckResult("resolution", "completed", selected_stream_index=video.index), [
            Finding(
                code="RESOLUTION_MISMATCH",
                severity="critical",
                title="Coded resolution mismatch",
                explanation=(
                    "Compared coded width and height. Display rotation does not "
                    "change those coded dimensions."
                ),
                check_id="resolution",
                stream_index=video.index,
                actual=actual,
                expected=expected,
            )
        ]
    return CheckResult("resolution", "completed", selected_stream_index=video.index), []


def check_frame_rate(
    metadata: MediaMetadata, config: ScanConfig
) -> tuple[CheckResult, list[Finding]]:
    if config.expect_fps is None:
        return CheckResult(
            "frame_rate", "skipped", reason_code="not_configured", required=False
        ), []
    video = _video(metadata)
    actual = None if video is None else video.parsed_avg_frame_rate
    if actual is None:
        return CheckResult("frame_rate", "failed", reason_code="unavailable", required=True), []
    if abs(actual - config.expect_fps) <= _FPS_TOLERANCE:
        return CheckResult("frame_rate", "completed", selected_stream_index=video.index), []
    return CheckResult("frame_rate", "completed", selected_stream_index=video.index), [
        Finding(
            code="FPS_MISMATCH",
            severity="critical",
            title="Reported frame rate mismatch",
            explanation="Compared avg_frame_rate only. This is not a cadence or VFR diagnosis.",
            check_id="frame_rate",
            stream_index=video.index,
            actual=str(video.avg_frame_rate),
            expected=config.expect_fps_input or str(config.expect_fps),
        )
    ]


def check_audio_presence(
    metadata: MediaMetadata, config: ScanConfig
) -> tuple[CheckResult, list[Finding]]:
    present = any(stream.codec_type == "audio" for stream in metadata.streams)
    if present:
        return CheckResult("audio_presence", "completed"), []
    if config.require_audio:
        return CheckResult("audio_presence", "completed"), [
            Finding(
                code="AUDIO_REQUIRED_MISSING",
                severity="critical",
                title="Required audio missing",
                explanation="No audio stream is present in the inventory.",
                check_id="audio_presence",
            )
        ]
    return CheckResult("audio_presence", "completed"), [
        Finding(
            code="AUDIO_ABSENT",
            severity="info",
            title="Audio absent",
            explanation="No audio stream is present. Silence detection does not apply.",
            check_id="audio_presence",
        )
    ]
