from fractions import Fraction

import pytest

from frameguard.models import MediaMetadata, StreamMetadata
from frameguard.probe import choose_streams, choose_timeline, normalize_probe


def stream(index: int, kind: str, **values: object) -> dict[str, object]:
    return {
        "index": index,
        "codec_type": kind,
        "codec_name": "h264" if kind == "video" else "aac",
        **values,
    }


def test_normalization_keeps_unknowns_and_rational_rates() -> None:
    metadata = normalize_probe(
        {
            "format": {"format_name": "mov,mp4", "start_time": "0.0"},
            "streams": [
                stream(
                    0,
                    "video",
                    width=320,
                    height=240,
                    avg_frame_rate="30000/1001",
                    r_frame_rate="30/1",
                    disposition={"default": 1, "attached_pic": 0},
                    side_data_list=[{"rotation": 90}],
                ),
                stream(1, "audio", avg_frame_rate="0/0"),
            ],
        }
    )

    assert metadata.streams[0].parsed_avg_frame_rate == Fraction(30_000, 1_001)
    assert metadata.streams[0].rotation_degrees == 90
    assert metadata.streams[0].width == 320
    assert metadata.streams[1].parsed_avg_frame_rate is None
    assert metadata.duration_seconds is None


def test_duplicate_or_malformed_stream_identity_fails() -> None:
    payload = {"streams": [stream(0, "video"), stream(0, "audio")]}
    with pytest.raises(ValueError, match="duplicate"):
        normalize_probe(payload)
    with pytest.raises(ValueError, match="streams"):
        normalize_probe({"streams": "bad"})


def test_selection_prefers_defaults_and_excludes_attached_picture() -> None:
    metadata = MediaMetadata(
        streams=[
            StreamMetadata(4, "video", "mjpeg", attached_pic=True),
            StreamMetadata(2, "video", "h264"),
            StreamMetadata(1, "video", "h264", disposition_default=True),
            StreamMetadata(7, "audio", "aac"),
            StreamMetadata(3, "audio", "aac", disposition_default=True),
        ]
    )

    selected = choose_streams(metadata)

    assert selected.selected_video_index == 1
    assert selected.selected_audio_index == 3
    assert selected.uninspected_stream_indexes == [2, 4, 7]


def test_timeline_uses_one_common_origin_or_raw_source_pts() -> None:
    format_origin = MediaMetadata(
        start_time_seconds=-0.25,
        streams=[
            StreamMetadata(0, "video", "h264", start_time_seconds=-0.25),
            StreamMetadata(1, "audio", "aac", start_time_seconds=0),
        ],
        selected_video_index=0,
        selected_audio_index=1,
    )
    assert choose_timeline(format_origin).origin_seconds == -0.25

    selected_starts = MediaMetadata(
        streams=[
            StreamMetadata(0, "video", "h264", start_time_seconds=2),
            StreamMetadata(1, "audio", "aac", start_time_seconds=2.5),
        ],
        selected_video_index=0,
        selected_audio_index=1,
    )
    timeline = choose_timeline(selected_starts)
    assert timeline.origin_seconds == 2
    assert timeline.origin_source == "selected_stream_starts"

    unknown = MediaMetadata(
        streams=[
            StreamMetadata(0, "video", "h264"),
            StreamMetadata(1, "audio", "aac", start_time_seconds=2.5),
        ],
        selected_video_index=0,
        selected_audio_index=1,
    )
    assert choose_timeline(unknown).basis == "source_pts"
    assert choose_timeline(unknown).origin_seconds is None
