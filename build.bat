@echo off
cd /d "%~dp0"
py -3.14 -m pip install -r requirements.txt
py -3.14 -m PyInstaller --clean SYNC.spec
echo.
echo Built: dist\SYNC.exe
