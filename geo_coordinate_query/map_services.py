"""Map provider API clients for geocoding and nearby POI retrieval."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import requests

from .config import get_api_key, get_baidu_ak
from .coordinates import bd09_to_gcj02, gcj02_to_bd09, gcj02_to_wgs84
from .matching import address_similarity

logger = logging.getLogger(__name__)

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_TEXT_URL = "https://restapi.amap.com/v3/place/text"
AMAP_AROUND_URL = "https://restapi.amap.com/v3/place/around"
BAIDU_GEOCODE_URL = "https://api.map.baidu.com/geocoding/v3/"
BAIDU_PLACE_URL = "https://api.map.baidu.com/place/v2/search"

AMAP_ALL_TOP_LEVEL_TYPE_MAP = {
    "汽车服务": "010000",
    "汽车销售": "020000",
    "汽车维修": "030000",
    "摩托车服务": "040000",
    "餐饮服务": "050000",
    "购物服务": "060000",
    "生活服务": "070000",
    "体育休闲服务": "080000",
    "医疗保健服务": "090000",
    "住宿服务": "100000",
    "风景名胜": "110000",
    "商务住宅": "120000",
    "政府机构及社会团体": "130000",
    "科教文化服务": "140000",
    "交通设施服务": "150000",
    "金融保险服务": "160000",
    "公司企业": "170000",
    "道路附属设施": "180000",
    "地名地址信息": "190000",
    "公共设施": "200000",
    "室内设施": "970000",
}
AMAP_PUBLIC_SERVICE_TYPE_MAP = {
    "市政设施": "200000",
    "医疗保健": AMAP_ALL_TOP_LEVEL_TYPE_MAP["医疗保健服务"],
    "科教文化": "140000",
    "政府机构": "130000",
    "交通设施": "150000",
    "体育休闲": AMAP_ALL_TOP_LEVEL_TYPE_MAP["体育休闲服务"],
}
AMAP_COMMERCIAL_TYPE_MAP = {
    "商业服务": "050000|060000|100000|120000|160000",
}
AMAP_NEARBY_CATEGORIES = {**AMAP_PUBLIC_SERVICE_TYPE_MAP, **AMAP_COMMERCIAL_TYPE_MAP}
BAIDU_NEARBY_QUERIES = {
    "市政设施": ("公共设施", "公共厕所", "紧急避难场所"),
    "医疗保健": ("医院", "诊所", "社区卫生服务中心"),
    "科教文化": ("学校", "图书馆", "博物馆", "文化馆"),
    "政府机构": ("政府机关", "社区居委会", "派出所"),
    "交通设施": ("公交站", "地铁站", "交通枢纽"),
    "体育休闲": ("体育场馆", "公园", "健身中心"),
    "商业服务": ("餐饮", "购物", "住宿", "金融", "商务住宅"),
}


def amap_search_candidates(
    keyword: str,
    city: str = "",
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Return AMap geocode and POI candidates for a place query."""
    key = api_key or get_api_key()
    if not key or not keyword.strip():
        return []

    candidates = _amap_geocode_candidates(keyword, city, key)
    for query in _query_variants(keyword):
        candidates.extend(_amap_poi_candidates(query, city, key))
    return _deduplicate_candidates(candidates)


def baidu_search_candidates(
    keyword: str,
    city: str = "",
    ak: str | None = None,
) -> list[dict[str, Any]]:
    """Return Baidu geocode and POI candidates for a place query."""
    key = ak or get_baidu_ak()
    if not key or not keyword.strip():
        return []

    candidates = _baidu_geocode_candidates(keyword, city, key)
    for query in _query_variants(keyword):
        candidates.extend(_baidu_poi_candidates(query, city, key))
    return _deduplicate_candidates(candidates)


