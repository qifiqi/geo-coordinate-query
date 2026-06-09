# 地址经纬度查询工具

基于高德地图 API 的地址经纬度批量查询工具，支持单地址查询和 Excel 批量处理。

## 功能

- **单地址查询**：输入地址或建筑名称，实时返回经纬度及详细信息（省份、城市、区县、POI名称等）
- **批量 Excel 处理**：导入 xlsx 文件，自动逐行查询并在同目录输出带经纬度的结果文件
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
| `geo_app.py` | GUI 主程序 |
| `main.py` | 命令行脚本版本 |
| `build.bat` | PyInstaller 打包脚本 |

## 截图

查询结果支持点击复制，经纬度高亮显示，日志实时滚动。
