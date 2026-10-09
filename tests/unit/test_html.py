from frameguard.reporting import render_html


def test_html_escapes_text_and_stays_offline(sample_report) -> None:
    report = sample_report(
        "incomplete",
        display_name='<script>alert("x")</script> & café',
        metadata=False,
    )
    page = render_html(report)

    assert "&lt;script&gt;alert" in page
    assert "<script" not in page.lower()
    assert "href=" not in page
    assert "src=" not in page
    assert "café" in page
    assert "incomplete" in page
    assert "probe_failed" in page
    assert "last picture PTS" in page
    assert "selected streams only" in page
    assert "uninspected" in page.lower() or "Unavailable" in page
    assert "Configuration" in page
    assert "expect_fps: 30000/1001" in page


def test_html_shows_interval_times(sample_report, finding) -> None:
    page = render_html(sample_report("warn", [finding("warning", "black", "BLACK_INTERVAL", 1.0)]))

    assert "BLACK_INTERVAL 1.0-2.0" in page
