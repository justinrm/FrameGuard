#!/usr/bin/env python3
"""Bounded, disposable FrameGuard M0 experiments. Not product code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

FFMPEG = os.environ.get("FRAMEGUARD_FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FRAMEGUARD_FFPROBE", "ffprobe")
STDOUT_CAP = 32 * 1024 * 1024
DIAGNOSTIC_CAP = 1024 * 1024
LINE_CAP = 64 * 1024
FINDING_CAP = 10_000
COMMAND_LOG: list[dict] = []

BLACK_RE = re.compile(
    r"\b(?:Parsed_)?blackdetect(?:_\d+)?\s*@\s*\S+[^\n]*\bblack_start:"
    r"(?P<start>\S+)\s+black_end:(?P<end>\S+)\s+black_duration:(?P<duration>\S+)"
)
SILENCE_START_RE = re.compile(
    r"\b(?:Parsed_)?silencedetect(?:_\d+)?\s*@\s*\S+[^\n]*\bsilence_start:\s*(?P<start>\S+)"
)
SILENCE_END_RE = re.compile(
    r"\b(?:Parsed_)?silencedetect(?:_\d+)?\s*@\s*\S+[^\n]*\bsilence_end:\s*(?P<end>\S+)"
    r"\s*\|\s*silence_duration:\s*(?P<duration>\S+)"
)
DECODE_ERROR_RE = re.compile(
    r"(error while decoding|invalid data found|corrupt|decode error|error submitting a packet)",
    re.IGNORECASE,
)


class Result(dict):
    @property
    def ok(self) -> bool:
        return (
            self["returncode"] == 0
            and not self["timed_out"]
            and not self["cancelled"]
            and not self["output_limit_exceeded"]
            and not self["line_limit_exceeded"]
        )


def run(
    argv: list[str],
    *,
    timeout: float = 30,
    stdout_cap: int = STDOUT_CAP,
    diagnostic_cap: int = DIAGNOSTIC_CAP,
    line_cap: int = LINE_CAP,
    on_line: Callable[[str], None] | None = None,
    cancel_after: float | None = None,
) -> Result:
    """Run argv-only with concurrent drains and terminate/kill/reap cleanup."""
    env = os.environ.copy()
    env.pop("FFREPORT", None)
    env["AV_LOG_FORCE_NOCOLOR"] = "1"
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=env,
        start_new_session=True,
    )
    stdout = bytearray()
    diagnostic_tail: deque[bytes] = deque()
    diagnostic_size = 0
    flags = {"output": False, "line": False}
    lock = threading.Lock()

    def drain_stdout() -> None:
        assert process.stdout
        while chunk := process.stdout.read(65536):
            with lock:
                room = stdout_cap - len(stdout)
                if room > 0:
                    stdout.extend(chunk[:room])
                if len(chunk) > room:
                    flags["output"] = True

    def drain_stderr() -> None:
        nonlocal diagnostic_size
        assert process.stderr
        pending = bytearray()
        while chunk := process.stderr.read(65536):
            with lock:
                diagnostic_tail.append(chunk)
                diagnostic_size += len(chunk)
                while diagnostic_size > diagnostic_cap and diagnostic_tail:
                    removed = diagnostic_tail.popleft()
                    diagnostic_size -= len(removed)
            pending.extend(chunk)
            while (newline := pending.find(b"\n")) >= 0:
                raw = bytes(pending[:newline])
                del pending[: newline + 1]
                if len(raw) > line_cap:
                    flags["line"] = True
                elif on_line:
                    on_line(raw.decode("utf-8", "replace"))
            if len(pending) > line_cap:
                flags["line"] = True
                pending.clear()
        if pending:
            if len(pending) > line_cap:
                flags["line"] = True
            elif on_line:
                on_line(pending.decode("utf-8", "replace"))

    threads = [
        threading.Thread(target=drain_stdout, daemon=True),
        threading.Thread(target=drain_stderr, daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = cancelled = False
    while process.poll() is None:
        elapsed = time.monotonic() - started
        if cancel_after is not None and elapsed >= cancel_after:
            cancelled = True
            break
        if elapsed >= timeout:
            timed_out = True
            break
        if flags["output"] or flags["line"]:
            break
        time.sleep(0.01)

    if process.poll() is None and (timed_out or cancelled or flags["output"] or flags["line"]):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    else:
        process.wait()
    for thread in threads:
        thread.join(timeout=2)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("pipe drain thread did not finish")

    result = Result(
        argv=argv,
        returncode=process.returncode,
        stdout=bytes(stdout),
        diagnostic_tail=b"".join(diagnostic_tail)[-diagnostic_cap:],
        timed_out=timed_out,
        cancelled=cancelled,
        output_limit_exceeded=flags["output"],
        line_limit_exceeded=flags["line"],
        elapsed_seconds=round(time.monotonic() - started, 6),
    )
    COMMAND_LOG.append(
        {
            "argv": argv,
            "returncode": result["returncode"],
            "timed_out": result["timed_out"],
            "cancelled": result["cancelled"],
            "output_limit_exceeded": result["output_limit_exceeded"],
            "line_limit_exceeded": result["line_limit_exceeded"],
            "stdout_bytes": len(result["stdout"]),
            "diagnostic_tail_bytes": len(result["diagnostic_tail"]),
            "elapsed_seconds": result["elapsed_seconds"],
        }
    )
    return result


def checked(argv: list[str], *, timeout: float = 30) -> Result:
    result = run(argv, timeout=timeout)
    if not result.ok:
        raise RuntimeError(
            f"command failed ({result['returncode']}): {argv!r}\n"
            + result["diagnostic_tail"].decode("utf-8", "replace")[-4000:]
        )
    return result


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def ffmpeg_output(path: Path, *args: str) -> None:
    checked([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args, str(path)], timeout=60)


def probe(path: Path, *, packets: bool = False, frames: bool = False) -> dict:
    argv = [
        FFPROBE,
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
    ]
    if packets:
        argv += [
            "-show_packets",
            "-show_entries",
            "packet=stream_index,pts_time,dts_time,duration_time,flags",
        ]
    elif frames:
        argv += [
            "-show_frames",
            "-show_entries",
            "frame=stream_index,media_type,best_effort_timestamp_time,pkt_duration_time,nb_samples",
        ]
    else:
        argv += [
            "-show_format",
            "-show_streams",
            "-show_entries",
            (
                "format=format_name,start_time,duration,size,bit_rate:"
                "stream=index,codec_type,codec_name,profile,width,height,pix_fmt,"
                "avg_frame_rate,r_frame_rate,time_base,start_time,duration,"
                "sample_rate,channels,channel_layout:"
                "stream_disposition=default,attached_pic:"
                "stream_tags=rotate:"
                "stream_side_data=rotation"
            ),
        ]
    argv += ["-of", "json", str(path)]
    return json.loads(checked(argv).get("stdout", b"{}"))


def choose_streams(payload: dict) -> tuple[int, int | None, list[int]]:
    streams = payload["streams"]
    videos = [
        stream
        for stream in streams
        if stream.get("codec_type") == "video"
        and stream.get("codec_name")
        and not stream.get("disposition", {}).get("attached_pic", 0)
    ]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not videos:
        raise ValueError("no real video")

    def choose(items: list[dict]) -> dict | None:
        if not items:
            return None
        defaults = [item for item in items if item.get("disposition", {}).get("default", 0)]
        return min(defaults or items, key=lambda item: item["index"])

    video = choose(videos)
    audio = choose(audios)
    assert video
    selected = {video["index"]}
    if audio:
        selected.add(audio["index"])
    return (
        video["index"],
        audio["index"] if audio else None,
        [stream["index"] for stream in streams if stream["index"] not in selected],
    )


def detector_argv(path: Path | str, stream_index: int, kind: str) -> list[str]:
    common = [
        FFMPEG,
        "-nostdin",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-xerror",
        "-copyts",
        "-noautorotate",
        "-f",
        "mov",
        "-protocol_whitelist",
        "file",
        "-enable_drefs",
        "0",
        "-use_absolute_path",
        "0",
        "-i",
        str(path),
        "-map",
        f"0:{stream_index}",
    ]
    if kind == "black":
        return common + [
            "-an",
            "-vf",
            "blackdetect=d=0.5:pic_th=0.98:pix_th=0.10",
            "-fps_mode",
            "passthrough",
            "-f",
            "null",
            "-",
        ]
    return common + [
        "-vn",
        "-af",
        "silencedetect=n=-60dB:d=2:mono=false",
        "-f",
        "null",
        "-",
    ]


def parse_events(lines: list[str], kind: str) -> tuple[list[dict], list[str], bool]:
    events: list[dict] = []
    errors: list[str] = []
    decode_error = False
    silence_start: float | None = None
    for line in lines:
        if DECODE_ERROR_RE.search(line):
            decode_error = True
        if kind == "black" and "blackdetect" in line and "black_" in line:
            match = BLACK_RE.search(line)
            if not match:
                errors.append("malformed attributed black event")
                continue
            values = {key: float(value) for key, value in match.groupdict().items()}
            if not all(math.isfinite(value) for value in values.values()):
                errors.append("nonfinite black event")
            elif (
                values["end"] < values["start"]
                or abs((values["end"] - values["start"]) - values["duration"]) > 0.01
            ):
                errors.append("inconsistent black event")
            else:
                events.append(values)
        elif kind == "silence" and "silencedetect" in line and "silence_" in line:
            if match := SILENCE_START_RE.search(line):
                value = float(match.group("start"))
                if silence_start is not None or not math.isfinite(value):
                    errors.append("invalid silence start")
                else:
                    silence_start = value
            elif match := SILENCE_END_RE.search(line):
                end = float(match.group("end"))
                duration = float(match.group("duration"))
                if (
                    silence_start is None
                    or not math.isfinite(end)
                    or not math.isfinite(duration)
                    or end < silence_start
                    or abs((end - silence_start) - duration) > 0.01
                ):
                    errors.append("invalid silence end")
                else:
                    events.append({"start": silence_start, "end": end, "duration": duration})
                silence_start = None
            else:
                errors.append("malformed attributed silence event")
        if len(events) > FINDING_CAP:
            errors.append("finding cap exceeded")
            break
    if silence_start is not None:
        errors.append("unclosed silence")
    return events, errors, decode_error


def detect(path: Path, stream_index: int, kind: str, *, cancel_after: float | None = None) -> dict:
    lines: list[str] = []
    result = run(
        detector_argv(path, stream_index, kind),
        timeout=30,
        on_line=lines.append,
        cancel_after=cancel_after,
    )
    events, parse_errors, decode_error = parse_events(lines, kind)
    complete = result.ok and not parse_errors and not decode_error
    return {
        "argv": result["argv"],
        "returncode": result["returncode"],
        "timed_out": result["timed_out"],
        "cancelled": result["cancelled"],
        "events": events,
        "parse_errors": parse_errors,
        "decode_error_detected": decode_error,
        "complete": complete,
        "event_lines": [
            line
            for line in lines
            if ("blackdetect" in line and "black_" in line)
            or ("silencedetect" in line and "silence_" in line)
        ],
        "diagnostic_tail": result["diagnostic_tail"].decode("utf-8", "replace")[-4000:],
    }


def mp4_boxes(data: bytes, start: int = 0, end: int | None = None, path: tuple[str, ...] = ()):
    end = len(data) if end is None else end
    cursor = start
    containers = {"moov", "trak", "mdia", "minf", "dinf", "stbl", "edts", "dref"}
    while cursor + 8 <= end:
        size, raw_type = struct.unpack_from(">I4s", data, cursor)
        box_type = raw_type.decode("latin1")
        header = 8
        if size == 1:
            size = struct.unpack_from(">Q", data, cursor + 8)[0]
            header = 16
        elif size == 0:
            size = end - cursor
        if size < header or cursor + size > end:
            break
        current = path + (box_type,)
        yield current, cursor, size, header
        if box_type in containers:
            child_start = cursor + header + (8 if box_type == "dref" else 0)
            yield from mp4_boxes(data, child_start, cursor + size, current)
        cursor += size


def edit_lists(path: Path) -> list[dict]:
    data = path.read_bytes()
    found: list[dict] = []
    for box_path, offset, size, header in mp4_boxes(data):
        if box_path[-1] != "elst":
            continue
        body = offset + header
        version = data[body]
        count = struct.unpack_from(">I", data, body + 4)[0]
        cursor = body + 8
        entries = []
        for _ in range(count):
            if version == 1:
                duration, media_time = struct.unpack_from(">Qq", data, cursor)
                cursor += 20
            else:
                duration, media_time = struct.unpack_from(">Ii", data, cursor)
                cursor += 12
            entries.append({"segment_duration": duration, "media_time": media_time})
        found.append(
            {"path": "/".join(box_path), "version": version, "entries": entries, "size": size}
        )
    return found


def patch_negative_ctts(path: Path, shift: int = 4004) -> None:
    data = bytearray(path.read_bytes())
    for box_path, offset, _size, header in mp4_boxes(data):
        if box_path[-1] != "ctts":
            continue
        body = offset + header
        count = struct.unpack_from(">I", data, body + 4)[0]
        data[body] = 1
        for entry in range(count):
            value_offset = body + 8 + entry * 8 + 4
            original = struct.unpack_from(">I", data, value_offset)[0]
            struct.pack_into(">i", data, value_offset, original - shift)
        path.write_bytes(data)
        return
    raise RuntimeError("negative-start fixture has no ctts box")


def timeline(payload: dict, selected: tuple[int, int | None, list[int]]) -> dict:
    format_start = payload.get("format", {}).get("start_time")
    if format_start is not None and math.isfinite(float(format_start)):
        origin = float(format_start)
        return {"basis": "media_relative", "origin": origin, "origin_source": "format_start_time"}
    wanted = {index for index in selected[:2] if index is not None}
    starts = [
        float(stream["start_time"])
        for stream in payload["streams"]
        if stream["index"] in wanted and stream.get("start_time") is not None
    ]
    if len(starts) == len(wanted) and all(math.isfinite(value) for value in starts):
        return {
            "basis": "media_relative",
            "origin": min(starts),
            "origin_source": "selected_stream_starts",
        }
    return {"basis": "source_pts", "origin": None, "origin_source": "unknown"}


def frame_pts_summary(payload: dict) -> dict:
    frames = payload.get("frames", [])
    by_stream: dict[int, list[float]] = {}
    for frame in frames:
        if frame.get("best_effort_timestamp_time") is not None:
            by_stream.setdefault(frame["stream_index"], []).append(
                float(frame["best_effort_timestamp_time"])
            )
    return {
        str(index): {
            "count": len(times),
            "first": times[:5],
            "last": times[-5:],
            "minimum": min(times),
            "maximum": max(times),
        }
        for index, times in by_stream.items()
    }


def contiguous_intervals(states: list[bool], times: list[float], final_end: float) -> list[dict]:
    intervals = []
    start: float | None = None
    for index, state in enumerate(states):
        if state and start is None:
            start = times[index]
        elif not state and start is not None:
            intervals.append(
                {"start": start, "end": times[index], "duration": times[index] - start}
            )
            start = None
    if start is not None:
        intervals.append({"start": start, "end": final_end, "duration": final_end - start})
    return intervals


def video_oracle(path: Path, stream_index: int) -> list[dict]:
    frames = [
        frame
        for frame in probe(path, frames=True).get("frames", [])
        if frame.get("media_type") == "video" and frame.get("stream_index") == stream_index
    ]
    times = [float(frame["best_effort_timestamp_time"]) for frame in frames]
    result = checked(
        [
            FFMPEG,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-copyts",
            "-noautorotate",
            "-f",
            "mov",
            "-protocol_whitelist",
            "file",
            "-enable_drefs",
            "0",
            "-use_absolute_path",
            "0",
            "-i",
            str(path),
            "-map",
            f"0:{stream_index}",
            "-an",
            "-vf",
            "scale=1:1,format=gray",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    samples = result["stdout"]
    if len(samples) != len(times):
        raise RuntimeError(f"video oracle frame mismatch: {len(samples)} != {len(times)}")
    if len(times) > 1:
        final_end = times[-1] + (times[-1] - times[-2])
    else:
        final_end = times[-1]
    return contiguous_intervals([sample <= 1 for sample in samples], times, final_end)


def audio_oracle(path: Path, stream_index: int) -> list[dict]:
    payload = probe(path)
    stream = next(item for item in payload["streams"] if item["index"] == stream_index)
    sample_rate = int(stream["sample_rate"])
    channels = int(stream["channels"])
    result = checked(
        [
            FFMPEG,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-copyts",
            "-f",
            "mov",
            "-protocol_whitelist",
            "file",
            "-enable_drefs",
            "0",
            "-use_absolute_path",
            "0",
            "-i",
            str(path),
            "-map",
            f"0:{stream_index}",
            "-vn",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-",
        ]
    )
    values = struct.unpack(f"<{len(result['stdout']) // 4}f", result["stdout"])
    frame_count = len(values) // channels
    start_time = float(stream.get("start_time", 0))
    states = [
        all(abs(values[index * channels + channel]) < 0.001 for channel in range(channels))
        for index in range(frame_count)
    ]
    times = [start_time + index / sample_rate for index in range(frame_count)]
    return [
        interval
        for interval in contiguous_intervals(states, times, start_time + frame_count / sample_rate)
        if interval["duration"] >= 0.1
    ]


def fixture_set(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    fixtures: dict[str, Path] = {}

    def make(name: str, *args: str) -> Path:
        path = root / name
        ffmpeg_output(path, *args)
        fixtures[name] = path
        return path

    video = "color=c=blue:s=320x240:r=30000/1001:d=6"
    make(
        "baseline ü space.mp4",
        "-f",
        "lavfi",
        "-i",
        video,
        "-f",
        "lavfi",
        "-i",
        "sine=f=1000:r=48000:d=6",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30000/1001",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
    )
    make(
        "video-only.mp4",
        "-f",
        "lavfi",
        "-i",
        video,
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30000/1001",
        "-movflags",
        "+faststart",
    )
    make(
        "reference-source.mp4",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=320x240:r=30:d=1",
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
    )
    make(
        "interior-black.mp4",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=320x240:r=30:d=1",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=320x240:r=30:d=2",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=320x240:r=30:d=3",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]",
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-movflags",
        "+faststart",
    )
    for name, first, second in [
        ("leading-black.mp4", ("black", 1.0), ("blue", 1.0)),
        ("trailing-black.mp4", ("blue", 1.0), ("black", 2.0)),
    ]:
        make(
            name,
            "-f",
            "lavfi",
            "-i",
            f"color=c={first[0]}:s=320x240:r=30:d={first[1]}",
            "-f",
            "lavfi",
            "-i",
            f"color=c={second[0]}:s=320x240:r=30:d={second[1]}",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-movflags",
            "+faststart",
        )
    make(
        "all-black.mp4",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=320x240:r=30:d=2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    )
    make(
        "long-all-black.mp4",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=64x64:r=30:d=120",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    )
    for frames in (14, 15, 16):
        make(
            f"black-tail-{frames}.mp4",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:r=30:d=1",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=320x240:r=30:d={frames / 30:.9f}",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-movflags",
            "+faststart",
        )

    silence_filter = "[1:a]aformat=channel_layouts=stereo,volume=0:enable='between(t,1,4)'[a]"
    for name, codec in [
        ("interior-silence-pcm.mov", "pcm_s16le"),
        ("interior-silence-aac.mp4", "aac"),
    ]:
        make(
            name,
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:r=30:d=6",
            "-f",
            "lavfi",
            "-i",
            "sine=f=1000:r=48000:d=6",
            "-filter_complex",
            silence_filter,
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            codec,
        )
    make(
        "all-silent.mov",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=320x240:r=30:d=3",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo:d=3",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "pcm_s16le",
    )

    def make_silence_boundary(name: str, silence_seconds: float, leading: bool) -> None:
        first = (
            f"anullsrc=r=48000:cl=stereo:d={silence_seconds}"
            if leading
            else "sine=f=1000:r=48000:d=1"
        )
        second = (
            "sine=f=1000:r=48000:d=1"
            if leading
            else f"anullsrc=r=48000:cl=stereo:d={silence_seconds}"
        )
        make(
            name,
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=320x240:r=30:d={1 + silence_seconds}",
            "-f",
            "lavfi",
            "-i",
            first,
            "-f",
            "lavfi",
            "-i",
            second,
            "-filter_complex",
            (
                "[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
                "[2:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
                "[a0][a1]concat=n=2:v=0:a=1[a]"
            ),
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "pcm_s16le",
        )

    make_silence_boundary("leading-silence.mov", 2.5, True)
    make_silence_boundary("trailing-silence.mov", 2.5, False)
    make_silence_boundary("silence-tail-below.mov", 1.99, False)
    make_silence_boundary("silence-tail-equal.mov", 2.0, False)
    make_silence_boundary("silence-tail-above.mov", 2.01, False)
    for name, expression in [
        ("active-left.mov", "0.1*sin(2*PI*1000*t)|0"),
        ("silent-stereo.mov", "0|0"),
    ]:
        make(
            name,
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:r=30:d=3",
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc={expression}:s=48000:d=3:c=stereo",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "pcm_s16le",
        )

    multi = make(
        "multi.mp4",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=320x240:r=30:d=2",
        "-f",
        "lavfi",
        "-i",
        "color=c=green:s=320x240:r=30:d=2",
        "-f",
        "lavfi",
        "-i",
        "sine=f=440:r=48000:d=2",
        "-f",
        "lavfi",
        "-i",
        "sine=f=880:r=48000:d=2",
        "-map",
        "0:v",
        "-map",
        "1:v",
        "-map",
        "2:a",
        "-map",
        "3:a",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-disposition:v:0",
        "0",
        "-disposition:v:1",
        "default",
        "-disposition:a:0",
        "0",
        "-disposition:a:1",
        "default",
    )
    cover = make(
        "cover.jpg",
        "-f",
        "lavfi",
        "-i",
        "color=c=yellow:s=64x64:d=0.04",
        "-frames:v",
        "1",
        "-c:v",
        "mjpeg",
    )
    make(
        "multi-cover.mp4",
        "-i",
        str(multi),
        "-i",
        str(cover),
        "-map",
        "0",
        "-map",
        "1:v",
        "-c",
        "copy",
        "-disposition:v:2",
        "attached_pic",
    )
    make(
        "rotated.mov",
        "-display_rotation:v:0",
        "90",
        "-i",
        str(fixtures["baseline ü space.mp4"]),
        "-map",
        "0",
        "-c",
        "copy",
    )
    make(
        "edit-list.mp4",
        "-i",
        str(fixtures["interior-black.mp4"]),
        "-itsoffset",
        "0.5",
        "-i",
        str(fixtures["interior-silence-pcm.mov"]),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        "-use_editlist",
        "1",
    )
    make(
        "aligned-events.mov",
        "-i",
        str(fixtures["interior-black.mp4"]),
        "-i",
        str(fixtures["interior-silence-pcm.mov"]),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        "-use_editlist",
        "1",
    )
    make(
        "nonzero-start.mov",
        "-itsoffset",
        "2",
        "-i",
        str(fixtures["aligned-events.mov"]),
        "-map",
        "0",
        "-c",
        "copy",
        "-copyts",
        "-avoid_negative_ts",
        "disabled",
        "-use_editlist",
        "1",
    )
    negative = make(
        "negative-start.mov",
        "-i",
        str(fixtures["aligned-events.mov"]),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-c",
        "copy",
        "-copyts",
        "-avoid_negative_ts",
        "disabled",
        "-use_editlist",
        "0",
    )
    patch_negative_ctts(negative)
    return fixtures


def process_experiments() -> dict:
    flood = run(
        [sys.executable, "-c", "import os; os.write(1,b'x'*200000); os.write(2,b'y'*200000)"],
        stdout_cap=32768,
        diagnostic_cap=16384,
    )
    timeout = run(
        [
            sys.executable,
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)",
        ],
        timeout=0.1,
    )
    cancelled = run([sys.executable, "-c", "import time; time.sleep(30)"], cancel_after=0.1)
    previous_ffreport = os.environ.get("FFREPORT")
    os.environ["FFREPORT"] = "file=must-not-exist.log"
    try:
        environment = checked(
            [
                sys.executable,
                "-c",
                "import os; print(os.getenv('FFREPORT')); print(os.getenv('AV_LOG_FORCE_NOCOLOR'))",
            ]
        )
    finally:
        if previous_ffreport is None:
            os.environ.pop("FFREPORT", None)
        else:
            os.environ["FFREPORT"] = previous_ffreport
    simulated_lines = [
        "[blackdetect @ 0x1] black_start:1 black_end:3 black_duration:2",
        "[h264 @ 0x2] Error while decoding MB 1 2",
        *["diagnostic " + ("z" * 1000) for _ in range(2000)],
        "[blackdetect @ 0x1] black_start:4 black_end:5 black_duration:1",
    ]
    events, errors, sticky = parse_events(simulated_lines, "black")
    malformed = parse_events(
        [
            "[blackdetect @ 0x1] black_start:nan black_end:3 black_duration:2",
            "[silencedetect @ 0x1] silence_end: 3 | silence_duration: 2",
        ],
        "black",
    )
    finite = parse_events(
        [
            "[Parsed_blackdetect_0 @ 0x1] black_start:-1e-1 black_end:+5e-1 black_duration:6e-1",
            "[metadata @ 0x2] black_start:9 black_end:10 black_duration:1",
        ],
        "black",
    )
    return {
        "flood": {
            "returncode": flood["returncode"],
            "output_limit_exceeded": flood["output_limit_exceeded"],
            "stdout_bytes": len(flood["stdout"]),
            "diagnostic_bytes": len(flood["diagnostic_tail"]),
        },
        "timeout": {
            "returncode": timeout["returncode"],
            "timed_out": timeout["timed_out"],
            "elapsed_seconds": timeout["elapsed_seconds"],
        },
        "cancellation": {
            "returncode": cancelled["returncode"],
            "cancelled": cancelled["cancelled"],
        },
        "environment": environment["stdout"].decode().splitlines(),
        "sticky_decode_simulation": {
            "events": events,
            "parse_errors": errors,
            "decode_error_detected": sticky,
            "completion_with_zero_returncode": not errors and not sticky,
        },
        "malformed_simulation": {
            "events": malformed[0],
            "parse_errors": malformed[1],
            "decode_error_detected": malformed[2],
        },
        "finite_and_attribution_simulation": {
            "events": finite[0],
            "parse_errors": finite[1],
            "decode_error_detected": finite[2],
        },
    }


def make_external_reference(source: Path, destination: Path, location: str) -> bool:
    data = bytearray(source.read_bytes())
    boxes = list(mp4_boxes(data))
    target = next(
        (
            (box_path, offset, size, header)
            for box_path, offset, size, header in boxes
            if box_path[-1] == "url "
        ),
        None,
    )
    if target is None:
        return False
    _path, offset, size, header = target
    # QuickTime `alis` drefs are the external-reference form handled by the
    # MOV demuxer. A bounded synthetic record is enough to exercise the
    # enable_drefs gate without pointing at a real external service.
    payload = bytearray(220)
    encoded_location = location.encode("utf-8")[:63]
    payload[50] = len(encoded_location)
    payload[51 : 51 + len(encoded_location)] = encoded_location
    struct.pack_into(">HH", payload, 150, 2, len(encoded_location))
    payload[154 : 154 + len(encoded_location)] = encoded_location
    terminator = 154 + len(encoded_location) + (len(encoded_location) % 2)
    struct.pack_into(">HH", payload, terminator, 0xFFFF, 0)
    data[offset + 4 : offset + 8] = b"alis"
    data[offset + header : offset + header + 4] = b"\0\0\0\0"
    data[offset : offset + 4] = struct.pack(">I", size + len(payload))
    for _box_path, parent_offset, parent_size, _parent_header in boxes:
        if parent_offset < offset and parent_offset + parent_size >= offset + size:
            if parent_size >= 2**32:
                raise RuntimeError("extended MP4 box unsupported in reference fixture")
            struct.pack_into(">I", data, parent_offset, parent_size + len(payload))
    data[offset + size : offset + size] = payload
    destination.write_bytes(data)
    return True


def restricted_input_experiments(root: Path, baseline: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.mp4"
    manifest.write_text("#EXTM3U\nhttp://127.0.0.1:9/not-contacted.ts\n", encoding="utf-8")
    manifest_result = run(detector_argv(manifest, 0, "black"))
    url_argv = detector_argv("http://127.0.0.1:9/not-contacted.mp4", 0, "black")
    url_result = run(url_argv)

    (root / "external.bin").write_bytes(b"controlled external reference marker")
    reference = root / "external-reference.mp4"
    patched = make_external_reference(baseline, reference, "external.bin")
    disabled_lines: list[str] = []
    reference_result = run(detector_argv(reference, 0, "black"), on_line=disabled_lines.append)
    enabled_argv = detector_argv(reference, 0, "black")
    enabled_argv[enabled_argv.index("-enable_drefs") + 1] = "1"
    enabled_lines: list[str] = []
    enabled_result = run(enabled_argv, on_line=enabled_lines.append)
    return {
        "manifest": {
            "returncode": manifest_result["returncode"],
            "diagnostic": manifest_result["diagnostic_tail"].decode("utf-8", "replace")[-1000:],
        },
        "url": {
            "returncode": url_result["returncode"],
            "diagnostic": url_result["diagnostic_tail"].decode("utf-8", "replace")[-1000:],
        },
        "external_reference_patch_applied": patched,
        "external_reference": {
            "returncode": reference_result["returncode"],
            "reference_lines": [
                line
                for line in disabled_lines
                if re.search(r"dref|alias|external track|absolute path", line, re.IGNORECASE)
            ],
            "diagnostic": reference_result["diagnostic_tail"].decode("utf-8", "replace")[-1000:],
        },
        "external_reference_enabled_control": {
            "returncode": enabled_result["returncode"],
            "reference_lines": [
                line
                for line in enabled_lines
                if re.search(r"dref|alias|external track|absolute path", line, re.IGNORECASE)
            ],
            "diagnostic": enabled_result["diagnostic_tail"].decode("utf-8", "replace")[-1000:],
        },
    }


def evaluate(report: dict) -> list[dict]:
    checks: list[dict] = []

    def check(name: str, passed: bool, observed: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "observed": observed})

    fixtures = report["fixtures"]
    check("all source hashes unchanged", report["all_source_hashes_unchanged"], True)
    check(
        "rational baseline and video-only inventory",
        fixtures["baseline ü space.mp4"]["probe"]["streams"][0]["avg_frame_rate"] == "30000/1001"
        and fixtures["video-only.mp4"]["selection"] == (0, None, []),
        {
            "rate": fixtures["baseline ü space.mp4"]["probe"]["streams"][0]["avg_frame_rate"],
            "video_only": fixtures["video-only.mp4"]["selection"],
        },
    )
    check(
        "default streams selected and attached picture excluded",
        fixtures["multi-cover.mp4"]["selection"] == (1, 3, [0, 2, 4])
        and fixtures["multi-cover.mp4"]["probe"]["streams"][4]["disposition"]["attached_pic"] == 1,
        fixtures["multi-cover.mp4"]["selection"],
    )
    check(
        "coded dimensions and rotation preserved",
        fixtures["rotated.mov"]["probe"]["streams"][0]["width"] == 320
        and fixtures["rotated.mov"]["probe"]["streams"][0]["height"] == 240
        and fixtures["rotated.mov"]["probe"]["streams"][0]["side_data_list"][0]["rotation"] == 90,
        fixtures["rotated.mov"]["probe"]["streams"][0],
    )

    black = report["black"]
    black_oracles = report["black_decoded_oracles"]
    check(
        "interior black matches decoded oracle",
        black["interior-black.mp4"]["events"] == [{"start": 1.0, "end": 3.0, "duration": 2.0}]
        and black["interior-black.mp4"]["events"] == black_oracles["interior-black.mp4"],
        black["interior-black.mp4"]["events"],
    )
    check(
        "black EOF native limitation and threshold edge",
        abs(black["trailing-black.mp4"]["events"][0]["end"] - 2.966667) < 1e-6
        and abs(black_oracles["trailing-black.mp4"][0]["end"] - 3.0) < 0.001
        and not black["black-tail-14.mp4"]["events"]
        and not black["black-tail-15.mp4"]["events"]
        and black["black-tail-16.mp4"]["events"][0]["end"] == 1.5,
        {
            name: black[name]["events"]
            for name in (
                "trailing-black.mp4",
                "black-tail-14.mp4",
                "black-tail-15.mp4",
                "black-tail-16.mp4",
            )
        },
    )
    check(
        "leading and all-black native events complete",
        black["leading-black.mp4"]["events"][0]["start"] == 0
        and black["all-black.mp4"]["events"][0]["start"] == 0
        and all(black[name]["complete"] for name in black),
        {
            "leading": black["leading-black.mp4"]["events"],
            "all": black["all-black.mp4"]["events"],
        },
    )

    silence = report["silence"]
    silence_oracles = report["silence_decoded_oracles"]

    def event_close(name: str, tolerance: float) -> bool:
        observed = silence[name]["events"][0]
        expected = silence_oracles[name][0]
        return (
            abs(observed["start"] - expected["start"]) <= tolerance
            and abs(observed["end"] - expected["end"]) <= tolerance
        )

    check(
        "PCM and AAC interior silence match decoded samples",
        event_close("interior-silence-pcm.mov", 1 / 48000 + 1e-6)
        and event_close("interior-silence-aac.mp4", 0.05),
        {
            "pcm": silence["interior-silence-pcm.mov"]["events"],
            "aac": silence["interior-silence-aac.mp4"]["events"],
        },
    )
    check(
        "silence EOF below/equal/above minimum",
        not silence["silence-tail-below.mov"]["events"]
        and silence["silence-tail-equal.mov"]["events"][0]["duration"] == 2
        and silence["silence-tail-above.mov"]["events"][0]["duration"] == 2.01,
        {
            name: silence[name]["events"]
            for name in (
                "silence-tail-below.mov",
                "silence-tail-equal.mov",
                "silence-tail-above.mov",
            )
        },
    )
    check(
        "collective channels require all channels silent",
        not silence["active-left.mov"]["events"]
        and silence["silent-stereo.mov"]["events"][0]["duration"] == 3,
        {
            "active_left": silence["active-left.mov"]["events"],
            "silent": silence["silent-stereo.mov"]["events"],
        },
    )
    check(
        "leading trailing and all-silent boundaries",
        silence["leading-silence.mov"]["events"][0]["start"] == 0
        and silence["trailing-silence.mov"]["events"][0]["end"] == 3.5
        and silence["all-silent.mov"]["events"][0] == {"start": 0.0, "end": 3.0, "duration": 3.0},
        {
            "leading": silence["leading-silence.mov"]["events"],
            "trailing": silence["trailing-silence.mov"]["events"],
            "all": silence["all-silent.mov"]["events"],
        },
    )

    check(
        "stored edit lists and decoded A/V PTS offset",
        len(report["edit_lists"]) == 2
        and report["edit_list_frame_pts"]["0"]["minimum"] == 0
        and report["edit_list_frame_pts"]["1"]["minimum"] == 0.5
        and report["edit_list_detectors"]["black"]["events"][0]["start"] == 1
        and abs(report["edit_list_detectors"]["silence"]["events"][0]["start"] - 1.502667) < 1e-6,
        {
            "lists": report["edit_lists"],
            "pts": report["edit_list_frame_pts"],
            "events": {
                key: value["events"] for key, value in report["edit_list_detectors"].items()
            },
        },
    )
    timestamp_detectors = report["timestamp_detectors"]
    check(
        "common nonzero origin normalization",
        report["timelines"]["nonzero-start.mov"]["origin"] == 2
        and timestamp_detectors["nonzero-start.mov"]["normalized"]["black"][0]["start"] == 1
        and abs(
            timestamp_detectors["nonzero-start.mov"]["normalized"]["silence"][0]["start"] - 1.002667
        )
        < 1e-6,
        timestamp_detectors["nonzero-start.mov"],
    )
    check(
        "negative origin preserves A/V offset",
        report["timelines"]["negative-start.mov"]["origin"] < 0
        and report["negative_start_frame_pts"]["0"]["minimum"] < 0
        and report["negative_start_frame_pts"]["1"]["minimum"] == 0
        and timestamp_detectors["negative-start.mov"]["normalized"]["black"][0]["start"] == 1
        and timestamp_detectors["negative-start.mov"]["normalized"]["silence"][0]["start"] > 1.19,
        timestamp_detectors["negative-start.mov"],
    )
    check(
        "unknown origin remains source PTS",
        report["unknown_timeline_simulation"]
        == {"basis": "source_pts", "origin": None, "origin_source": "unknown"},
        report["unknown_timeline_simulation"],
    )

    process = report["process"]
    check(
        "timeout flood cancellation and environment fail closed",
        process["flood"]["output_limit_exceeded"]
        and process["flood"]["stdout_bytes"] == 32768
        and process["timeout"]["timed_out"]
        and process["timeout"]["returncode"] == -9
        and process["cancellation"]["cancelled"]
        and process["environment"] == ["None", "1"],
        process,
    )
    check(
        "sticky decode error defeats zero-return closing events",
        process["sticky_decode_simulation"]["decode_error_detected"]
        and not process["sticky_decode_simulation"]["completion_with_zero_returncode"]
        and len(process["sticky_decode_simulation"]["events"]) == 2,
        process["sticky_decode_simulation"],
    )
    check(
        "parser rejects nonfinite and accepts attributed signed scientific values",
        process["malformed_simulation"]["parse_errors"] == ["nonfinite black event"]
        and process["finite_and_attribution_simulation"]["events"]
        == [{"start": -0.1, "end": 0.5, "duration": 0.6}],
        {
            "malformed": process["malformed_simulation"],
            "finite": process["finite_and_attribution_simulation"],
        },
    )
    check(
        "native xerror decode failure and cancellation incomplete",
        report["damaged_native"]["returncode"] != 0
        and report["damaged_native"]["decode_error_detected"]
        and not report["damaged_native"]["complete"]
        and report["cancelled_native"]["cancelled"]
        and not report["cancelled_native"]["complete"],
        {
            "damaged": report["damaged_native"],
            "cancelled": report["cancelled_native"],
        },
    )

    restricted = report["restricted_inputs"]
    check(
        "URL and manifest rejected before remote loading",
        restricted["url"]["returncode"] != 0
        and "not on whitelist 'file'" in restricted["url"]["diagnostic"]
        and restricted["manifest"]["returncode"] != 0,
        restricted,
    )
    check(
        "external QuickTime alias skipped with drefs disabled",
        restricted["external_reference_patch_applied"]
        and restricted["external_reference"]["returncode"] != 0
        and any(
            "Skipped opening external track" in line
            for line in restricted["external_reference"]["reference_lines"]
        )
        and any(
            "error opening alias" in line
            for line in restricted["external_reference_enabled_control"]["reference_lines"]
        ),
        restricted,
    )

    forbidden = {"-shortest", "-ss", "-to", "-t", "-r", "-ac", "-ar"}
    detector_argvs = [
        result["argv"]
        for group in (
            report["black"],
            report["silence"],
            report["edit_list_detectors"],
        )
        for result in group.values()
    ]
    check(
        "detector argv contract",
        all(
            {"-nostdin", "-copyts", "-noautorotate", "-xerror", "-map", "-f"}.issubset(argv)
            and not forbidden.intersection(argv)
            for argv in detector_argvs
        ),
        detector_argvs[0],
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", type=Path, help="use and retain this temporary work directory")
    args = parser.parse_args()
    temporary = None
    if args.keep:
        root = args.keep.resolve()
        root.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="frameguard-m0-")
        root = Path(temporary.name)

    report: dict = {
        "python": sys.version.split()[0],
        "ffmpeg": checked([FFMPEG, "-version"])["stdout"].decode().splitlines()[0],
        "ffprobe": checked([FFPROBE, "-version"])["stdout"].decode().splitlines()[0],
        "workdir": str(root),
        "operational_caps": {
            "tool_timeout_seconds": 10,
            "probe_timeout_seconds": 30,
            "detector_timeout_seconds": 600,
            "probe_stdout_bytes": 8 * 1024 * 1024,
            "diagnostic_tail_bytes": DIAGNOSTIC_CAP,
            "event_line_bytes": LINE_CAP,
            "findings": FINDING_CAP,
            "terminate_grace_seconds": 2,
        },
    }
    fixtures = fixture_set(root)
    hashes_before = {name: digest(path) for name, path in fixtures.items()}
    probes = {name: probe(path) for name, path in fixtures.items() if path.suffix != ".jpg"}
    selections = {name: choose_streams(payload) for name, payload in probes.items()}

    detector_names = [
        "interior-black.mp4",
        "leading-black.mp4",
        "trailing-black.mp4",
        "all-black.mp4",
        "black-tail-14.mp4",
        "black-tail-15.mp4",
        "black-tail-16.mp4",
    ]
    black = {name: detect(fixtures[name], selections[name][0], "black") for name in detector_names}
    silence_names = [
        "interior-silence-pcm.mov",
        "interior-silence-aac.mp4",
        "all-silent.mov",
        "leading-silence.mov",
        "trailing-silence.mov",
        "silence-tail-below.mov",
        "silence-tail-equal.mov",
        "silence-tail-above.mov",
        "active-left.mov",
        "silent-stereo.mov",
    ]
    silence = {
        name: detect(fixtures[name], selections[name][1], "silence")
        for name in silence_names
        if selections[name][1] is not None
    }

    damaged = root / "damaged-black.mp4"
    ffmpeg_output(
        damaged,
        "-i",
        str(fixtures["all-black.mp4"]),
        "-map",
        "0:v:0",
        "-c:v",
        "copy",
        "-bsf:v",
        "noise=amount=100",
        "-movflags",
        "+faststart",
    )
    damaged_result = detect(damaged, 0, "black")
    cancellation = detect(fixtures["long-all-black.mp4"], 0, "black", cancel_after=0.05)

    hashes_after = {name: digest(path) for name, path in fixtures.items()}
    oracles = {name: video_oracle(fixtures[name], selections[name][0]) for name in detector_names}
    audio_oracles = {
        name: audio_oracle(fixtures[name], selections[name][1])
        for name in silence_names
        if selections[name][1] is not None
    }
    timestamp_names = [
        "baseline ü space.mp4",
        "edit-list.mp4",
        "nonzero-start.mov",
        "negative-start.mov",
    ]
    timelines = {name: timeline(probes[name], selections[name]) for name in timestamp_names}
    timestamp_detectors = {}
    for name in ("nonzero-start.mov", "negative-start.mov"):
        selected = selections[name]
        raw = {
            "black": detect(fixtures[name], selected[0], "black"),
            "silence": detect(fixtures[name], selected[1], "silence"),
        }
        origin = timelines[name]["origin"]
        timestamp_detectors[name] = {
            "raw": raw,
            "normalized": {
                kind: [
                    {
                        **event,
                        "start": event["start"] - origin,
                        "end": event["end"] - origin,
                    }
                    for event in result["events"]
                ]
                for kind, result in raw.items()
            },
        }
    edit_selection = selections["edit-list.mp4"]
    edit_detectors = {
        "black": detect(fixtures["edit-list.mp4"], edit_selection[0], "black"),
        "silence": detect(fixtures["edit-list.mp4"], edit_selection[1], "silence"),
    }
    report.update(
        {
            "fixtures": {
                name: {
                    "sha256_before": hashes_before[name],
                    "sha256_after": hashes_after[name],
                    "unchanged": hashes_before[name] == hashes_after[name],
                    "probe": probes.get(name),
                    "selection": selections.get(name),
                }
                for name in fixtures
            },
            "black": black,
            "black_decoded_oracles": oracles,
            "silence": silence,
            "silence_decoded_oracles": audio_oracles,
            "edit_lists": edit_lists(fixtures["edit-list.mp4"]),
            "edit_list_frame_pts": frame_pts_summary(probe(fixtures["edit-list.mp4"], frames=True)),
            "edit_list_detectors": edit_detectors,
            "negative_start_frame_pts": frame_pts_summary(
                probe(fixtures["negative-start.mov"], frames=True)
            ),
            "timelines": timelines,
            "timestamp_detectors": timestamp_detectors,
            "unknown_timeline_simulation": timeline(
                {
                    "format": {},
                    "streams": [
                        {"index": 0, "codec_type": "video"},
                        {"index": 1, "codec_type": "audio", "start_time": "0.25"},
                    ],
                },
                (0, 1, []),
            ),
            "damaged_native": damaged_result,
            "cancelled_native": cancellation,
            "process": process_experiments(),
            "restricted_inputs": restricted_input_experiments(
                root, fixtures["reference-source.mp4"]
            ),
        }
    )
    report["all_source_hashes_unchanged"] = all(
        before == hashes_after[name] for name, before in hashes_before.items()
    )
    report["gate_checks"] = evaluate(report)
    report["gate_passed"] = all(check["passed"] for check in report["gate_checks"])
    report["command_log"] = list(COMMAND_LOG)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    if temporary:
        temporary.cleanup()
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
