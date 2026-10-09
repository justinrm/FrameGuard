import json
from dataclasses import replace

import pytest

from frameguard.reporting import render_json, report_to_dict


def test_projection_keeps_nulls_fractions_and_sorted_findings(sample_report, finding) -> None:
    report = sample_report(
        "warn",
        [
            finding("info", "audio_presence", "AUDIO_ABSENT"),
            finding("warning", "black", "BLACK_INTERVAL", 3),
            finding("critical", "resolution", "RESOLUTION_MISMATCH"),
            finding("warning", "black", "BLACK_INTERVAL", 1),
        ],
    )
    payload = report_to_dict(report)
    encoded = json.dumps(payload)

    assert payload["schema_version"] == "0.1.0"
    assert payload["tool_version"] == "0.1.0"
    assert payload["input"]["display_name"] == "clip.mp4"
    assert payload["media_metadata"]["streams"][0]["sample_rate_hz"] is None
    assert payload["media_metadata"]["streams"][0]["parsed_avg_frame_rate"] == "30000/1001"
    assert payload["configuration"]["expect_width"] is None
    assert [item["code"] for item in payload["findings"]] == [
        "RESOLUTION_MISMATCH",
        "BLACK_INTERVAL",
        "BLACK_INTERVAL",
        "AUDIO_ABSENT",
    ]
    assert payload["findings"][1]["interval"]["start_seconds"] == 1
    assert "ffmpeg_path" not in encoded
    assert "/Users" not in encoded


def test_equivalent_scans_match_except_elapsed_time(sample_report) -> None:
    left = report_to_dict(sample_report())
    right = report_to_dict(replace(sample_report(), analysis_duration_seconds=9.5))
    assert left.pop("analysis_duration_seconds") != right.pop("analysis_duration_seconds")
    assert left == right


@pytest.mark.parametrize("status", ["pass", "warn", "fail", "incomplete"])
def test_json_round_trip_covers_each_status(sample_report, finding, status: str) -> None:
    findings = []
    if status == "warn":
        findings = [finding("warning", "black", "BLACK_INTERVAL", 1)]
    elif status == "fail":
        findings = [finding("critical", "resolution", "RESOLUTION_MISMATCH")]
    report = sample_report(status, findings, metadata=status != "incomplete")
    payload = json.loads(render_json(report))
    assert payload["overall_status"] == status
    assert payload == report_to_dict(report)


def test_nonfinite_numbers_are_rejected(sample_report) -> None:
    report = replace(sample_report(), analysis_duration_seconds=float("nan"))
    with pytest.raises(ValueError):
        report_to_dict(report)
