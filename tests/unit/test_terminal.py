from frameguard.reporting import render_terminal


def test_terminal_strips_controls_and_keeps_unicode(sample_report, finding) -> None:
    report = sample_report(
        "warn",
        [finding("warning", "black", "BLACK_INTERVAL", 1)],
        display_name="café\x1b[31m clip.mp4",
    )
    text = render_terminal(report)

    assert "\x1b" not in text
    assert "café" in text
    assert "Status: warn" in text
    assert "BLACK_INTERVAL" in text
    assert "Video stream: 0" in text
    assert "human review" in text


def test_terminal_names_incomplete_diagnostics(sample_report) -> None:
    text = render_terminal(sample_report("incomplete", metadata=False))

    assert "Status: incomplete" in text
    assert "ffprobe could not inspect" in text
    assert "probe: failed" in text
