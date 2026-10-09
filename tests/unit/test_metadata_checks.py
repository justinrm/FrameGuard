from fractions import Fraction

from frameguard.checks.metadata import check_audio_presence, check_frame_rate, check_resolution
from frameguard.models import MediaMetadata, ScanConfig, StreamMetadata


def media() -> MediaMetadata:
    return MediaMetadata(
        streams=[
            StreamMetadata(
                0,
                "video",
                "h264",
                width=1920,
                height=1080,
                avg_frame_rate="30000/1001",
                parsed_avg_frame_rate=Fraction(30000, 1001),
                rotation_degrees=90,
            )
        ],
        selected_video_index=0,
    )


def test_rotated_coded_dimensions_still_mismatch() -> None:
    result, findings = check_resolution(media(), ScanConfig(expect_width=1080, expect_height=1920))
    assert result.status == "completed"
    assert findings[0].code == "RESOLUTION_MISMATCH"
    assert findings[0].actual == {"width": 1920, "height": 1080}
    assert "coded" in findings[0].explanation.lower()


def test_resolution_skips_without_expectation_and_fails_when_unknown() -> None:
    skipped, _ = check_resolution(media(), ScanConfig())
    assert skipped.status == "skipped"
    unknown = media()
    unknown.streams[0].width = None
    failed, findings = check_resolution(unknown, ScanConfig(expect_width=1920))
    assert failed.status == "failed"
    assert failed.reason_code == "unavailable"
    assert findings == []


def test_audio_presence_codes() -> None:
    silent = MediaMetadata(streams=[StreamMetadata(0, "video", "h264")], selected_video_index=0)
    required, findings = check_audio_presence(silent, ScanConfig(require_audio=True))
    assert required.status == "completed"
    assert findings[0].code == "AUDIO_REQUIRED_MISSING"
    _optional, info = check_audio_presence(silent, ScanConfig())
    assert info[0].code == "AUDIO_ABSENT"
    with_audio = MediaMetadata(
        streams=[StreamMetadata(0, "video", "h264"), StreamMetadata(2, "audio", "aac")],
        selected_video_index=0,
        selected_audio_index=2,
    )
    present, none = check_audio_presence(with_audio, ScanConfig(require_audio=True))
    assert present.status == "completed"
    assert none == []


def test_frame_rate_tolerance() -> None:
    matched, none = check_frame_rate(media(), ScanConfig(expect_fps=Fraction("29.97")))
    assert matched.status == "completed"
    assert none == []
    _mismatched, findings = check_frame_rate(media(), ScanConfig(expect_fps=Fraction(30)))
    assert findings[0].code == "FPS_MISMATCH"
    boundary = MediaMetadata(
        streams=[
            StreamMetadata(
                0,
                "video",
                "h264",
                parsed_avg_frame_rate=Fraction(30) + Fraction(1, 1000),
                avg_frame_rate="30010/1000",
            )
        ],
        selected_video_index=0,
    )
    ok, empty = check_frame_rate(boundary, ScanConfig(expect_fps=Fraction(30)))
    assert ok.status == "completed"
    assert empty == []
    unknown = media()
    unknown.streams[0].parsed_avg_frame_rate = None
    unknown.streams[0].r_frame_rate = "30/1"
    failed, _ = check_frame_rate(unknown, ScanConfig(expect_fps=Fraction(30)))
    assert failed.reason_code == "unavailable"
    skipped, _ = check_frame_rate(media(), ScanConfig())
    assert skipped.reason_code == "not_configured"
