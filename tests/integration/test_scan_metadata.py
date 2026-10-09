from fractions import Fraction
from pathlib import Path

from frameguard.models import ScanConfig, exit_code
from frameguard.scanner import scan


def _finding(report, code: str):
    return next(item for item in report.findings if item.code == code)


def _check(report, check_id: str):
    return next(item for item in report.checks if item.check_id == check_id)


def test_real_baseline_scan_passes(media_fixtures: dict[str, Path]) -> None:
    report = scan(media_fixtures["baseline"], ScanConfig())

    assert report.media_metadata is not None
    assert report.media_metadata.selected_video_index == 0
    assert report.media_metadata.selected_audio_index == 1
    assert report.overall_status == "pass"
    assert {check.check_id for check in report.checks if check.status == "completed"} >= {
        "black",
        "silence",
    }


def test_required_missing_audio_fails_and_skips_silence(
    media_fixtures: dict[str, Path],
) -> None:
    report = scan(media_fixtures["video_only"], ScanConfig(require_audio=True))

    assert exit_code(report) == 1
    assert _finding(report, "AUDIO_REQUIRED_MISSING").severity == "critical"
    silence = _check(report, "silence")
    assert silence.status == "skipped"
    assert silence.reason_code == "no_audio"


def test_optional_absent_audio_passes(media_fixtures: dict[str, Path]) -> None:
    report = scan(media_fixtures["video_only"], ScanConfig())

    assert exit_code(report) == 0
    assert _finding(report, "AUDIO_ABSENT").severity == "info"
    assert _check(report, "silence").reason_code == "no_audio"


def test_integer_fps_mismatches_rational_baseline(media_fixtures: dict[str, Path]) -> None:
    report = scan(
        media_fixtures["baseline"],
        ScanConfig(expect_fps=Fraction(30), expect_fps_input="30"),
    )

    assert exit_code(report) == 1
    assert _finding(report, "FPS_MISMATCH").severity == "critical"


def test_rotated_copy_still_mismatches_portrait_coded_size(
    media_fixtures: dict[str, Path],
) -> None:
    report = scan(media_fixtures["rotated"], ScanConfig(expect_width=240, expect_height=320))

    assert report.media_metadata is not None
    video = report.media_metadata.streams[report.media_metadata.selected_video_index]
    assert video.rotation_degrees == 90
    assert exit_code(report) == 1
    finding = _finding(report, "RESOLUTION_MISMATCH")
    assert finding.actual == {"width": 320, "height": 240}
    assert finding.expected == {"width": 240, "height": 320}
