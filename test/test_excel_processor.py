"""Tests for the unified Excel import and export workflow."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from geo_coordinate_query.excel_processor import process_excel
from geo_coordinate_query.query_service import PlaceCandidate


class _CandidateService:
    def search(self, keyword, city="", provider="auto"):
        return [
            PlaceCandidate(
                "amap",
                0.9,
                {
                    "provider": "amap",
                    "lng": 114.301055,
                    "lat": 30.592831,
                    "name": "汉口历史文化风貌区",
                    "address": "吉庆民俗街05-105号",
                    "city": "武汉市",
                    "district": "江岸区",
                    "method": "高德 POI",
                    "coord_type": "GCJ-02",
                    "accurate": True,
                },
            )
        ]


class ExcelProcessorTest(unittest.TestCase):
    @patch("geo_coordinate_query.excel_processor.PlaceQueryService", return_value=_CandidateService())
    def test_process_excel_writes_unified_result_columns(self, _service) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "input.xlsx"
            output_file = Path(directory) / "result.xlsx"
            pd.DataFrame({"名称": ["汉口历史文化风貌区"], "城市": ["武汉市"]}).to_excel(input_file, index=False)

            summary = process_excel(input_file, "auto", output_file, sleep_seconds=0)
            result = pd.read_excel(output_file)

        self.assertEqual(summary.accurate, 1)
        self.assertEqual(summary.fail, 0)
        self.assertEqual(result.at[0, "地图服务"], "amap")
        self.assertEqual(result.at[0, "匹配方式"], "高德 POI")
        self.assertEqual(result.at[0, "城市"], "武汉市")
        self.assertEqual(result.at[0, "API城市"], "武汉市")
        self.assertGreaterEqual(result.at[0, "地址相似度"], 0.7)
