# 地址经纬度查询工具

基于高德地图和百度地图 API 的地址经纬度查询工具，支持单地址查询、Excel 批量处理和坐标系转换。

## 功能

- **单地址查询**：输入地址或建筑名称，实时返回经纬度及详细信息（省份、城市、区县、POI名称等）
- **批量 Excel 处理**：导入 xlsx 文件，自动逐行查询并在同目录输出带经纬度的结果文件
- **百度地图查询**：支持百度 AK 查询和批量导出百度匹配结果
- **坐标转换**：支持 GCJ-02 与 WGS-84 单点转换，以及 Excel 批量转换
- **多策略搜索**：geocode 地理编码优先，POI 关键词搜索回退，确保匹配精度
- **点击复制**：查询结果任意字段点击即可复制到剪贴板
- **API Key 管理**：设置页面配置高德 API Key，附带创建说明

## 技术栈

- Python 3
- tkinter（GUI）
- requests（HTTP）
- pandas + openpyxl（Excel 读写）
- PyInstaller（打包 exe）

## 使用方式

### 运行源码

```bash
pip install requests pandas openpyxl
python geo_app.py
```

命令行工具：

```bash
python main.py --help
python main.py config --amap-key YOUR_AMAP_KEY --baidu-ak YOUR_BAIDU_AK
python main.py query "武汉大学" --provider amap --wgs84 --similarity
python main.py batch 优秀历史建筑资料.xlsx --provider amap --output result.xlsx
python main.py convert point 114.298572 30.572815 --direction gcj-to-wgs
python main.py convert excel input.xlsx --output output_wgs84.xlsx
```

CLI 子命令：

| 命令 | 用途 |
|------|------|
| `config` | 查看或保存高德 Key、百度 AK |
| `query` | 查询单个地址或建筑名称，支持高德/百度和 JSON 输出 |
| `batch` | 批量处理 Excel，支持指定服务、输出路径和请求间隔 |
| `convert point` | 转换单个坐标点 |
| `convert excel` | 批量转换 Excel 中的经纬度列 |

### 打包 exe

```bash
build.bat
```

输出：`dist/地址经纬度查询工具.exe`

### 获取高德 API Key

1. 注册 [高德开放平台](https://lbs.amap.com/)
2. 控制台 → 应用管理 → 创建应用
3. 添加 Key，服务平台选择「Web服务」
4. 免费额度：每日 5,000 次调用

## 文件说明

| 文件 | 说明 |
|------|------|
| `geo_app.py` | tkinter GUI 入口，只保留界面和事件绑定 |
| `main.py` | 命令行批处理入口，复用服务层 |
| `geo_coordinate_query/config.py` | API Key 配置读写 |
| `geo_coordinate_query/map_services.py` | 高德和百度地图 API 查询 |
| `geo_coordinate_query/excel_processor.py` | 高德 Excel 批处理 |
| `geo_coordinate_query/baidu_excel_processor.py` | 百度 Excel 批处理 |
| `geo_coordinate_query/batch_convert.py` | Excel 坐标批量转换 |
| `geo_coordinate_query/coordinates.py` | 坐标系转换算法 |
| `geo_coordinate_query/matching.py` | 地址相似度计算 |
| `build.bat` | PyInstaller 打包脚本 |

## 截图

查询结果支持点击复制，经纬度高亮显示，日志实时滚动。
