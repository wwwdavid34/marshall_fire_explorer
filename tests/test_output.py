"""Tests for pipeline output modules."""

import json

from pipeline.output.parcel_json import _safe_float, _safe_int


class TestSafeConversions:
    """Test JSON-safe type conversions."""

    def test_safe_float_normal(self):
        assert _safe_float(3.14159) == 3.1416

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) is None

    def test_safe_int_normal(self):
        assert _safe_int(7) == 7

    def test_safe_int_none(self):
        assert _safe_int(None) is None

    def test_safe_int_float(self):
        assert _safe_int(7.9) == 7


class TestRegistryStructure:
    """Test registry.json output structure."""

    def test_registry_has_required_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pipeline.output.registry.RESULTS_DIR", tmp_path,
        )
        from pipeline.output.registry import write_registry_json
        write_registry_json()

        dest = tmp_path / "registry.json"
        assert dest.exists()
        data = json.loads(dest.read_text())
        assert "site" in data
        assert "aoi" in data
        assert "observation_dates" in data
        assert "data" in data
        assert data["aoi"]["bbox"] == [-105.16, 39.93, -105.07, 40.01]


class TestTimelineStructure:
    """Test timeline.json output structure."""

    def test_timeline_has_dates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pipeline.output.timeline_json.RESULTS_DIR", tmp_path,
        )
        monkeypatch.setattr(
            "pipeline.output.timeline_json.PROCESSED_DIR", tmp_path / "processed",
        )
        from pipeline.output.timeline_json import write_timeline_json
        write_timeline_json()

        dest = tmp_path / "timeline.json"
        assert dest.exists()
        data = json.loads(dest.read_text())
        assert "observation_dates" in data
        assert "pre_fire_date" in data
        assert data["pre_fire_date"] == "2021-11"
        assert len(data["observation_dates"]) == 5
