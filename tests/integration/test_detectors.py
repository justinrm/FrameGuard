from pathlib import Path

from frameguard.models import ScanConfig, exit_code
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
