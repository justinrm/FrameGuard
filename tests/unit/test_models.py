import json
from dataclasses import asdict
from fractions import Fraction

import pytest

from frameguard.models import ScanConfig, ensure_finite_json


def test_model_unknowns_remain_null_and_fractions_are_explicit() -> None:
    config = ScanConfig(expect_fps=Fraction(30_000, 1_001), expect_fps_input="30000/1001")
    projected = asdict(config)
    projected["expect_fps"] = str(config.expect_fps)
    ensure_finite_json(projected)
    encoded = json.dumps(projected, allow_nan=False)

    assert '"expect_width": null' in encoded
    assert '"expect_fps": "30000/1001"' in encoded


def test_nonfinite_json_is_rejected() -> None:
    with pytest.raises(ValueError):
        ensure_finite_json({"bad": float("inf")})
