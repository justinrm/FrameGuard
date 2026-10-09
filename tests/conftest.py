from __future__ import annotations

import importlib.util
from fractions import Fraction
from pathlib import Path

import pytest

from frameguard.models import (
    CheckResult,
    Diagnostic,
    Finding,
    InputInfo,
    Interval,
    MediaMetadata,
    ScanReport,
    StreamMetadata,
    Timeline,
    ToolVersions,
)
from frameguard.process import discover_tools


def build_finding(severity: str, check_id: str, code: str, start: float | None = None) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        title=code,
        explanation="evidence",
        check_id=check_id,
        stream_index=0,
        interval=None if start is None else Interval(start, start + 1, 1.0, start, start + 1),
    )


def build_sample_report(
    status: str = "pass",
    findings: list[Finding] | None = None,
    *,
    metadata: bool = True,
    display_name: str = "clip.mp4",
) -> ScanReport:
    probe_failed = status == "incomplete"
    return ScanReport(
        schema_version="0.1.0",
        tool_version="0.1.0",
        input=InputInfo(display_name, 12),
        media_metadata=None
        if not metadata or probe_failed
        else MediaMetadata(
            format_name="mov,mp4",
            streams=[
                StreamMetadata(
                    index=0,
                    codec_type="video",
                    width=320,
                    height=240,
                    avg_frame_rate="30000/1001",
                    parsed_avg_frame_rate=Fraction(30000, 1001),
                    disposition_default=True,
                )
            ],
            selected_video_index=0,
            selected_audio_index=None,
            uninspected_stream_indexes=[2],
        ),
        configuration={"expect_width": None, "expect_fps": "30000/1001"},
        timeline=Timeline("media_relative", 0.0, "format_start_time", ["selected streams only"]),
        checks=[
            CheckResult("input_validation", "completed"),
            CheckResult(
                "probe",
                "failed" if probe_failed else "completed",
                reason_code="probe_failed" if probe_failed else None,
                diagnostics=[
                    Diagnostic("probe_failed", "ffprobe could not inspect clip.mp4", "probe")
                ]
                if probe_failed
                else [],
            ),
            CheckResult(
                "black",
                "completed",
                limitations=["trailing black ends at last picture PTS"],
            ),
        ],
        findings=list(findings or []),
        diagnostics=[Diagnostic("probe_failed", "ffprobe could not inspect clip.mp4", "probe")]
        if probe_failed
        else [],
        overall_status=status,
        analysis_duration_seconds=1.25,
        tool_versions=ToolVersions("ffmpeg version 9.0.2", "ffprobe version 9.0.2"),
    )


@pytest.fixture
def sample_report():
    return build_sample_report


@pytest.fixture
def finding():
    return build_finding


@pytest.fixture(scope="session")
def media_fixtures(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    module_path = Path(__file__).parent / "fixtures" / "generate.py"
    spec = importlib.util.spec_from_file_location("frameguard_fixture_generator", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tools = discover_tools()
    return module.generate_probe_fixtures(
        tmp_path_factory.mktemp("frameguard-media"),
        tools.ffmpeg_path,
    )
