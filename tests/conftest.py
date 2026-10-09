from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from frameguard.process import discover_tools


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
