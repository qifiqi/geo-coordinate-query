"""Command-line interface for geocoding and coordinate conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from geo_coordinate_query.batch_convert import convert_coordinate_excel
from geo_coordinate_query.config import get_api_key, get_baidu_ak, get_config, update_config
from geo_coordinate_query.coordinates import gcj02_to_wgs84, wgs84_to_gcj02
from geo_coordinate_query.excel_processor import process_excel
from geo_coordinate_query.matching import address_similarity
from geo_coordinate_query.query_service import PlaceQueryService, ProviderName

Provider = ProviderName


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _summary_to_dict(summary: Any) -> dict[str, Any]:
    data = summary.__dict__.copy()
    data["output_file"] = str(data["output_file"])
    data["message"] = summary.message
    return data


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if not path.is_file():
        raise ValueError(f"不是文件: {path}")


def cmd_config(args: argparse.Namespace) -> int:
    values: dict[str, str] = {}
    if args.amap_key is not None:
        values["api_key"] = args.amap_key.strip()
    if args.baidu_ak is not None:
        values["baidu_ak"] = args.baidu_ak.strip()
    if values:
        update_config(**values)

    config = get_config()
    if args.json:
        _print_json(
            {
                "amap_key_set": bool(config.get("api_key")),
                "baidu_ak_set": bool(config.get("baidu_ak")),
            }
        )
    else:
        print(f"高德 Key: {'已配置' if get_api_key() else '未配置'}")
        print(f"百度 AK: {'已配置' if get_baidu_ak() else '未配置'}")
    return 0


def _query(provider: Provider, keyword: str, city: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    candidates = PlaceQueryService().search(keyword, city, provider)
    records = [candidate.as_dict() for candidate in candidates]
    return (records[0] if records else None), records


def cmd_query(args: argparse.Namespace) -> int:
    result, candidates = _query(args.provider, args.keyword, args.city)
    if not result:
        if args.json:
            _print_json({"ok": False, "keyword": args.keyword, "provider": args.provider, "candidates": []})
        else:
            print("未找到结果")
        return 2

    if args.wgs84:
        wgs_lng, wgs_lat = gcj02_to_wgs84(float(result["lng"]), float(result["lat"]))
        result = {**result, "wgs_lng": wgs_lng, "wgs_lat": wgs_lat}
    if args.similarity:
        result = {**result, "similarity": address_similarity(args.keyword, result)}

    if args.json:
        output = {"ok": True, "keyword": args.keyword, "provider": args.provider, "result": result}
        if args.candidates:
            output["candidates"] = candidates
        _print_json(output)
    else:
        print(f"服务: {args.provider}")
        print(f"关键词: {args.keyword}")
        print(f"坐标: {result.get('lng')}, {result.get('lat')} ({result.get('coord_type', 'GCJ-02')})")
        if args.wgs84:
            print(f"WGS-84: {result.get('wgs_lng')}, {result.get('wgs_lat')}")
        print(f"匹配方式: {result.get('method', '')}")
        print(f"地址: {result.get('address', '') or result.get('name', '')}")
        if args.similarity:
            print(f"相似度: {result.get('similarity', 0):.0%}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    input_file = Path(args.input)
    _require_file(input_file)
    output_file = Path(args.output) if args.output else None
    logger = None if args.quiet else print

    summary = process_excel(
        input_file,
        provider=args.provider,
        output_path=output_file,
        log=logger,
        sleep_seconds=args.delay,
        city=args.city,
    )

    if args.json:
        _print_json(_summary_to_dict(summary))
    else:
        print(summary.message)
        print(f"结果已保存到: {summary.output_file}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    if args.convert_command == "point":
        if args.direction == "gcj-to-wgs":
            lng, lat = gcj02_to_wgs84(args.lng, args.lat)
            coord_type = "WGS-84"
        else:
            lng, lat = wgs84_to_gcj02(args.lng, args.lat)
            coord_type = "GCJ-02"

        if args.json:
            _print_json({"lng": lng, "lat": lat, "coord_type": coord_type})
        else:
            print(f"{lng}, {lat} ({coord_type})")
        return 0

    input_file = Path(args.input)
    _require_file(input_file)
    summary = convert_coordinate_excel(
        input_file,
        output_path=Path(args.output) if args.output else None,
        log=None if args.quiet else print,
        sleep_seconds=args.delay,
    )
    if args.json:
        _print_json(_summary_to_dict(summary))
    else:
        print(summary.message)
        print(f"结果已保存到: {summary.output_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="地址经纬度查询、Excel 批处理和坐标转换 CLI 工具。",
    )
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers(dest="command")

    config = subparsers.add_parser("config", help="查看或保存 API Key 配置")
    config.add_argument("--amap-key", help="保存高德地图 Web 服务 Key")
    config.add_argument("--baidu-ak", help="保存百度地图 AK")
    config.add_argument("--json", action="store_true", help="以 JSON 输出配置状态")
    config.set_defaults(func=cmd_config)

    query = subparsers.add_parser("query", help="查询单个地址或建筑名称")
    query.add_argument("keyword", help="地址、建筑名或 POI 关键词")
    query.add_argument("-p", "--provider", choices=["amap", "baidu", "auto"], default="auto", help="地图服务")
    query.add_argument("--city", default="", help="城市名称，用于限制 POI 搜索范围")
    query.add_argument("--wgs84", action="store_true", help="同时输出 WGS-84 坐标")
    query.add_argument("--similarity", action="store_true", help="输出输入关键词与结果地址的相似度")
    query.add_argument("--candidates", action="store_true", help="JSON 输出中包含全部候选地点")
    query.add_argument("--json", action="store_true", help="以 JSON 输出")
    query.set_defaults(func=cmd_query)

    batch = subparsers.add_parser("batch", help="批量查询 Excel 文件")
    batch.add_argument("input", help="输入 Excel 文件，需包含 地址/名称/原名称 等列")
    batch.add_argument("-p", "--provider", choices=["amap", "baidu", "auto"], default="auto", help="地图服务")
    batch.add_argument("-o", "--output", help="输出 Excel 文件路径")
    batch.add_argument("--city", default="", help="城市名称；空值时优先读取输入表的“城市”列")
    batch.add_argument("--delay", type=float, default=0.15, help="每行请求间隔秒数")
    batch.add_argument("-q", "--quiet", action="store_true", help="不输出逐行处理日志")
    batch.add_argument("--json", action="store_true", help="以 JSON 输出处理摘要")
    batch.set_defaults(func=cmd_batch)

    convert = subparsers.add_parser("convert", help="坐标转换")
    convert_subparsers = convert.add_subparsers(dest="convert_command", required=True)

    point = convert_subparsers.add_parser("point", help="转换单个坐标点")
    point.add_argument("lng", type=float, help="经度")
    point.add_argument("lat", type=float, help="纬度")
    point.add_argument(
        "-d",
        "--direction",
        choices=["gcj-to-wgs", "wgs-to-gcj"],
        default="gcj-to-wgs",
        help="转换方向",
    )
    point.add_argument("--json", action="store_true", help="以 JSON 输出")
    point.set_defaults(func=cmd_convert)

    excel = convert_subparsers.add_parser("excel", help="批量转换 Excel 坐标列")
    excel.add_argument("input", help='输入 Excel 文件，需包含 "经度" 和 "纬度" 列')
    excel.add_argument("-o", "--output", help="输出 Excel 文件路径")
    excel.add_argument("--delay", type=float, default=0.05, help="每行处理间隔秒数")
    excel.add_argument("-q", "--quiet", action="store_true", help="不输出逐行处理日志")
    excel.add_argument("--json", action="store_true", help="以 JSON 输出处理摘要")
    excel.set_defaults(func=cmd_convert)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.func is None:
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        return 130
    except Exception as err:
        print(f"错误: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
