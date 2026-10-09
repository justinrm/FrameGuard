from frameguard.checks.black import BlackParser
from frameguard.models import ProcessResult, Timeline


def finish(lines: list[str], *, returncode: int = 0) -> tuple[BlackParser, list]:
    parser = BlackParser()
    for line in lines:
        parser.feed(line)
    intervals, diagnostics = parser.finish(
        ProcessResult(returncode, b"", b""),
        Timeline("media_relative", 0.0, "format_start_time"),
    )
    return parser, (intervals, diagnostics)


def test_attributed_black_event_and_lookalike() -> None:
    parser, (intervals, diagnostics) = finish(
        [
            "[Parsed_blackdetect_0 @ 0x1] black_start:1 black_end:3 black_duration:2",
            "[metadata @ 0x2] black_start:9 black_end:10 black_duration:1",
            "[Parsed_blackdetect_0 @ 0x1] black_start:-1e-1 black_end:+5e-1 black_duration:6e-1",
        ]
    )
    assert diagnostics == []
    assert [
        (item.start_seconds, item.end_seconds, item.duration_seconds) for item in intervals
    ] == [
        (1.0, 3.0, 2.0),
        (-0.1, 0.5, 0.6),
    ]
    assert parser.decode_error_detected is False


def test_malformed_and_sticky_decode_error_fail() -> None:
    _, (intervals, diagnostics) = finish(
        ["[Parsed_blackdetect_0 @ 0x1] black_start:nan black_end:3 black_duration:2"]
    )
    assert intervals == []
    assert diagnostics

    parser, (kept, failed) = finish(
        [
            "[Parsed_blackdetect_0 @ 0x1] black_start:1 black_end:3 black_duration:2",
            "[h264 @ 0x2] Error while decoding MB 1 2",
            "[Parsed_blackdetect_0 @ 0x1] black_start:4 black_end:5 black_duration:1",
        ]
    )
    assert parser.decode_error_detected
    assert len(kept) == 2
    assert failed
