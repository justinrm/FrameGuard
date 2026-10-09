from __future__ import annotations

import json
from pathlib import Path

from frameguard.models import ProcessResult, ScanConfig, Toolchain, ToolVersions
from frameguard.scanner import scan


def test_metadata_scan_is_useful_but_explicitly_incomplete(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"read-only-test-input")
    payload = {
        "format": {"format_name": "mov,mp4", "start_time": "0", "duration": "1"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 320,
                "height": 240,
                "avg_frame_rate": "30/1",
                "disposition": {"default": 1, "attached_pic": 0},
            }
        ],
    }

    def runner(_spec: object) -> ProcessResult:
        return ProcessResult(0, json.dumps(payload).encode(), b"")

    tools = Toolchain(
        Path("ffmpeg"),
        Path("ffprobe"),
        ToolVersions("ffmpeg version 9.0.2", "ffprobe version 9.0.2", ["mov"]),
    )
    report = scan(media, ScanConfig(), runner=runner, tools=tools)

    assert report.media_metadata is not None
    assert report.media_metadata.selected_video_index == 0
    assert report.overall_status == "incomplete"
    assert next(check for check in report.checks if check.check_id == "black").reason_code == (
        "feature_not_implemented"
    )
    assert next(check for check in report.checks if check.check_id == "silence").reason_code == (
        "no_audio"
    )


def test_missing_input_is_controlled_incomplete(tmp_path: Path) -> None:
    tools = Toolchain(Path("ffmpeg"), Path("ffprobe"), ToolVersions())
    report = scan(tmp_path / "missing.mp4", ScanConfig(), tools=tools)

    assert report.overall_status == "incomplete"
    assert report.media_metadata is None
    assert any(diagnostic.code == "input_unavailable" for diagnostic in report.diagnostics)


def test_audio_only_probe_is_incomplete(tmp_path: Path) -> None:
    media = tmp_path / "audio.mp4"
    media.write_bytes(b"audio-only")
    payload = {
        "format": {"format_name": "mov,mp4"},
        "streams": [
            {
                "index": 0,
                "codec_type": "audio",
                "codec_name": "aac",
                "disposition": {"default": 1},
            }
        ],
    }

    def runner(_spec: object) -> ProcessResult:
        return ProcessResult(0, json.dumps(payload).encode(), b"")

    report = scan(
        media,
        ScanConfig(),
        runner=runner,
        tools=Toolchain(Path("ffmpeg"), Path("ffprobe"), ToolVersions()),
    )
    assert report.overall_status == "incomplete"
    assert report.media_metadata is None
    assert any(check.check_id == "probe" and check.status == "failed" for check in report.checks)
