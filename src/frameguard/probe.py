from __future__ import annotations

import json
import math
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

from .models import (
    Diagnostic,
    MediaMetadata,
    ProbeResult,
    ProcessResult,
    ProcessSpec,
    StreamMetadata,
    Timeline,
    Toolchain,
)

Runner = Callable[[ProcessSpec], ProcessResult]


def _finite_float(value: object, *, nonnegative: bool = False) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or (nonnegative and parsed < 0):
        return None
    return parsed


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _nonnegative_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _rate(value: object) -> tuple[str | None, Fraction | None]:
    if not isinstance(value, str) or not value:
        return None, None
    try:
        parsed = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return value, None
    return value, parsed if parsed > 0 else None


def normalize_probe(payload: dict) -> MediaMetadata:
    streams_payload = payload.get("streams")
    if not isinstance(streams_payload, list):
        raise ValueError("probe streams must be an array")

    indexes: set[int] = set()
    streams: list[StreamMetadata] = []
    for raw in streams_payload:
        if not isinstance(raw, dict):
            raise ValueError("probe stream must be an object")
        index = raw.get("index")
        codec_type = raw.get("codec_type")
        if not isinstance(index, int) or not isinstance(codec_type, str):
            raise ValueError("probe stream identity is malformed")
        if index in indexes:
            raise ValueError(f"duplicate stream index: {index}")
        indexes.add(index)

        disposition = raw.get("disposition")
        disposition = disposition if isinstance(disposition, dict) else {}
        average_text, average = _rate(raw.get("avg_frame_rate"))
        real_rate_text, _ = _rate(raw.get("r_frame_rate"))
        rotation = None
        rotation_source = None
        side_data = raw.get("side_data_list")
        if isinstance(side_data, list):
            for item in side_data:
                if isinstance(item, dict):
                    candidate = _finite_float(item.get("rotation"))
                    if candidate is not None:
                        rotation = candidate
                        rotation_source = "display_matrix"
                        break
        tags = raw.get("tags")
        if rotation is None and isinstance(tags, dict):
            candidate = _finite_float(tags.get("rotate"))
            if candidate is not None:
                rotation = candidate
                rotation_source = "rotate_tag"

        streams.append(
            StreamMetadata(
                index=index,
                codec_type=codec_type,
                codec_name=raw.get("codec_name")
                if isinstance(raw.get("codec_name"), str)
                else None,
                disposition_default=bool(disposition.get("default", 0)),
                attached_pic=bool(disposition.get("attached_pic", 0)),
                width=_positive_int(raw.get("width")),
                height=_positive_int(raw.get("height")),
                pixel_format=raw.get("pix_fmt") if isinstance(raw.get("pix_fmt"), str) else None,
                avg_frame_rate=average_text,
                r_frame_rate=real_rate_text,
                parsed_avg_frame_rate=average,
                start_time_seconds=_finite_float(raw.get("start_time")),
                duration_seconds=_finite_float(raw.get("duration"), nonnegative=True),
                time_base=raw.get("time_base") if isinstance(raw.get("time_base"), str) else None,
                rotation_degrees=rotation,
                rotation_source=rotation_source,
                sample_aspect_ratio=(
                    raw.get("sample_aspect_ratio")
                    if isinstance(raw.get("sample_aspect_ratio"), str)
                    else None
                ),
                display_aspect_ratio=(
                    raw.get("display_aspect_ratio")
                    if isinstance(raw.get("display_aspect_ratio"), str)
                    else None
                ),
                sample_rate_hz=_positive_int(raw.get("sample_rate")),
                channels=_positive_int(raw.get("channels")),
                channel_layout=(
                    raw.get("channel_layout")
                    if isinstance(raw.get("channel_layout"), str)
                    else None
                ),
            )
        )

    format_payload = payload.get("format")
    format_payload = format_payload if isinstance(format_payload, dict) else {}
    return MediaMetadata(
        format_name=(
            format_payload.get("format_name")
            if isinstance(format_payload.get("format_name"), str)
            else None
        ),
        duration_seconds=_finite_float(format_payload.get("duration"), nonnegative=True),
        size_bytes=_nonnegative_int(format_payload.get("size")),
        bit_rate_bps=_nonnegative_int(format_payload.get("bit_rate")),
        start_time_seconds=_finite_float(format_payload.get("start_time")),
        streams=streams,
    )