def geocode_search(
    keyword: str,
    city: str = "",
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """Return the first AMap geocoding candidate for compatibility."""
    key = api_key or get_api_key()
    if not key or not keyword.strip():
        return None
    candidates = _amap_geocode_candidates(keyword, city, key)
    return candidates[0] if candidates else None


def poi_search(
    keyword: str,
    city: str = "",
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """Return the first AMap POI candidate for compatibility."""
    key = api_key or get_api_key()
    if not key or not keyword.strip():
        return None
    candidates = _amap_poi_candidates(keyword, city, key)
    return candidates[0] if candidates else None


def smart_search(keyword: str, city: str = "") -> dict[str, Any] | None:
    """Return the most similar AMap candidate for a place query."""
    return _best_candidate(keyword, amap_search_candidates(keyword, city))


def baidu_geocode_search(
    keyword: str,
    city: str = "",
    ak: str | None = None,
) -> dict[str, Any] | None:
    """Return the first Baidu geocoding candidate for compatibility."""
    key = ak or get_baidu_ak()
    if not key or not keyword.strip():
        return None
    candidates = _baidu_geocode_candidates(keyword, city, key)
    return candidates[0] if candidates else None


def baidu_poi_search(
    keyword: str,
    city: str = "",
    ak: str | None = None,
) -> dict[str, Any] | None:
    """Return the first Baidu POI candidate for compatibility."""
    key = ak or get_baidu_ak()
    if not key or not keyword.strip():
        return None
    candidates = _baidu_poi_candidates(keyword, city, key)
    return candidates[0] if candidates else None


def baidu_smart_search(keyword: str, city: str = "") -> dict[str, Any] | None:
    """Return the most similar Baidu candidate for a place query."""
    return _best_candidate(keyword, baidu_search_candidates(keyword, city))


def amap_nearby_poi_search(
    lng: float,
    lat: float,
    radius: int,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Search requested public-facility and commercial POIs near a GCJ-02 point."""
    key = api_key or get_api_key()
    if not key:
        raise RuntimeError("未配置高德地图 API Key")

    records: list[dict[str, Any]] = []
    for category, poi_types in AMAP_NEARBY_CATEGORIES.items():
        page = 1
        while True:
            payload = _request_json(
                AMAP_AROUND_URL,
                {
                    "key": key,
                    "location": f"{lng},{lat}",
                    "radius": radius,
                    "types": poi_types,
                    "offset": 25,
                    "page": page,
                    "extensions": "all",
                },
            )
            if payload.get("status") != "1":
                raise RuntimeError(payload.get("info", "高德周边搜索失败"))
            pois = payload.get("pois", [])
            records.extend(_amap_nearby_record(category, poi) for poi in pois)
            if len(pois) < 25:
                break
            page += 1
    return _deduplicate_nearby_records(records)


def baidu_nearby_poi_search(
    lng: float,
    lat: float,
    radius: int,
    ak: str | None = None,
) -> list[dict[str, Any]]:
    """Search requested public-facility and commercial POIs near a GCJ-02 point."""
    key = ak or get_baidu_ak()
    if not key:
        raise RuntimeError("未配置百度地图 AK")

    bd_lng, bd_lat = gcj02_to_bd09(lng, lat)
    records: list[dict[str, Any]] = []
    for category, queries in BAIDU_NEARBY_QUERIES.items():
        for query in queries:
            page = 0
            while True:
                payload = _request_json(
                    BAIDU_PLACE_URL,
                    {
                        "ak": key,
                        "query": query,
                        "location": f"{bd_lat},{bd_lng}",
                        "radius": radius,
                        "scope": 2,
                        "page_size": 20,
                        "page_num": page,
                        "output": "json",
                    },
                )
                if payload.get("status") != 0:
                    raise RuntimeError(payload.get("message", "百度周边搜索失败"))
                results = payload.get("results", [])
                records.extend(_baidu_nearby_record(category, poi) for poi in results)
                total = int(payload.get("total", 0))
                if len(results) < 20 or (page + 1) * 20 >= total:
                    break
                page += 1
    return _deduplicate_nearby_records(records)


def nearby_poi_search(
    provider: str,
    lng: float,
    lat: float,
    radius: int,
) -> list[dict[str, Any]]:
    """Search nearby POIs through the requested map provider."""
    if provider == "amap":
        return amap_nearby_poi_search(lng, lat, radius)
    if provider == "baidu":
        return baidu_nearby_poi_search(lng, lat, radius)
    raise ValueError(f"不支持的地图服务: {provider}")


def _amap_geocode_candidates(
    keyword: str,
    city: str,
    key: str,
) -> list[dict[str, Any]]:
    payload = _request_json(
        AMAP_GEOCODE_URL,
        {"address": keyword.strip(), "city": city, "key": key},
        ignore_errors=True,
    )
    if payload.get("status") != "1":
        return []
    return [_amap_geocode_record(item) for item in payload.get("geocodes", [])]


def _amap_poi_candidates(
    keyword: str,
    city: str,
    key: str,
) -> list[dict[str, Any]]:
    payload = _request_json(
        AMAP_TEXT_URL,
        {
            "keywords": keyword.strip(),
            "city": city,
            "citylimit": "true" if city else "false",
            "key": key,
            "offset": 10,
            "extensions": "all",
        },
        ignore_errors=True,
    )
    if payload.get("status") != "1":
        return []
    return [_amap_poi_record(item) for item in payload.get("pois", [])]


def _baidu_geocode_candidates(
    keyword: str,
    city: str,
    key: str,
) -> list[dict[str, Any]]:
    payload = _request_json(
        BAIDU_GEOCODE_URL,
        {"address": keyword.strip(), "city": city, "ak": key, "output": "json"},
        ignore_errors=True,
    )
    if payload.get("status") != 0 or not payload.get("result"):
        return []
    return [_baidu_geocode_record(payload["result"])]


def _baidu_poi_candidates(
    keyword: str,
    city: str,
    key: str,
) -> list[dict[str, Any]]:
    payload = _request_json(
        BAIDU_PLACE_URL,
        {
            "query": keyword.strip(),
            "region": city,
            "city_limit": "true" if city else "false",
            "ak": key,
            "output": "json",
            "page_size": 10,
            "scope": 2,
        },
        ignore_errors=True,
    )
    if payload.get("status") != 0:
        return []
    return [_baidu_poi_record(item) for item in payload.get("results", [])]


def _amap_geocode_record(item: dict[str, Any]) -> dict[str, Any]:
    lng, lat = _split_location(item.get("location", ""))
    level = str(item.get("level", ""))
    return {
        "provider": "amap",
        "candidate_id": f"amap:geocode:{lng},{lat}",
        "lng": lng,
        "lat": lat,
        "province": item.get("province", ""),
        "city": item.get("city", ""),
        "district": item.get("district", ""),
        "address": item.get("formatted_address", ""),
        "name": "",
        "level": level,
        "accurate": level not in {"省", "市", "区县", "乡镇", "村庄"},
        "method": "高德地理编码",
        "coord_type": "GCJ-02",
    }


def _amap_poi_record(item: dict[str, Any]) -> dict[str, Any]:
    lng, lat = _split_location(item.get("location", ""))
    return {
        "provider": "amap",
        "candidate_id": f"amap:poi:{item.get('id', '') or f'{lng},{lat}'}",
        "lng": lng,
        "lat": lat,
        "province": item.get("pname", ""),
        "city": item.get("cityname", ""),
        "district": item.get("adname", ""),
        "address": item.get("address", ""),
        "name": item.get("name", ""),
        "tel": item.get("tel", ""),
        "type": item.get("type", ""),
        "accurate": True,
        "method": "高德 POI",
        "coord_type": "GCJ-02",
    }


def _baidu_geocode_record(item: dict[str, Any]) -> dict[str, Any]:
    location = item.get("location", {})
    bd_lng = float(location.get("lng", 0))
    bd_lat = float(location.get("lat", 0))
    lng, lat = bd09_to_gcj02(bd_lng, bd_lat)
    confidence = int(item.get("confidence", 0))
    level = str(item.get("level", ""))
    return {
        "provider": "baidu",
        "candidate_id": f"baidu:geocode:{bd_lng},{bd_lat}",
        "lng": lng,
        "lat": lat,
        "bd_lng": bd_lng,
        "bd_lat": bd_lat,
        "province": "",
        "city": "",
        "district": "",
        "address": item.get("formatted_address", ""),
        "name": "",
        "confidence": confidence,
        "level": level,
        "accurate": confidence >= 60 and level not in {"城市", "区县", "乡镇"},
        "method": "百度地理编码",
        "coord_type": "GCJ-02(由BD-09转换)",
    }


def _baidu_poi_record(item: dict[str, Any]) -> dict[str, Any]:
    location = item.get("location", {})
    bd_lng = float(location.get("lng", 0))
    bd_lat = float(location.get("lat", 0))
    lng, lat = bd09_to_gcj02(bd_lng, bd_lat)
    detail = item.get("detail_info", {})
    return {
        "provider": "baidu",
        "candidate_id": f"baidu:poi:{item.get('uid', '') or f'{bd_lng},{bd_lat}'}",
        "lng": lng,
        "lat": lat,
        "bd_lng": bd_lng,
        "bd_lat": bd_lat,
        "province": item.get("province", ""),
        "city": item.get("city", ""),
        "district": item.get("area", ""),
        "address": item.get("address", ""),
        "name": item.get("name", ""),
        "tel": item.get("telephone", ""),
        "type": detail.get("tag", item.get("tag", "")),
        "accurate": True,
        "method": "百度 POI",
        "coord_type": "GCJ-02(由BD-09转换)",
    }


def _request_json(
    url: str,
    params: dict[str, Any],
    ignore_errors: bool = False,
) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as err:
        if ignore_errors:
            logger.warning("地图服务请求失败: %s", err)
            return {}
        raise RuntimeError(f"地图服务请求失败: {err}") from err


def _query_variants(keyword: str) -> tuple[str, ...]:
    normalized = keyword.strip()
    variants = [normalized]
    historical_variant = normalized.replace("历史风貌", "历史文化风貌")
    if historical_variant != normalized:
        variants.append(historical_variant)
    return tuple(variants)


def _split_location(location: Any) -> tuple[float, float]:
    try:
        lng, lat = str(location).split(",", 1)
        return float(lng), float(lat)
    except (TypeError, ValueError):
        return 0.0, 0.0


def _deduplicate_candidates(
    candidates: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id", ""))
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        records.append(candidate)
    return records


def _best_candidate(
    keyword: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda result: (
            address_similarity(keyword, result),
            bool(result.get("accurate")),
        ),
    )


def _amap_nearby_record(category: str, poi: dict[str, Any]) -> dict[str, Any]:
    lng, lat = _split_location(poi.get("location", ""))
    wgs_lng, wgs_lat = gcj02_to_wgs84(lng, lat)
    return {
        "服务": "高德",
        "类别": category,
        "名称": poi.get("name", ""),
        "地址": poi.get("address", ""),
        "类型": poi.get("type", ""),
        "电话": poi.get("tel", ""),
        "距中心距离(米)": poi.get("distance", ""),
        "经度(GCJ-02)": lng,
        "纬度(GCJ-02)": lat,
        "WGS84经度": wgs_lng,
        "WGS84纬度": wgs_lat,
        "POI ID": poi.get("id", ""),
    }


def _baidu_nearby_record(category: str, poi: dict[str, Any]) -> dict[str, Any]:
    candidate = _baidu_poi_record(poi)
    wgs_lng, wgs_lat = gcj02_to_wgs84(candidate["lng"], candidate["lat"])
    return {
        "服务": "百度",
        "类别": category,
        "名称": candidate["name"],
        "地址": candidate["address"],
        "类型": candidate.get("type", ""),
        "电话": candidate.get("tel", ""),
        "距中心距离(米)": poi.get("distance", ""),
        "经度(GCJ-02)": candidate["lng"],
        "纬度(GCJ-02)": candidate["lat"],
        "WGS84经度": wgs_lng,
        "WGS84纬度": wgs_lat,
        "POI ID": poi.get("uid", ""),
    }


def _deduplicate_nearby_records(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique_records: list[dict[str, Any]] = []
    for record in records:
        record_id = str(record.get("POI ID", ""))
        if record_id and record_id in seen:
            continue
        seen.add(record_id)
        unique_records.append(record)
    return unique_records
