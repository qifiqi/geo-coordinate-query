import pandas as pd
import requests
import time
from urllib.parse import quote

# 高德地图API配置
gao_de_api_key = '9ae99783bce390962a1795e54ced3c07'

# 读取Excel文件
def read_excel_file(file_path):
    try:
        df = pd.read_excel(file_path)
        print(f"成功读取Excel文件，共{len(df)}行数据")
        print(f"列名: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"读取Excel文件失败: {e}")
        return None

# ========== 多种查询策略 ==========

# 策略1: geocode地理编码（地址 -> 坐标）
def geocode_search(keyword):
    encoded = quote(keyword.strip())
    url = f"https://restapi.amap.com/v3/geocode/geo?address={encoded}&key={gao_de_api_key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and data.get('count') != '0':
            geo = data['geocodes'][0]
            lng, lat = geo['location'].split(',')
            district = geo.get('district', '')
            city = geo.get('city', '')
            formatted = geo.get('formatted_address', '')
            detail = f"{city}{district} - {formatted}"
            # 判断精度：有district说明至少匹配到区级，否则只是城市中心点
            is_accurate = bool(district)
            return float(lng), float(lat), detail, is_accurate, "geocode"
    except:
        pass
    return None, None, None, False, "geocode"

# 策略2: POI搜索（名称关键词搜索，适合地标建筑）
def poi_search(keyword, city='武汉'):
    encoded = quote(keyword.strip())
    encoded_city = quote(city)
    url = f"https://restapi.amap.com/v3/place/text?keywords={encoded}&city={encoded_city}&key={gao_de_api_key}&offset=1"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and int(data.get('count', 0)) > 0:
            poi = data['pois'][0]
            lng, lat = poi['location'].split(',')
            name = poi.get('name', '')
            address = poi.get('address', '')
            district = poi.get('adname', '')
            city_name = poi.get('cityname', '')
            detail = f"{city_name}{district} - {name}({address}) [POI]"
            is_accurate = True  # POI匹配通常较准
            return float(lng), float(lat), detail, is_accurate, "POI"
    except:
        pass
    return None, None, None, False, "POI"

# 策略3: 输入提示 + 地理编码（先补全地址再编码）
def inputtip_geocode(keyword, city='武汉'):
    encoded = quote(keyword.strip())
    encoded_city = quote(city)
    url = f"https://restapi.amap.com/v3/assistant/inputtips?keywords={encoded}&city={encoded_city}&key={gao_de_api_key}&datatype=poi"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and len(data.get('tips', [])) > 0:
            tip = data['tips'][0]
            tip_id = tip.get('id', '')
            if tip_id:
                # 用ID直接查POI详情
                detail_url = f"https://restapi.amap.com/v3/place/detail?id={tip_id}&key={gao_de_api_key}"
                resp2 = requests.get(detail_url, timeout=10)
                data2 = resp2.json()
                if data2.get('status') == '1' and int(data2.get('count', 0)) > 0:
                    poi = data2['pois'][0]
                    lng, lat = poi['location'].split(',')
                    name = poi.get('name', '')
                    address = poi.get('address', '')
                    district = poi.get('adname', '')
                    city_name = poi.get('cityname', '')
                    detail = f"{city_name}{district} - {name}({address}) [提示]"
                    return float(lng), float(lat), detail, True, "输入提示"
    except:
        pass
    return None, None, None, False, "输入提示"

# ========== 多策略查询主函数 ==========

def smart_search(row):
    """多策略搜索，优先保证精度"""
    address = str(row.get('地址', '')).strip() if pd.notna(row.get('地址')) else ''
    name = str(row.get('名称', '')).strip() if pd.notna(row.get('名称')) else ''
    old_name = str(row.get('原名称', '')).strip() if pd.notna(row.get('原名称')) else ''

    candidates = []  # (lng, lat, detail, is_accurate, method, search_keyword)

    # === 第一轮：geocode 地址搜索 ===
    if address and len(address) > 3:
        lng, lat, detail, accurate, method = geocode_search(address)
        if lng:
            candidates.append((lng, lat, detail, accurate, method, address))
            if accurate:
                return candidates[-1]  # 精确匹配，直接返回

    # === 第二轮：POI搜索（用建筑名称） ===
    # 尝试名称
    if name and name != 'nan' and len(name) > 2 and name not in ['居民住宅', '幼儿园']:
        lng, lat, detail, accurate, method = poi_search(name)
        if lng:
            candidates.append((lng, lat, detail, accurate, method, name))
            if accurate:
                return candidates[-1]

    # 尝试原名称（历史建筑原名可能更有辨识度）
    if old_name and old_name != 'nan' and len(old_name) > 2:
        lng, lat, detail, accurate, method = poi_search(old_name)
        if lng:
            candidates.append((lng, lat, detail, accurate, method, old_name))
            if accurate:
                return candidates[-1]

    # === 第三轮：名称+地址组合POI搜索 ===
    if name and address and name != 'nan':
        combined = f"{name}({address})"
        lng, lat, detail, accurate, method = poi_search(combined)
        if lng:
            candidates.append((lng, lat, detail, accurate, method, combined))
            if accurate:
                return candidates[-1]

    # === 第四轮：输入提示辅助 ===
    search_key = name if (name and name != 'nan' and name not in ['居民住宅']) else address
    if search_key:
        lng, lat, detail, accurate, method = inputtip_geocode(search_key)
        if lng:
            candidates.append((lng, lat, detail, accurate, method, search_key))

    # 返回最佳结果（优先精确的，否则返回第一个有结果的）
    for c in candidates:
        if c[3]:  # is_accurate
            return c
    if candidates:
        return candidates[0]

    return (None, None, None, False, "无结果", "")

# ========== 批量处理 ==========

def process_addresses(df):
    df['经度'] = None
    df['纬度'] = None
    df['API返回地址'] = None
    df['匹配方式'] = None
    df['精度'] = None
    df['状态'] = None
    df['搜索关键词'] = None

    accurate_count = 0
    low_count = 0
    fail_count = 0
    start_time = time.time()

    print(f"\n{'='*70}")
    print(f"开始处理，共 {len(df)} 条记录")
    print(f"{'='*70}\n")

    for index, row in df.iterrows():
        address = str(row.get('地址', '')).strip() if pd.notna(row.get('地址')) else ''
        name = str(row.get('名称', '')).strip() if pd.notna(row.get('名称')) else ''

        print(f"[{index + 1}/{len(df)}] {name} | {address}")

        lng, lat, detail, is_accurate, method, keyword = smart_search(row)

        df.at[index, '经度'] = lng
        df.at[index, '纬度'] = lat
        df.at[index, 'API返回地址'] = detail
        df.at[index, '匹配方式'] = method
        df.at[index, '搜索关键词'] = keyword

        if lng is not None:
            accuracy_label = "精确" if is_accurate else "⚠️ 粗略"
            df.at[index, '精度'] = accuracy_label
            df.at[index, '状态'] = "成功" if is_accurate else "精度低"

            if is_accurate:
                accurate_count += 1
                print(f"   ✅ {method} | {lng}, {lat}")
                print(f"   📍 {detail}")
            else:
                low_count += 1
                print(f"   ⚠️  {method} | {lng}, {lat} (仅城市级，不精确!)")
                print(f"   📍 {detail}")
        else:
            fail_count += 1
            df.at[index, '精度'] = "失败"
            df.at[index, '状态'] = "失败"
            print(f"   ❌ 无结果")

        print(f"   ---")
        time.sleep(0.15)

    elapsed = time.time() - start_time

    # 打印详细统计
    print(f"\n{'='*70}")
    print(f"处理完成！耗时: {elapsed:.1f}秒")
    print(f"{'='*70}")
    print(f"  总记录数:     {len(df)}")
    print(f"  ✅ 精确匹配:  {accurate_count} ({accurate_count/len(df)*100:.1f}%)")
    print(f"  ⚠️  粗略匹配:  {low_count} ({low_count/len(df)*100:.1f}%)")
    print(f"  ❌ 失败:      {fail_count} ({fail_count/len(df)*100:.1f}%)")
    print(f"{'='*70}")

    # 打印不精确和失败的记录
    inaccurate = df[df['精度'] != '精确']
    if len(inaccurate) > 0:
        print(f"\n需要关注的记录 ({len(inaccurate)}条):")
        print(f"{'-'*70}")
        for idx, r in inaccurate.iterrows():
            status_icon = "⚠️" if r['精度'] == '⚠️ 粗略' else "❌"
            print(f"  {status_icon} 行{idx+1}: {r.get('名称','N/A')} | 地址: {r.get('地址','N/A')} | 方式: {r['匹配方式']} | {r['状态']}")
            if r.get('API返回地址'):
                print(f"     -> {r['API返回地址']}")

    return df

# 保存结果到Excel
def save_to_excel(df, output_file):
    try:
        df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\n结果已保存到: {output_file}")
        return True
    except Exception as e:
        print(f"保存Excel文件失败: {e}")
        return False

# 主函数
def main():
    file_path = "优秀历史建筑资料.xlsx"

    df = read_excel_file(file_path)
    if df is None:
        return

    print(f"\n数据前5行:")
    print(df[['名称', '地址']].head().to_string())

    df_result = process_addresses(df)

    output_file = "优秀历史建筑资料_经纬度.xlsx"
    save_to_excel(df_result, output_file)

if __name__ == "__main__":
    main()
