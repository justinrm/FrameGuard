from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from frameguard.models import (
    DependencyError,
    ProcessResult,
    ScanConfig,
    Toolchain,
    ToolVersions,
    exit_code,
)
from frameguard.scanner import scan


def test_video_only_probe_can_pass(tmp_path: Path) -> None:
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
    assert report.overall_status == "pass"
    assert next(check for check in report.checks if check.check_id == "black").status == "completed"
    assert next(check for check in report.checks if check.check_id == "silence").reason_code == (
        "no_audio"
    )
    assert any(finding.code == "AUDIO_ABSENT" for finding in report.findings)


def test_missing_tools_are_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"read-only-test-input")

    def missing() -> Toolchain:
        raise DependencyError("ffmpeg is required")

    monkeypatch.setattr("frameguard.scanner.discover_tools", missing)
    report = scan(media, ScanConfig())

    assert report.overall_status == "incomplete"
    dependencies = next(check for check in report.checks if check.check_id == "dependencies")
    assert dependencies.reason_code == "dependency_error"


def test_changed_input_stays_incomplete(tmp_path: Path) -> None:
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
        media.write_bytes(media.read_bytes() + b"x")
        return ProcessResult(0, json.dumps(payload).encode(), b"")

    report = scan(
        media,
        ScanConfig(),
        runner=runner,
        tools=Toolchain(Path("ffmpeg"), Path("ffprobe"), ToolVersions()),
    )

    assert report.overall_status == "incomplete"
    assert any(diagnostic.code == "input_changed" for diagnostic in report.diagnostics)
    assert next(check for check in report.checks if check.check_id == "probe").status == "completed"


def test_directory_and_fifo_are_not_regular_files(tmp_path: Path) -> None:
    folder = tmp_path / "clip.mp4"
    folder.mkdir()
    directory = scan(folder, ScanConfig())
    assert directory.overall_status == "incomplete"
    assert directory.checks[0].reason_code == "input_not_regular"
    assert exit_code(directory) == 2

    pipe = tmp_path / "pipe.mp4"
    os.mkfifo(pipe)
    fifo = scan(pipe, ScanConfig())
    assert fifo.overall_status == "incomplete"
    assert fifo.checks[0].reason_code == "input_not_regular"
    assert exit_code(fifo) == 2


def test_missing_input_is_controlled_incomplete(tmp_path: Path) -> None:
    tools = Toolchain(Path("ffmpeg"), Path("ffprobe"), ToolVersions())
    report = scan(tmp_path / "missing.mp4", ScanConfig(), tools=tools)

    assert report.overall_status == "incomplete"
    assert report.media_metadata is None
    assert any(diagnostic.code == "input_unavailable" for diagnostic in report.diagnostics)


def test_detector_failure_keeps_other_results_incomplete(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"read-only-test-input")
    payload = {
        "format": {"format_name": "mov,mp4", "start_time": "0"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 320,
                "height": 240,
                "avg_frame_rate": "30/1",
                "disposition": {"default": 1, "attached_pic": 0},
            },
            {"index": 1, "codec_type": "audio", "codec_name": "aac", "disposition": {"default": 1}},
        ],
    }

    def runner(spec: object) -> ProcessResult:
        argv = getattr(spec, "argv", [])
        if any("blackdetect" in part for part in argv):
            callback = getattr(spec, "event_callback", None)
            if callback:
                callback("[h264 @ 0x1] Error while decoding MB")
            return ProcessResult(0, b"", b"")
        return ProcessResult(0, json.dumps(payload).encode(), b"")

    report = scan(
        media,
        ScanConfig(expect_width=100),
        runner=runner,
        tools=Toolchain(Path("ffmpeg"), Path("ffprobe"), ToolVersions()),
    )
    assert report.overall_status == "incomplete"
    assert any(finding.code == "RESOLUTION_MISMATCH" for finding in report.findings)
    assert next(check for check in report.checks if check.check_id == "black").status == "failed"
    assert (
        next(check for check in report.checks if check.check_id == "silence").status == "completed"
    )


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
