"""Excel row preparation and batch geocoding helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import pandas as pd

from .coordinates import gcj02_to_wgs84
from .map_services import geocode_search, poi_search
from .matching import address_similarity

ProgressCallback = Callable[[str], None]
StatusCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class BatchSummary:
    output_file: Path
    accurate: int
    low: int
    fail: int
    total: int

    @property
    def message(self) -> str:
        return (
            f"完成! 精确:{self.accurate} 粗略:{self.low} "
            f"失败:{self.fail} 共:{self.total}"
        )


def _cell_text(row: pd.Series, column: str) -> str:
    value = row.get(column)
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_search_address(row: pd.Series) -> str:
    """Build the best search keyword from one source workbook row."""
    address = _cell_text(row, "地址")
    name = _cell_text(row, "名称")
    old_name = _cell_text(row, "原名称")

    if address and len(address) > 3:
        return address
    if name and name != "nan" and len(name) > 2:
        return f"武汉市{name}"
    if old_name and old_name != "nan" and len(old_name) > 2:
        return f"武汉市{old_name}"
    return address or name


def smart_search_excel(row: pd.Series) -> tuple[dict[str, Any] | None, str]:
    """Search one Excel row with address, name, and old-name fallbacks."""
    address = _cell_text(row, "地址")
    name = _cell_text(row, "名称")
    old_name = _cell_text(row, "原名称")
    candidates: list[tuple[dict[str, Any], str]] = []

    if address and len(address) > 3:
        result = geocode_search(address)
        if result:
            candidates.append((result, address))
            if result["accurate"]:
                return result, address

    if name and name != "nan" and len(name) > 2 and name not in ["居民住宅", "幼儿园"]:
        result = poi_search(name)
        if result:
            candidates.append((result, name))
            if result["accurate"]:
                return result, name

    if old_name and old_name != "nan" and len(old_name) > 2:
        result = poi_search(old_name)
        if result:
            candidates.append((result, old_name))
            if result["accurate"]:
                return result, old_name

    if name and address and name != "nan":
        combined = f"{name}({address})"
        result = poi_search(combined)
        if result:
            candidates.append((result, combined))

    for candidate, keyword in candidates:
        if candidate.get("accurate"):
            return candidate, keyword
    if candidates:
        return candidates[0]
    return None, ""


def prepare_result_columns(df: pd.DataFrame) -> None:
    """Create the columns written by the batch geocoding process."""
    columns: dict[str, Any] = {
        "经度": None,
        "纬度": None,
        "WGS84经度": None,
        "WGS84纬度": None,
        "坐标系": "GCJ-02",
        "省份": None,
        "城市": None,
        "区县": None,
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
    """Write one provider result into a workbook row and return similarity."""
    df.at[idx, "经度"] = result["lng"]
    df.at[idx, "纬度"] = result["lat"]
    try:
        wgs_lng, wgs_lat = gcj02_to_wgs84(
            float(result["lng"]),
            float(result["lat"]),
        )
        df.at[idx, "WGS84经度"] = wgs_lng
        df.at[idx, "WGS84纬度"] = wgs_lat
    except (TypeError, ValueError) as err:
        if log:
            log(f"  [警告] 第{idx + 1}行 WGS-84转换失败: {err}")

    sim = address_similarity(search_kw, result)
    df.at[idx, "地址相似度"] = sim
    df.at[idx, "省份"] = result.get("province", "")
    df.at[idx, "城市"] = result.get("city", "")
    df.at[idx, "区县"] = result.get("district", "")
    df.at[idx, "API返回地址"] = result.get("address", "") or result.get("name", "")
    df.at[idx, "匹配方式"] = result.get("method", "")
    df.at[idx, "坐标系"] = result.get("coord_type", "GCJ-02")
    return sim


def process_amap_excel(
    file_path: str | Path,
    output_path: str | Path | None = None,
    log: ProgressCallback | None = None,
    status: StatusCallback | None = None,
    sleep_seconds: float = 0.15,
) -> BatchSummary:
    """Geocode an Excel file with AMap and save a sibling result workbook."""
    input_file = Path(file_path)
    df = pd.read_excel(input_file)
    total = len(df)
    if log:
        log(f"读取文件: {input_file.name}，共{total}行")

    prepare_result_columns(df)
    accurate = low = fail = 0

    for idx, row in df.iterrows():
        search_kw = build_search_address(row)
        result, _ = smart_search_excel(row)

        if result:
            sim = write_geocode_result(df, idx, search_kw, result, log)
            if result.get("accurate"):
                df.at[idx, "精度"] = "精确"
                accurate += 1
            else:
                df.at[idx, "精度"] = "粗略"
                low += 1

            status_text = "OK" if result.get("accurate") else "LOW"
            sim_warn = " [相似度低]" if sim < 0.4 else ""
            if log:
                log(
                    f"[{idx + 1}/{total}] {status_text} {result['lng']},{result['lat']} "
                    f"({result.get('address', '')}){sim_warn} (相似度:{sim:.0%})"
                )
        else:
            fail += 1
            df.at[idx, "精度"] = "失败"
            if log:
                log(f"[{idx + 1}/{total}] FAIL")

        if status:
            pct = (idx + 1) / total * 100 if total else 100
            status(pct, f"处理中 {idx + 1}/{total}")
        time.sleep(sleep_seconds)

    output_file = Path(output_path) if output_path else input_file.with_name(f"{input_file.stem}_经纬度.xlsx")
    df.to_excel(output_file, index=False, engine="openpyxl")
    return BatchSummary(output_file, accurate, low, fail, total)