def choose_streams(metadata: MediaMetadata) -> MediaMetadata:
    videos = [
        stream
        for stream in metadata.streams
        if stream.codec_type == "video" and stream.codec_name and not stream.attached_pic
    ]
    if not videos:
        raise ValueError("no real video stream")
    audios = [stream for stream in metadata.streams if stream.codec_type == "audio"]

    def choose(candidates: list[StreamMetadata]) -> StreamMetadata | None:
        if not candidates:
            return None
        defaults = [stream for stream in candidates if stream.disposition_default]
        return min(defaults or candidates, key=lambda stream: stream.index)

    video = choose(videos)
    audio = choose(audios)
    assert video is not None
    metadata.selected_video_index = video.index
    metadata.selected_audio_index = audio.index if audio else None
    selected = {video.index}
    if audio:
        selected.add(audio.index)
    metadata.uninspected_stream_indexes = sorted(
        stream.index for stream in metadata.streams if stream.index not in selected
    )
    metadata.selection_reason = "default-disposition real video/audio, then lowest absolute index"
    return metadata


def choose_timeline(metadata: MediaMetadata) -> Timeline:
    if metadata.start_time_seconds is not None and math.isfinite(metadata.start_time_seconds):
        return Timeline(
            basis="media_relative",
            origin_seconds=metadata.start_time_seconds,
            origin_source="format_start_time",
        )

    selected = {
        index
        for index in (metadata.selected_video_index, metadata.selected_audio_index)
        if index is not None
    }
    starts = [stream.start_time_seconds for stream in metadata.streams if stream.index in selected]
    if len(starts) == len(selected) and starts and all(value is not None for value in starts):
        return Timeline(
            basis="media_relative",
            origin_seconds=min(value for value in starts if value is not None),
            origin_source="selected_stream_starts",
        )
    return Timeline(
        basis="source_pts",
        origin_seconds=None,
        origin_source="unknown",
        limitations=["timestamps retain source PTS because no common origin is known"],
    )


def probe_media(path: Path, tools: Toolchain, runner: Runner) -> ProbeResult:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return ProbeResult(
            None,
            [Diagnostic("input_unavailable", f"input is unavailable: {path.name}", "probe")],
        )
    if not resolved.is_file():
        return ProbeResult(
            None,
            [Diagnostic("input_not_regular", f"input is not a regular file: {path.name}", "probe")],
        )

    entries = (
        "format=format_name,start_time,duration,size,bit_rate:"
        "stream=index,codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,"
        "r_frame_rate,time_base,start_time,duration,sample_aspect_ratio,"
        "display_aspect_ratio,sample_rate,channels,channel_layout:"
        "stream_disposition=default,attached_pic:"
        "stream_tags=rotate:"
        "stream_side_data=rotation"
    )
    result = runner(
        ProcessSpec(
            argv=[
                str(tools.ffprobe_path),
                "-v",
                "error",
                "-f",
                "mov",
                "-protocol_whitelist",
                "file",
                "-enable_drefs",
                "0",
                "-use_absolute_path",
                "0",
                "-show_format",
                "-show_streams",
                "-show_entries",
                entries,
                "-of",
                "json",
                str(resolved),
            ],
            timeout_seconds=30,
            stdout_limit_bytes=8 * 1024 * 1024,
            diagnostic_limit_bytes=1024 * 1024,
            line_limit_bytes=64 * 1024,
        )
    )
    if (
        result.returncode != 0
        or result.timed_out
        or result.output_limit_exceeded
        or result.line_limit_exceeded
    ):
        return ProbeResult(
            None,
            [Diagnostic("probe_failed", f"ffprobe could not inspect {path.name}", "probe")],
        )
    try:
        payload = json.loads(result.stdout)
        metadata = choose_streams(normalize_probe(payload))
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return ProbeResult(
            None,
            [Diagnostic("probe_malformed", f"invalid media inventory: {error}", "probe")],
        )
    return ProbeResult(metadata)
