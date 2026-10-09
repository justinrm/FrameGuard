from pathlib import Path

from frameguard.checks.silence import SilenceParser, detect_silence
from frameguard.models import (
    MediaMetadata,
    ProcessResult,
    ScanConfig,
    StreamMetadata,
    Timeline,
    Toolchain,
    ToolVersions,
)


def test_paired_silence_event() -> None:
    parser = SilenceParser()
    parser.feed("[Parsed_silencedetect_0 @ 0x1] silence_start: 1")
    parser.feed("[Parsed_silencedetect_0 @ 0x1] silence_end: 4 | silence_duration: 3")
    intervals, diagnostics = parser.finish(
        ProcessResult(0, b"", b""),
        Timeline("media_relative", 0.0, "format_start_time"),
    )
    assert diagnostics == []
    assert intervals[0].duration_seconds == 3


def test_unmatched_and_decode_error_fail() -> None:
    parser = SilenceParser()
    parser.feed("[Parsed_silencedetect_0 @ 0x1] silence_end: 3 | silence_duration: 2")
    _, diagnostics = parser.finish(
        ProcessResult(0, b"", b""), Timeline("source_pts", None, "unknown")
    )
    assert diagnostics

    sticky = SilenceParser()
    sticky.feed("[aac @ 0x1] Error while decoding")
    sticky.feed("[Parsed_silencedetect_0 @ 0x1] silence_start: 1")
    sticky.feed("[Parsed_silencedetect_0 @ 0x1] silence_end: 4 | silence_duration: 3")
    intervals, failed = sticky.finish(
        ProcessResult(0, b"", b""), Timeline("source_pts", None, "unknown")
    )
    assert sticky.decode_error_detected
    assert intervals and failed


def test_no_audio_skips_without_running(tmp_path: Path) -> None:
    called = False

    def runner(_spec: object) -> ProcessResult:
        nonlocal called
        called = True
        return ProcessResult(0, b"", b"")

    result, findings = detect_silence(
        tmp_path / "none.mp4",
        MediaMetadata(streams=[StreamMetadata(0, "video", "h264")], selected_video_index=0),
        ScanConfig(),
        Timeline("source_pts", None, "unknown"),
        Toolchain(Path("ffmpeg"), Path("ffprobe"), ToolVersions()),
        runner,
    )
    assert result.status == "skipped"
    assert result.reason_code == "no_audio"
    assert result.required is False
    assert findings == []
    assert called is False
