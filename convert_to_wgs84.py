"""
GCJ-02 转 WGS-84 坐标转换脚本
将 优秀历史建筑资料_经纬度.xlsx 中的经纬度从 GCJ-02 转换为 WGS-84
"""
import math
import pandas as pd
import os

# ========== GCJ-02 -> WGS-84 转换算法 ==========

PI = math.pi
A = 6378245.0  # 长半轴
EE = 0.00669342162296594323  # 偏心率平方

def _transform_lat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 *
            math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 *
            math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 *
            math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret

def _transform_lng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 *
            math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 *
            math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 *
            math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret

def gcj02_to_wgs84(lng, lat):
    """GCJ-02 转 WGS-84"""
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    wgs_lat = lat - dlat
    wgs_lng = lng - dlng
    return round(wgs_lng, 6), round(wgs_lat, 6)


def wgs84_to_gcj02(lng, lat):
    """WGS-84 转 GCJ-02（迭代逼近法，精度 < 0.000001 度）"""
    # 先用正向算法获取初始偏移
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    # GCJ-02 = WGS-84 + delta
    gcj_lng = lng + dlng
    gcj_lat = lat + dlat
    # 迭代修正（2次即可达到高精度）
    for _ in range(2):
        wgs_lng_check, wgs_lat_check = gcj02_to_wgs84(gcj_lng, gcj_lat)
        gcj_lng += (lng - wgs_lng_check)
        gcj_lat += (lat - wgs_lat_check)
    return round(gcj_lng, 6), round(gcj_lat, 6)


def convert_excel(input_path, output_path=None):
    """转换Excel文件中的GCJ-02坐标为WGS-84"""
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_WGS84{ext}"

    df = pd.read_excel(input_path)
    print(f"读取文件: {input_path}，共 {len(df)} 条记录")

    converted = 0
    wgs_lng_list = []
    wgs_lat_list = []

    for idx, row in df.iterrows():
        lng = row.get('经度')
        lat = row.get('纬度')
        if pd.notna(lng) and pd.notna(lat):
            try:
                wgs_lng, wgs_lat = gcj02_to_wgs84(float(lng), float(lat))
                wgs_lng_list.append(wgs_lng)
                wgs_lat_list.append(wgs_lat)
                converted += 1
            except Exception:
                wgs_lng_list.append(None)
                wgs_lat_list.append(None)
        else:
            wgs_lng_list.append(None)
            wgs_lat_list.append(None)

    df['WGS84经度'] = wgs_lng_list
    df['WGS84纬度'] = wgs_lat_list

    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"已转换 {converted} 条记录")
    print(f"结果已保存到: {output_path}")
    return output_path


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, "优秀历史建筑资料_经纬度.xlsx")
    if os.path.exists(input_file):
        convert_excel(input_file)
    else:
        print(f"文件不存在: {input_file}")
