from __future__ import annotations

import hashlib
from pathlib import Path

from frameguard.probe import probe_media
from frameguard.process import discover_tools, run_process


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_actual_probe_inventory_rotation_and_source_preservation(
    media_fixtures: dict[str, Path],
) -> None:
    tools = discover_tools()

    for path in media_fixtures.values():
        before = sha256(path)
        result = probe_media(path, tools, run_process)
        assert result.metadata is not None, result.diagnostics
        assert sha256(path) == before

    baseline = probe_media(media_fixtures["baseline"], tools, run_process).metadata
    assert baseline is not None
    assert baseline.selected_video_index == 0
    assert baseline.selected_audio_index == 1
    assert baseline.streams[0].avg_frame_rate == "30000/1001"

    video_only = probe_media(media_fixtures["video_only"], tools, run_process).metadata
    assert video_only is not None
    assert video_only.selected_audio_index is None

    rotated = probe_media(media_fixtures["rotated"], tools, run_process).metadata
    assert rotated is not None
    assert rotated.streams[0].width == 320
    assert rotated.streams[0].height == 240
    assert rotated.streams[0].rotation_degrees == 90
