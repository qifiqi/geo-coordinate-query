"""Tests for nearby POI map service queries."""

import unittest
from unittest.mock import Mock, patch

from geo_coordinate_query.map_services import (
    AMAP_NEARBY_CATEGORIES,
    AMAP_ALL_TOP_LEVEL_TYPE_MAP,
    AMAP_PUBLIC_SERVICE_TYPE_MAP,
    BAIDU_NEARBY_QUERIES,
    amap_nearby_poi_search,
    baidu_nearby_poi_search,
)
from geo_coordinate_query.query_service import PlaceCandidate
from nearby_poi import _nearby_provider, resolve_center


class NearbyPoiTest(unittest.TestCase):
    def test_all_amap_top_level_types_are_documented_in_mapping(self) -> None:
        self.assertEqual(len(AMAP_ALL_TOP_LEVEL_TYPE_MAP), 21)
        self.assertEqual(AMAP_ALL_TOP_LEVEL_TYPE_MAP["汽车服务"], "010000")
        self.assertEqual(AMAP_ALL_TOP_LEVEL_TYPE_MAP["室内设施"], "970000")

    def test_medical_service_mapping_uses_amap_090000(self) -> None:
        self.assertEqual(AMAP_PUBLIC_SERVICE_TYPE_MAP["医疗保健"], "090000")

    @patch("geo_coordinate_query.map_services.requests.get")
    def test_amap_nearby_search_uses_requested_type_codes(self, request) -> None:
        request.side_effect = [
            Mock(
                json=lambda category=category: {
                    "status": "1",
                    "pois": [{"id": category, "location": "114.3,30.6"}],
                },
                raise_for_status=Mock(),
            )
            for category in AMAP_NEARBY_CATEGORIES
        ]

        records = amap_nearby_poi_search(114.3, 30.6, 2000, "test-key")

        self.assertEqual([record["类别"] for record in records], list(AMAP_NEARBY_CATEGORIES))
        self.assertIn("WGS84经度", records[0])
        self.assertIn("WGS84纬度", records[0])
        self.assertEqual(
            [call.kwargs["params"]["types"] for call in request.call_args_list],
            list(AMAP_NEARBY_CATEGORIES.values()),
        )

    @patch("geo_coordinate_query.map_services.requests.get")
    def test_baidu_nearby_search_converts_response_to_gcj02(self, request) -> None:
        request.side_effect = [
            Mock(
                json=lambda: {"status": 0, "total": 1, "results": [{"uid": "public", "location": {"lng": 114.3065, "lat": 30.606}}]},
                raise_for_status=Mock(),
            ),
            *[
                Mock(json=lambda: {"status": 0, "total": 0, "results": []}, raise_for_status=Mock())
                for _ in range(sum(map(len, BAIDU_NEARBY_QUERIES.values())) - 1)
            ],
        ]

        records = baidu_nearby_poi_search(114.3, 30.6, 2000, "test-ak")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["服务"], "百度")
        self.assertEqual(records[0]["类别"], "市政设施")
        self.assertAlmostEqual(records[0]["经度(GCJ-02)"], 114.3, places=3)
        self.assertIn("WGS84经度", records[0])
        self.assertIn("location", request.call_args_list[0].kwargs["params"])

    @patch("nearby_poi.PlaceQueryService")
    def test_resolve_center_uses_unified_candidate_service(self, service_class) -> None:
        service_class.return_value.resolve.return_value = PlaceCandidate(
            "amap",
            0.8,
            {"lng": 114.3, "lat": 30.6, "provider": "amap"},
        )

        result = resolve_center("amap", "武汉汉口历史风貌区", "武汉市")

        self.assertEqual(result["lng"], 114.3)
        self.assertEqual(result["provider"], "amap")
        service_class.return_value.resolve.assert_called_once_with("武汉汉口历史风貌区", "武汉市", "amap")

    @patch("nearby_poi.get_api_key", return_value="")
    @patch("nearby_poi.get_baidu_ak", return_value="test-ak")
    def test_coordinate_only_auto_provider_uses_configured_baidu_key(self, baidu_key, amap_key) -> None:
        self.assertEqual(_nearby_provider("auto"), "baidu")
        amap_key.assert_called_once()
        baidu_key.assert_called_once()
