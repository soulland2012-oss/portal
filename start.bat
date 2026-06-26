@echo off
chcp 65001 > nul
echo.
echo  SQB AI Transformation Portal
echo  ==============================
echo  Запуск сервера...
echo.
cd /d "%~dp0"
python app.py
pause
