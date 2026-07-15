"""Tests for place-candidate ranking and name-aware similarity."""

import unittest

from geo_coordinate_query.matching import address_similarity
from geo_coordinate_query.query_service import PlaceQueryService


class _FakeProvider:
    def __init__(self, name, records):
        self.name = name
        self._records = records

    def search(self, keyword, city):
        return self._records


class QueryServiceTest(unittest.TestCase):
    def test_similarity_prefers_poi_name_over_unrelated_street_address(self):
        score = address_similarity(
            "武汉汉口历史风貌区",
            {
                "name": "汉口历史文化风貌区",
                "address": "吉庆民俗街05-105号",
            },
        )

        self.assertGreaterEqual(score, 0.7)

    def test_poi_candidate_outranks_wrong_geocode(self):
        service = PlaceQueryService(
            [
                _FakeProvider(
                    "amap",
                    [
                        {
                            "candidate_id": "wrong-geocode",
                            "name": "",
                            "address": "湖北省武汉市黄陂区汉口",
                            "city": "武汉市",
                            "district": "黄陂区",
                            "accurate": False,
                            "lng": 114.325141,
                            "lat": 30.699595,
                        },
                        {
                            "candidate_id": "right-poi",
                            "name": "汉口历史文化风貌区",
                            "address": "吉庆民俗街05-105号",
                            "type": "风景名胜;旅游景点",
                            "city": "武汉市",
                            "district": "江岸区",
                            "accurate": True,
                            "lng": 114.301055,
                            "lat": 30.592831,
                        },
                    ],
                )
            ]
        )

        result = service.resolve("武汉汉口历史风貌区", "武汉市", "amap")

        self.assertIsNotNone(result)
        self.assertEqual(result.data["candidate_id"], "right-poi")
        self.assertGreater(result.score, 0.7)

    def test_area_query_demotes_similarly_named_company(self):
        service = PlaceQueryService(
            [
                _FakeProvider(
                    "amap",
                    [
                        {
                            "candidate_id": "company",
                            "name": "汉口历史文化风貌街区经营管理有限责任公司",
                            "address": "武汉市江岸区洞庭街35号",
                            "city": "武汉市",
                            "type": "公司企业;公司",
                            "accurate": True,
                        },
                        {
                            "candidate_id": "district",
                            "name": "汉口历史文化风貌区",
                            "address": "吉庆民俗街05-105号",
                            "city": "武汉市",
                            "type": "风景名胜;旅游景点",
                            "accurate": True,
                        },
                    ],
                )
            ]
        )

        result = service.resolve("武汉汉口历史风貌区", "武汉市", "amap")

        self.assertEqual(result.data["candidate_id"], "district")
