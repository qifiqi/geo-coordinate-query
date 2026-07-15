"""Fetch public-facility and commercial POIs near a named place."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from geo_coordinate_query.config import get_api_key, get_baidu_ak
from geo_coordinate_query.map_services import (
    nearby_poi_search,
)
from geo_coordinate_query.query_service import PlaceQueryService, ProviderName


def resolve_center(provider: ProviderName, address: str, city: str) -> dict[str, object]:
    """Resolve a named place to a GCJ-02 coordinate."""
    candidate = PlaceQueryService().resolve(address, city, provider)
    if not candidate:
        raise RuntimeError(f"未能定位地点：{address}。请补充更具体的地址或使用 --lng/--lat。")
    return candidate.as_dict()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="查询地点周边的公共服务设施和商业 POI")
    parser.add_argument("address", nargs="?", help="中心地点名称或详细地址；未提供时将交互输入")
    parser.add_argument("--provider", choices=["amap", "baidu", "auto"], default="auto", help="地图服务，默认自动对比")
    parser.add_argument("--city", default="", help="城市名称，例如：武汉市")
    parser.add_argument("--lng", type=float, help="中心点经度（GCJ-02），与 --lat 同时使用")
    parser.add_argument("--lat", type=float, help="中心点纬度（GCJ-02），与 --lng 同时使用")
    parser.add_argument("--radius", type=int, default=2000, help="检索半径，单位米，默认 2000")
    parser.add_argument("--output", type=Path, default=Path("周边POI.xlsx"), help="输出 Excel 文件")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.radius <= 50000:
        raise ValueError("radius 必须在 1 到 50000 米之间")
    if (args.lng is None) != (args.lat is None):
        raise ValueError("--lng 和 --lat 必须同时提供")
    if args.provider == "amap" and not get_api_key():
        raise RuntimeError("未配置高德地图 API Key，请先执行: python main.py config --amap-key YOUR_KEY")
    if args.provider == "baidu" and not get_baidu_ak():
        raise RuntimeError("未配置百度地图 AK，请先执行: python main.py config --baidu-ak YOUR_AK")

    address = (args.address or input("请输入中心地点名称或地址：")).strip()
    if args.lng is None and not address:
        raise ValueError("请提供地点名称/地址，或同时提供 --lng 和 --lat")
    if args.lng is not None:
        provider = _nearby_provider(args.provider)
        center = {"lng": args.lng, "lat": args.lat, "provider": provider}
    else:
        center = resolve_center(args.provider, address, args.city)
    provider = str(center["provider"])
    lng, lat = float(center["lng"]), float(center["lat"])
    records = nearby_poi_search(provider, lng, lat, args.radius)

    pd.DataFrame(records).to_excel(args.output, index=False)
    print(f"中心点: {lng}, {lat} (GCJ-02, {provider})")
    print(f"已导出 {len(records)} 条 POI：{args.output.resolve()}")
    return 0


def _nearby_provider(provider: ProviderName) -> str:
    if provider != "auto":
        return provider
    if get_api_key():
        return "amap"
    if get_baidu_ak():
        return "baidu"
    raise RuntimeError("未配置高德地图 API Key 或百度地图 AK")


if __name__ == "__main__":
    raise SystemExit(main())
