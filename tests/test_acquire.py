"""Tests for pipeline acquisition modules (mocked — no network calls)."""

from unittest.mock import MagicMock, patch

from config.settings import AOI, OBSERVATION_DATES


class TestSentinel1:
    """Test sentinel1 acquisition with mocked STAC client."""

    @patch("pipeline.acquire.sentinel1.pystac_client.Client")
    def test_acquire_sentinel1_searches_all_dates(self, mock_client_cls, tmp_path):
        mock_catalog = MagicMock()
        mock_client_cls.open.return_value = mock_catalog
        # Return empty results so download is skipped
        mock_search = MagicMock()
        mock_search.items.return_value = iter([])
        mock_catalog.search.return_value = mock_search

        with patch("pipeline.acquire.sentinel1.OUT_DIR", tmp_path):
            from pipeline.acquire.sentinel1 import acquire_sentinel1
            acquire_sentinel1()

        assert mock_catalog.search.call_count == len(OBSERVATION_DATES)

    @patch("pipeline.acquire.sentinel1.pystac_client.Client")
    def test_acquire_sentinel1_uses_correct_collection(self, mock_client_cls):
        mock_catalog = MagicMock()
        mock_client_cls.open.return_value = mock_catalog
        mock_search = MagicMock()
        mock_search.items.return_value = iter([])
        mock_catalog.search.return_value = mock_search

        from pipeline.acquire.sentinel1 import acquire_sentinel1
        acquire_sentinel1()

        for call in mock_catalog.search.call_args_list:
            assert call.kwargs["collections"] == ["sentinel-1-grd"]
            assert call.kwargs["bbox"] == AOI


class TestLandsat:
    """Test landsat acquisition with mocked STAC client."""

    @patch("pipeline.acquire.landsat.pystac_client.Client")
    def test_acquire_landsat_applies_cloud_filter(self, mock_client_cls):
        mock_catalog = MagicMock()
        mock_client_cls.open.return_value = mock_catalog
        mock_search = MagicMock()
        mock_search.items.return_value = iter([])
        mock_catalog.search.return_value = mock_search

        from pipeline.acquire.landsat import acquire_landsat
        acquire_landsat()

        for call in mock_catalog.search.call_args_list:
            assert call.kwargs["collections"] == ["landsat-c2-l2"]
            assert "eo:cloud_cover" in call.kwargs["query"]


class TestLidar:
    """Test lidar acquisition with mocked HTTP."""

    @patch("pipeline.acquire.lidar.requests.get")
    def test_acquire_lidar_calls_tnm_api(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"items": []}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        from pipeline.acquire.lidar import acquire_lidar
        acquire_lidar()

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "tnmaccess.nationalmap.gov" in args[0]
        assert "Lidar Point Cloud" in kwargs["params"]["datasets"]


class TestParcelsPermits:
    """Test parcels/permits acquisition with mocked HTTP."""

    def test_check_local_data_returns_dict(self):
        from pipeline.acquire.parcels_permits import check_local_data
        status = check_local_data()
        assert "parcel_shp" in status
        assert "permits_csv" in status
        assert "account_parcels_csv" in status

    @patch("pipeline.acquire.parcels_permits.requests.get")
    def test_acquire_fema_damage_queries_fema(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"features": []}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        with patch("pipeline.acquire.parcels_permits.OUT_GROUND_TRUTH", tmp_path):
            from pipeline.acquire.parcels_permits import acquire_fema_damage
            acquire_fema_damage()

        args, kwargs = mock_get.call_args
        assert "fema.gov" in args[0]
