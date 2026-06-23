"""Batch coordinate conversion for Excel workbooks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time

import pandas as pd

from .coordinates import gcj02_to_wgs84

ProgressCallback = Callable[[str], None]
StatusCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class ConvertSummary:
    output_file: Path
    converted: int
    failed: int
    total: int

    @property
    def message(self) -> str:
        return f"完成! 转换成功:{self.converted} 失败:{self.failed} 共:{self.total}"


def convert_coordinate_excel(
    file_path: str | Path,
    output_path: str | Path | None = None,
    log: ProgressCallback | None = None,
    status: StatusCallback | None = None,
    sleep_seconds: float = 0.05,
) -> ConvertSummary:
    """Convert GCJ-02 longitude/latitude columns in an Excel workbook to WGS-84."""
    input_file = Path(file_path)
    df = pd.read_excel(input_file)
    if "经度" not in df.columns or "纬度" not in df.columns:
        raise ValueError('Excel文件必须包含 "经度" 和 "纬度" 列！\n请检查列名是否正确。')

    total = len(df)
    if log:
        log(f"读取文件: {input_file.name}，共{total}行")

    df["WGS84经度"] = None
    df["WGS84纬度"] = None
    converted = failed = 0

    for idx, row in df.iterrows():
        lng = row.get("经度")
        lat = row.get("纬度")
        if pd.notna(lng) and pd.notna(lat):
            try:
                wgs_lng, wgs_lat = gcj02_to_wgs84(float(lng), float(lat))
                df.at[idx, "WGS84经度"] = wgs_lng
                df.at[idx, "WGS84纬度"] = wgs_lat
                converted += 1
                if log:
                    log(f"[{idx + 1}/{total}] OK -> {wgs_lng},{wgs_lat}")
            except (TypeError, ValueError):
                failed += 1
                if log:
                    log(f"[{idx + 1}] 失败: 经纬度格式错误")
        else:
            failed += 1

        if status:
            pct = (idx + 1) / total * 100 if total else 100
            status(pct, f"转换中 {idx + 1}/{total}")
        time.sleep(sleep_seconds)

    output_file = Path(output_path) if output_path else input_file.with_name(f"{input_file.stem}_WGS84.xlsx")
    df.to_excel(output_file, index=False, engine="openpyxl")
    return ConvertSummary(output_file, converted, failed, total)
