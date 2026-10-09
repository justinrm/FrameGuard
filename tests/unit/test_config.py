from fractions import Fraction

import pytest

from frameguard.models import ConfigError, ScanConfig, validate_config


def test_valid_config_accepts_decimal_equivalent_fraction() -> None:
    config = ScanConfig(expect_fps=Fraction("29.97"), expect_fps_input="29.97")
    validate_config(config)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expect_width", 0),
        ("expect_height", -1),
        ("expect_fps", Fraction(0)),
        ("black_min_duration_seconds", 0),
        ("silence_min_duration_seconds", 86_401),
        ("silence_noise_db", 1),
        ("analysis_timeout_seconds", float("nan")),
    ],
)
def test_invalid_config_values_are_rejected(field: str, value: object) -> None:
    config = ScanConfig(**{field: value})
    with pytest.raises(ConfigError):
        validate_config(config)
