import pandas as pd
import math
import os

# ========== GCJ-02 转 WGS-84 核心算法 ==========
def gcj02_to_wgs84(lng, lat):
    """GCJ-02(火星坐标) 转 WGS-84"""
    if abs(lng) < 1 or abs(lat) < 1:  # 异常值检查
        return lng, lat
    
    a = 6378245.0
    ee = 0.00669342162296594323
    
    def _transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    
    def _transform_lon(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret
    
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlon = _transform_lon(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    wgs_lat = lat - dlat
    wgs_lng = lng - dlon
    return wgs_lng, wgs_lat


# ========== 处理Excel文件 ==========
def convert_excel_coordinates(input_file, output_file=None, lng_col='经度', lat_col='纬度'):
    """
    转换Excel文件中的GCJ-02坐标为WGS-84
    
    参数:
        input_file: 输入的Excel文件路径
        output_file: 输出的Excel文件路径（可选，默认在原文件名后加'_wgs84'）
        lng_col: 经度列名，默认'经度'
        lat_col: 纬度列名，默认'纬度'
    """
    # 读取Excel文件
    print(f"正在读取文件: {input_file}")
    df = pd.read_excel(input_file)
    
    # 检查列是否存在
    if lng_col not in df.columns:
        raise ValueError(f"未找到经度列: {lng_col}，可用列: {list(df.columns)}")
    if lat_col not in df.columns:
        raise ValueError(f"未找到纬度列: {lat_col}，可用列: {list(df.columns)}")
    
    print(f"共读取 {len(df)} 条记录")
    print(f"原始坐标范围 - 经度: [{df[lng_col].min():.6f}, {df[lat_col].max():.6f}], 纬度: [{df[lat_col].min():.6f}, {df[lat_col].max():.6f}]")
    
    # 转换坐标
    wgs_lngs = []
    wgs_lats = []
    for idx, row in df.iterrows():
        lng = row[lng_col]
        lat = row[lat_col]
        wgs_lng, wgs_lat = gcj02_to_wgs84(lng, lat)
        wgs_lngs.append(wgs_lng)
        wgs_lats.append(wgs_lat)
    
    # 添加新列
    df['经度_WGS84'] = wgs_lngs
    df['纬度_WGS84'] = wgs_lats
    
    # 计算偏移量（用于验证）
    df['经度偏移'] = df[lng_col] - df['经度_WGS84']
    df['纬度偏移'] = df[lat_col] - df['纬度_WGS84']
    
    print(f"\n转换完成！")
    print(f"平均偏移量 - 经度: {df['经度偏移'].mean():.8f} (~{df['经度偏移'].mean() * 111000:.2f}米), 纬度: {df['纬度偏移'].mean():.8f} (~{df['纬度偏移'].mean() * 111000:.2f}米)")
    
    # 保存文件
    if output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_wgs84{ext}"
    
    df.to_excel(output_file, index=False)
    print(f"已保存到: {output_file}")
    
    # 显示前几条数据预览
    print("\n===== 转换结果预览 =====")
    preview_cols = [col for col in df.columns if col not in ['经度偏移', '纬度偏移']]
    print(df[preview_cols].head(10).to_string())
    
    return df


# ========== 生成ArcGIS Pro可用的CSV文件（可选） ==========
def export_to_arcgis_csv(df, output_csv=None, lng_col='经度_WGS84', lat_col='纬度_WGS84'):
    """导出为ArcGIS Pro可直接导入的CSV文件"""
    if output_csv is None:
        output_csv = "arcgis_import_points.csv"
    
    # 选择需要的列
    export_df = df.copy()
    # 重命名坐标列为标准名称
    export_df.rename(columns={lng_col: 'Longitude', lat_col: 'Latitude'}, inplace=True)
    
    export_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"已导出ArcGIS Pro CSV文件: {output_csv}")
    print("在ArcGIS Pro中使用'XY表转点'工具，X字段选Longitude，Y字段选Latitude，坐标系选WGS 1984")


# ========== 主程序 ==========
if __name__ == "__main__":
    # ===== 请修改这里的文件路径 =====
    INPUT_FILE = r"D:\Users\Administrator\Desktop\geo-coordinate-query\优秀历史建筑资料_经纬度.xlsx"  # 替换为你的Excel文件路径
    
    # ===== 如果你的列名不是'经度'和'纬度'，请修改这里 =====
    LNG_COLUMN = '经度'   # 经度列名
    LAT_COLUMN = '纬度'   # 纬度列名
    
    # ===== 执行转换 =====
    try:
        # 转换坐标并保存新Excel
        result_df = convert_excel_coordinates(
            input_file=INPUT_FILE,
            lng_col=LNG_COLUMN,
            lat_col=LAT_COLUMN
        )
        
        # 可选：导出ArcGIS Pro可直接使用的CSV
        export_to_arcgis_csv(result_df)
        
        print("\n✅ 处理完成！")
        
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {INPUT_FILE}")
        print("请修改脚本中的 INPUT_FILE 变量为正确的文件路径")
    except Exception as e:
        print(f"❌ 错误：{e}")