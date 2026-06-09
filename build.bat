@echo off
call conda activate py11
cd /d "%~dp0"
python -m PyInstaller --onefile --windowed --name "地址经纬度查询工具" --hidden-import=openpyxl --hidden-import=requests --exclude-module=scipy --exclude-module=matplotlib --exclude-module=PyQt5 --exclude-module=PIL --exclude-module=sqlalchemy --exclude-module=psycopg2 --exclude-module=lxml --clean geo_app.py
echo.
echo ===== 打包完成 =====
echo 输出文件: dist\地址经纬度查询工具.exe
pause
