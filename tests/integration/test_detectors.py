import itertools
import struct
import subprocess
from pathlib import Path

from frameguard.models import ScanConfig, exit_code
from frameguard.process import discover_tools
from frameguard.reporting import render_json, render_terminal
from frameguard.scanner import scan


def _finding(report, code: str):
    return next(item for item in report.findings if item.code == code)


def test_interior_black_warns_and_short_tail_does_not(media_fixtures: dict[str, Path]) -> None:
    interior = scan(media_fixtures["interior_black"], ScanConfig())
    assert interior.overall_status == "warn"
    black = _finding(interior, "BLACK_INTERVAL")
    assert black.interval is not None
    assert abs(black.interval.start_seconds - 1) < 0.05
    assert abs(black.interval.end_seconds - 3) < 0.05
    assert any("last picture PTS" in item for item in _check(interior, "black").limitations)

    tail = scan(media_fixtures["black_tail"], ScanConfig())
    assert not any(item.code == "BLACK_INTERVAL" for item in tail.findings)
    assert _check(tail, "black").status == "completed"


def test_damaged_bitstream_stays_incomplete(media_fixtures: dict[str, Path]) -> None:
    report = scan(media_fixtures["damaged"], ScanConfig())
    black = _check(report, "black")

    assert black.status == "failed"
    assert report.overall_status == "incomplete"
    assert exit_code(report) == 2
    assert all(item.provisional for item in report.findings if item.check_id == "black")


def test_leading_black_starts_at_zero(media_fixtures: dict[str, Path]) -> None:
    report = scan(media_fixtures["leading_black"], ScanConfig())
    black = _finding(report, "BLACK_INTERVAL")

    assert report.overall_status == "warn"
    assert exit_code(report) == 0
    assert black.interval is not None
    assert abs(black.interval.start_seconds - 0) < 0.05
    assert abs(black.interval.end_seconds - 1) < 0.05


def test_aac_silence_matches_recorded_oracle(media_fixtures: dict[str, Path]) -> None:
    report = scan(media_fixtures["silence_aac"], ScanConfig())
    interval = _finding(report, "SILENCE_INTERVAL").interval

    assert report.overall_status == "warn"
    assert exit_code(report) == 0
    assert interval is not None
    assert abs(interval.start_seconds - 1.003792) < 0.05
    assert abs(interval.end_seconds - 4.009542) < 0.05


def test_edit_list_keeps_one_origin_and_av_offset(media_fixtures: dict[str, Path]) -> None:
    path = media_fixtures["edit_list"]
    report = scan(path, ScanConfig())
    metadata = report.media_metadata
    assert metadata is not None
    video = next(
        stream for stream in metadata.streams if stream.index == metadata.selected_video_index
    )
    audio = next(
        stream for stream in metadata.streams if stream.index == metadata.selected_audio_index
    )
    black = _finding(report, "BLACK_INTERVAL").interval
    silence = _finding(report, "SILENCE_INTERVAL").interval

    assert len(_edit_lists(path)) == 2
    assert video.start_time_seconds == 0
    assert audio.start_time_seconds == 0.5
    assert report.timeline.basis == "media_relative"
    assert report.timeline.origin_seconds == 0
    assert report.timeline.origin_source == "format_start_time"
    assert black is not None and silence is not None
    assert abs(black.start_seconds - 1) < 0.05
    assert abs(black.end_seconds - 3) < 0.05
    assert abs(silence.start_seconds - 1.502667) < 0.01
    assert abs((silence.raw_start_seconds - black.raw_start_seconds) - 0.502667) < 0.02
    assert (
        abs(
            (silence.start_seconds - black.start_seconds)
            - (silence.raw_start_seconds - black.raw_start_seconds)
        )
        < 1e-9
    )
    assert exit_code(report) == 0


def test_short_and_vfr_scans_do_not_claim_pacing(media_fixtures: dict[str, Path]) -> None:
    short = scan(media_fixtures["short"], ScanConfig())
    assert short.media_metadata is not None
    assert short.media_metadata.duration_seconds is not None
    assert short.media_metadata.duration_seconds < 0.5
    assert _check(short, "probe").status == "completed"
    assert _check(short, "black").status == "completed"
    assert short.overall_status == "pass"

    vfr = scan(media_fixtures["vfr"], ScanConfig())
    assert vfr.media_metadata is not None
    video = next(
        stream
        for stream in vfr.media_metadata.streams
        if stream.index == vfr.media_metadata.selected_video_index
    )
    matched = scan(media_fixtures["vfr"], ScanConfig(expect_fps=video.parsed_avg_frame_rate))
    assert _check(matched, "frame_rate").status == "completed"
    assert not any(item.code == "FPS_MISMATCH" for item in matched.findings)
    text = render_terminal(vfr) + render_json(vfr)
    assert "uniform" not in text.lower()
    assert "constant frame" not in text.lower()
    assert _frame_deltas_differ(media_fixtures["vfr"])


def test_pcm_silence_warns_and_one_active_channel_does_not(media_fixtures: dict[str, Path]) -> None:
    silent = scan(media_fixtures["interior_silence"], ScanConfig())
    assert silent.overall_status == "warn"
    interval = _finding(silent, "SILENCE_INTERVAL").interval
    assert interval is not None
    assert abs(interval.start_seconds - 1) < 0.002
    assert abs(interval.duration_seconds - 3) < 0.002

    active = scan(media_fixtures["active_left"], ScanConfig())
    assert active.overall_status == "pass"
    assert not any(item.code == "SILENCE_INTERVAL" for item in active.findings)


def _check(report, check_id: str):
    return next(item for item in report.checks if item.check_id == check_id)


def _edit_lists(path: Path) -> list[tuple[str, ...]]:
    data = path.read_bytes()
    found: list[tuple[str, ...]] = []

    def walk(start: int, end: int, box_path: tuple[str, ...]) -> None:
        cursor = start
        containers = {"moov", "trak", "mdia", "minf", "dinf", "stbl", "edts"}
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
            current = box_path + (box_type,)
            if box_type == "elst":
                found.append(current)
            elif box_type in containers:
                walk(cursor + header, cursor + size, current)
            cursor += size

    walk(0, len(data), ())
    return found


def _frame_deltas_differ(path: Path) -> bool:
    result = subprocess.run(
        [
            str(discover_tools().ffprobe_path),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=best_effort_timestamp_time",
            "-of",
            "csv=p=0",
            str(path),
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    times = [float(line.split(",")[0]) for line in result.stdout.splitlines() if line.strip(",")]
    deltas = [round(later - earlier, 6) for earlier, later in itertools.pairwise(times)]
    return len(set(deltas)) > 1
