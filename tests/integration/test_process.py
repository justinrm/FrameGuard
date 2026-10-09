from frameguard.process import discover_tools


def test_actual_toolchain_matches_validated_build() -> None:
    tools = discover_tools()

    assert tools.versions.ffmpeg_version.startswith("ffmpeg version 9.0.2")
    assert tools.versions.ffprobe_version.startswith("ffprobe version 9.0.2")
    assert {"blackdetect", "silencedetect", "mov"}.issubset(tools.versions.capabilities)
