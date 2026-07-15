"""Excel row preparation and provider-independent batch geocoding."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import pandas as pd

from .coordinates import gcj02_to_wgs84
from .matching import address_similarity
from .query_service import PlaceQueryService, ProviderName

ProgressCallback = Callable[[str], None]
StatusCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class BatchSummary:
    """Summary of one workbook geocoding run."""

    output_file: Path
    accurate: int
    low: int
    fail: int
    total: int

    @property
    def message(self) -> str:
        return f"完成! 精确:{self.accurate} 粗略:{self.low} 失败:{self.fail} 共:{self.total}"


def _cell_text(row: pd.Series, column: str) -> str:
    value = row.get(column)
    return "" if pd.isna(value) else str(value).strip()


def build_search_address(row: pd.Series, city: str = "") -> str:
    """Build the primary query from the conventional source columns."""
    return next(iter(_row_queries(row, city)), "")


def smart_search_excel(
    row: pd.Series,
    provider: ProviderName = "amap",
    service: PlaceQueryService | None = None,
    city: str = "",
) -> tuple[dict[str, Any] | None, str]:
    """Find the best map candidate for one source workbook row."""
    query_service = service or PlaceQueryService()
    candidates: list[tuple[dict[str, Any], str]] = []
    query_city = _cell_text(row, "城市") or city
    for query in _row_queries(row, query_city):
        for candidate in query_service.search(query, query_city, provider):
            candidates.append((candidate.as_dict(), query))
    if not candidates:
        return None, ""

    result, query = max(
        candidates,
        key=lambda item: (float(item[0].get("similarity", 0)), bool(item[0].get("accurate"))),
    )
    return result, query


def prepare_result_columns(df: pd.DataFrame) -> None:
    """Create the output fields added by the batch geocoding process."""
    columns: dict[str, Any] = {
        "经度": None,
        "纬度": None,
        "WGS84经度": None,
        "WGS84纬度": None,
        "坐标系": "GCJ-02",
        "地图服务": None,
        "API省份": None,
        "API城市": None,
        "API区县": None,
        "API返回地址": None,
        "匹配方式": None,
        "精度": None,
        "地址相似度": None,
    }
    for column, value in columns.items():
        df[column] = value


def write_geocode_result(
    df: pd.DataFrame,
    idx: int,
    search_kw: str,
    result: dict[str, Any],
    log: ProgressCallback | None = None,
) -> float:
    """Write one candidate to a workbook row and return its similarity."""
    df.at[idx, "经度"] = result["lng"]
    df.at[idx, "纬度"] = result["lat"]
    try:
        wgs_lng, wgs_lat = gcj02_to_wgs84(float(result["lng"]), float(result["lat"]))
        df.at[idx, "WGS84经度"] = wgs_lng
        df.at[idx, "WGS84纬度"] = wgs_lat
    except (TypeError, ValueError) as err:
        if log:
            log(f"  [警告] 第{idx + 1}行 WGS-84转换失败: {err}")

    similarity = address_similarity(search_kw, result)
    df.at[idx, "地址相似度"] = similarity
    df.at[idx, "地图服务"] = result.get("provider", "")
    df.at[idx, "API省份"] = result.get("province", "")
    df.at[idx, "API城市"] = result.get("city", "")
    df.at[idx, "API区县"] = result.get("district", "")
    df.at[idx, "API返回地址"] = result.get("address", "") or result.get("name", "")
    df.at[idx, "匹配方式"] = result.get("method", "")
    df.at[idx, "坐标系"] = result.get("coord_type", "GCJ-02")
    return similarity


def process_excel(
    file_path: str | Path,
    provider: ProviderName = "amap",
    output_path: str | Path | None = None,
    log: ProgressCallback | None = None,
    status: StatusCallback | None = None,
    sleep_seconds: float = 0.15,
    city: str = "",
) -> BatchSummary:
    """Geocode an Excel file through the selected map provider strategy."""
    input_file = Path(file_path)
    df = pd.read_excel(input_file)
    total = len(df)
    if log:
        log(f"读取文件: {input_file.name}，共{total}行，服务:{provider}")

    prepare_result_columns(df)
    accurate = low = fail = 0
    service = PlaceQueryService()
    for idx, row in df.iterrows():
        result, search_kw = smart_search_excel(row, provider, service, city)
        if result:
            similarity = write_geocode_result(df, idx, search_kw, result, log)
            is_accurate = bool(result.get("accurate")) and similarity >= 0.5
            df.at[idx, "精度"] = "精确" if is_accurate else "粗略"
            accurate += int(is_accurate)
            low += int(not is_accurate)
            if log:
                quality = "OK" if is_accurate else "LOW"
                log(
                    f"[{idx + 1}/{total}] {quality} {result['lng']},{result['lat']} "
                    f"({result.get('address') or result.get('name', '')}) "
                    f"(相似度:{similarity:.0%})"
                )
        else:
            fail += 1
            df.at[idx, "精度"] = "失败"
            if log:
                log(f"[{idx + 1}/{total}] FAIL")

        if status:
            percent = (idx + 1) / total * 100 if total else 100
            status(percent, f"处理中 {idx + 1}/{total}")
        time.sleep(sleep_seconds)

    output_file = Path(output_path) if output_path else input_file.with_name(
        f"{input_file.stem}_{_provider_label(provider)}经纬度.xlsx"
    )
    df.to_excel(output_file, index=False, engine="openpyxl")
    return BatchSummary(output_file, accurate, low, fail, total)


def process_amap_excel(
    file_path: str | Path,
    output_path: str | Path | None = None,
    log: ProgressCallback | None = None,
    status: StatusCallback | None = None,
    sleep_seconds: float = 0.15,
    city: str = "",
) -> BatchSummary:
    """Compatibility wrapper for an AMap-only Excel batch run."""
    return process_excel(file_path, "amap", output_path, log, status, sleep_seconds, city)


def _row_queries(row: pd.Series, city: str) -> tuple[str, ...]:
    address = _cell_text(row, "地址")
    name = _cell_text(row, "名称")
    old_name = _cell_text(row, "原名称")
    queries: list[str] = []
    if address and len(address) > 3:
        queries.append(address)
    if name and len(name) > 2 and name not in {"居民住宅", "幼儿园"}:
        queries.append(f"{city}{name}")
    if old_name and len(old_name) > 2:
        queries.append(f"{city}{old_name}")
    if name and address:
        queries.append(f"{name} {address}")
    return tuple(dict.fromkeys(queries))


def _provider_label(provider: ProviderName) -> str:
    return {"amap": "高德", "baidu": "百度", "auto": "自动"}[provider]
