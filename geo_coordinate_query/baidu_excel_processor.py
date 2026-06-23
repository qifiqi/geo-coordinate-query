"""Baidu Maps Excel batch geocoding."""

from __future__ import annotations

from pathlib import Path
import time

import pandas as pd

from .excel_processor import (
    BatchSummary,
    ProgressCallback,
    StatusCallback,
    build_search_address,
    prepare_result_columns,
    write_geocode_result,
)
from .map_services import baidu_smart_search


def process_baidu_excel(
    file_path: str | Path,
    output_path: str | Path | None = None,
    log: ProgressCallback | None = None,
    status: StatusCallback | None = None,
    sleep_seconds: float = 0.15,
) -> BatchSummary:
    """Geocode an Excel file with Baidu Maps and save a sibling workbook."""
    input_file = Path(file_path)
    df = pd.read_excel(input_file)
    total = len(df)
    if log:
        log(f"读取文件: {input_file.name}，共{total}行")

    prepare_result_columns(df)
    accurate = low = fail = 0

    for idx, row in df.iterrows():
        search_kw = build_search_address(row)
        result = baidu_smart_search(search_kw)

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

    output_file = Path(output_path) if output_path else input_file.with_name(f"{input_file.stem}_百度经纬度.xlsx")
    df.to_excel(output_file, index=False, engine="openpyxl")
    return BatchSummary(output_file, accurate, low, fail, total)
