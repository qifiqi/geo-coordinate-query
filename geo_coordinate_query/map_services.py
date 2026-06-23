"""Map provider API clients."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests

from .config import get_api_key, get_baidu_ak
from .coordinates import bd09_to_gcj02

logger = logging.getLogger(__name__)


def geocode_search(keyword, api_key=None):
    """地理编码搜索"""
    key = api_key or get_api_key()
    if not key:
        return None
    encoded = quote(keyword.strip())
    url = f"https://restapi.amap.com/v3/geocode/geo?address={encoded}&key={key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and data.get('count') != '0':
            geo = data['geocodes'][0]
            lng, lat = geo['location'].split(',')
            district = geo.get('district', '')
            city = geo.get('city', '')
            province = geo.get('province', '')
            formatted = geo.get('formatted_address', '')
            level = geo.get('level', '')
            is_accurate = bool(district)
            return {
                'lng': float(lng), 'lat': float(lat),
                'province': province, 'city': city, 'district': district,
                'address': formatted, 'level': level,
                'accurate': is_accurate, 'method': 'geocode',
                'coord_type': 'GCJ-02'
            }
    except:
        pass
    return None


def poi_search(keyword, city='', api_key=None):
    """POI搜索"""
    key = api_key or get_api_key()
    if not key:
        return None
    encoded = quote(keyword.strip())
    url = f"https://restapi.amap.com/v3/place/text?keywords={encoded}&city={quote(city)}&key={key}&offset=3"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and int(data.get('count', 0)) > 0:
            poi = data['pois'][0]
            lng, lat = poi['location'].split(',')
            return {
                'lng': float(lng), 'lat': float(lat),
                'province': poi.get('pname', ''),
                'city': poi.get('cityname', ''),
                'district': poi.get('adname', ''),
                'address': poi.get('address', ''),
                'name': poi.get('name', ''),
                'tel': poi.get('tel', ''),
                'type': poi.get('type', ''),
                'accurate': True, 'method': 'POI',
                'coord_type': 'GCJ-02'
            }
    except:
        pass
    return None


def smart_search(keyword):
    """多策略智能搜索，返回最佳结果"""
    if not keyword or not keyword.strip():
        return None
    keyword = keyword.strip()
    candidates = []

    result = geocode_search(keyword)
    if result:
        candidates.append(result)
        if result['accurate']:
            return result

    result = poi_search(keyword)
    if result:
        candidates.append(result)
        if result['accurate']:
            return result

    return candidates[0] if candidates else None


def baidu_geocode_search(keyword, ak=None):
    """百度地图地理编码搜索"""
    key = ak or get_baidu_ak()
    if not key:
        return None
    encoded = quote(keyword.strip())
    url = f"https://api.map.baidu.com/geocoding/v3/?address={encoded}&ak={key}&output=json"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == 0 and data.get('result'):
            result = data['result']
            location = result.get('location', {})
            lng = location.get('lng', 0)
            lat = location.get('lat', 0)
            # 百度返回BD-09坐标，转换为GCJ-02
            gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
            confidence = result.get('confidence', 0)
            level = result.get('level', '')
            is_accurate = confidence >= 50 and level not in ['城市', '区县', '乡镇']
            return {
                'lng': gcj_lng, 'lat': gcj_lat,
                'bd_lng': lng, 'bd_lat': lat,
                'province': '', 'city': '', 'district': '',
                'address': keyword.strip(),
                'confidence': confidence, 'level': level,
                'accurate': is_accurate, 'method': '百度geocode',
                'coord_type': 'GCJ-02(由BD-09转换)'
            }
    except Exception:
        pass
    return None


def baidu_poi_search(keyword, city='', ak=None):
    """百度地图POI搜索"""
    key = ak or get_baidu_ak()
    if not key:
        return None
    encoded = quote(keyword.strip())
    encoded_city = quote(city) if city else ''
    url = f"https://api.map.baidu.com/place/v2/search?query={encoded}&region={encoded_city}&ak={key}&output=json&page_size=3"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == 0 and data.get('results') and len(data['results']) > 0:
            poi = data['results'][0]
            location = poi.get('location', {})
            lng = location.get('lng', 0)
            lat = location.get('lat', 0)
            # 百度返回BD-09坐标，转换为GCJ-02
            gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
            province = poi.get('province', '')
            city_name = poi.get('city', '')
            area = poi.get('area', '')
            address = poi.get('address', '')
            name = poi.get('name', '')
            overall_rating = poi.get('overall_rating', '')
            return {
                'lng': gcj_lng, 'lat': gcj_lat,
                'bd_lng': lng, 'bd_lat': lat,
                'province': province, 'city': city_name, 'district': area,
                'address': address, 'name': name,
                'tel': poi.get('telephone', ''),
                'type': poi.get('tag', ''),
                'rating': overall_rating,
                'accurate': True, 'method': '百度POI',
                'coord_type': 'GCJ-02(由BD-09转换)'
            }
    except Exception:
        pass
    return None


def baidu_smart_search(keyword):
    """百度地图多策略智能搜索"""
    if not keyword or not keyword.strip():
        return None
    keyword = keyword.strip()
    candidates = []

    result = baidu_geocode_search(keyword)
    if result:
        candidates.append(result)
        if result['accurate']:
            return result

    result = baidu_poi_search(keyword)
    if result:
        candidates.append(result)
        if result['accurate']:
            return result

    return candidates[0] if candidates else None

