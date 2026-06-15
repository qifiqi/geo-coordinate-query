@echo off
call conda activate py3.11
cd /d "%~dp0"
D:\minicoda\envs\py3.11\python.exe -m PyInstaller "地址经纬度查询工具.spec" --noconfirm
echo.
echo ===== 打包完成 =====
echo 输出文件: dist\地址经纬度查询工具.exe
pause
