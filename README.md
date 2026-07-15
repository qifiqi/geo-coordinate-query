# 地址经纬度查询工具

基于高德地图和百度地图 API 的地点、周边 POI 与 Excel 批处理工具。

## 功能

- **候选地点查询**：高德、百度或自动对比同时返回地理编码与 POI 候选；用户确认中心点后再进行后续操作
- **周边 POI 查询**：按中心点检索市政、医疗、科教文化、政府、交通、体育休闲及商业服务；导出同时包含 GCJ-02 与 WGS-84 坐标
- **批量 Excel 处理**：导入 xlsx 文件，使用统一策略自动选择高德或百度候选，输出坐标、服务来源、匹配方式及相似度
- **坐标转换**：支持 GCJ-02 与 WGS-84 单点转换，以及 Excel 批量转换
- **精度排序**：名称和地址分别评分；区域/街区/景区查询优先空间实体，降低同名公司、办事机构的干扰
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
python main.py query "武汉汉口历史风貌区" --provider auto --city 武汉市 --candidates --json
python main.py batch 优秀历史建筑资料.xlsx --provider auto --output result.xlsx
python nearby_poi.py "武汉汉口历史风貌区" --provider auto --city 武汉市 --radius 2000
python main.py convert point 114.298572 30.572815 --direction gcj-to-wgs
python main.py convert excel input.xlsx --output output_wgs84.xlsx
```

CLI 子命令：

| 命令 | 用途 |
|------|------|
| `config` | 查看或保存高德 Key、百度 AK |
| `query` | 查询地点候选，支持高德、百度、自动对比、城市限制和 JSON 输出 |
| `batch` | 批量处理 Excel，支持高德、百度、自动对比、城市限制、输出路径和请求间隔 |
| `nearby_poi.py` | 独立周边 POI 脚本，输入地点或 GCJ-02 坐标后导出公共设施与商业 POI |
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
| `geo_app.py` | tkinter GUI：统一的地点候选、周边 POI、批处理和坐标转换工作流 |
| `main.py` | 命令行批处理入口，复用服务层 |
| `geo_coordinate_query/config.py` | API Key 配置读写 |
| `geo_coordinate_query/query_service.py` | Provider Strategy 候选查询、排序和自动选择 |
| `geo_coordinate_query/map_services.py` | 高德和百度地图 API 客户端 |
| `geo_coordinate_query/excel_processor.py` | 统一 Excel 批处理管线 |
| `geo_coordinate_query/batch_convert.py` | Excel 坐标批量转换 |
| `geo_coordinate_query/coordinates.py` | 坐标系转换算法 |
| `geo_coordinate_query/matching.py` | 地址相似度计算 |
| `build.bat` | PyInstaller 打包脚本 |

## 截图

查询结果支持点击复制，经纬度高亮显示，日志实时滚动。
