from frameguard.models import ScanConfig
from frameguard.scanner import scan


def test_real_baseline_scan_passes(
    media_fixtures: dict[str, object],
) -> None:
    report = scan(media_fixtures["baseline"], ScanConfig())

    assert report.media_metadata is not None
    assert report.media_metadata.selected_video_index == 0
    assert report.media_metadata.selected_audio_index == 1
    assert report.overall_status == "pass"
    assert {check.check_id for check in report.checks if check.status == "completed"} >= {
        "black",
        "silence",
    }
