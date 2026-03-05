"""Smoke tests for environment configuration."""

from config.settings import AOI, OBSERVATION_DATES, get_config


def test_dev_config_defaults():
    config = get_config("dev")
    assert config.s3_endpoint_url == "http://localhost:4566"
    assert config.data_bucket == "dm-dev-data"


def test_aoi_is_valid_bbox():
    assert len(AOI) == 4
    west, south, east, north = AOI
    assert west < east
    assert south < north


def test_observation_dates_count():
    assert len(OBSERVATION_DATES) == 5
    assert OBSERVATION_DATES[0] == "2021-11"
    assert OBSERVATION_DATES[-1] == "2024-06"
