"""Tests for pipeline processing modules."""

import numpy as np


class TestSarProcessing:
    """Test SAR processing logic (no I/O)."""

    def test_linear_to_db(self):
        from pipeline.process.sar import _linear_to_db
        linear = np.array([1.0, 0.1, 0.01, 0.0])
        db = _linear_to_db(linear)
        assert np.isclose(db[0], 0.0)
        assert np.isclose(db[1], -10.0)
        assert np.isclose(db[2], -20.0)
        assert np.isnan(db[3])  # log10(0) → NaN

    def test_compute_change(self):
        from pipeline.process.sar import _compute_change
        pre = np.array([-5.0, -10.0, -8.0])
        post = np.array([-9.0, -10.0, -4.0])
        change = _compute_change(pre, post)
        np.testing.assert_array_equal(change, [-4.0, 0.0, 4.0])


class TestLandsatProcessing:
    """Test Landsat processing logic (no I/O)."""

    def test_sr_scale(self):
        from pipeline.process.landsat import _apply_sr_scale
        # DN=10000 → 10000 * 0.0000275 - 0.174 = 0.101
        dn = np.array([10000.0, 0.0, 50000.0])
        sr = _apply_sr_scale(dn)
        assert np.isclose(sr[0], 0.101, atol=0.001)
        assert sr[1] == 0.0  # clipped
        assert sr[2] == 1.0  # clipped

    def test_st_scale(self):
        from pipeline.process.landsat import _apply_st_scale
        # DN=50000 → 50000 * 0.00341802 + 149.0 = 319.901 K
        dn = np.array([50000.0])
        temp = _apply_st_scale(dn)
        assert np.isclose(temp[0], 319.901, atol=0.01)

    def test_normalized_difference(self):
        from pipeline.process.landsat import _normalized_difference
        a = np.array([0.5, 0.0, 0.3])
        b = np.array([0.3, 0.0, 0.3])
        nd = _normalized_difference(a, b)
        assert np.isclose(nd[0], 0.25)
        assert np.isnan(nd[1])  # 0/0
        assert np.isclose(nd[2], 0.0)


class TestLidarProcessing:
    """Test LiDAR processing helpers."""

    def test_build_pdal_pipeline_ground(self):
        from pipeline.process.lidar import _build_pdal_pipeline
        pipe = _build_pdal_pipeline("input.laz", "output.tif", "ground")
        types = [step["type"] for step in pipe]
        assert "readers.las" in types
        assert "filters.smrf" in types
        assert "writers.gdal" in types

    def test_build_pdal_pipeline_first(self):
        from pipeline.process.lidar import _build_pdal_pipeline
        pipe = _build_pdal_pipeline("input.laz", "output.tif", "first")
        types = [step["type"] for step in pipe]
        assert "filters.range" in types
        # Should filter ReturnNumber[1:1]
        range_step = next(s for s in pipe if s["type"] == "filters.range")
        assert "ReturnNumber" in range_step["limits"]
