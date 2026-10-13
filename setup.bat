@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Money Studio - Cai dat
echo ================================================
echo   Money Studio (Broke Ben) - cai dat lan dau (1-3 phut)
echo ================================================
echo.

set "PYEXE="
for %%P in ("py -3" "python" "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe" "E:\HorrorStudio\env\Scripts\python.exe" "E:\RelatableStudio\env\Scripts\python.exe" "E:\LocalTTS\env_en\Scripts\python.exe") do (
  if not defined PYEXE (
    %%~P -c "import sys,tkinter,venv; assert sys.version_info>=(3,10)" >nul 2>nul && set "PYEXE=%%~P"
  )
)
if not defined PYEXE (
  echo [LOI] Khong tim thay Python 3.10+ co Tkinter.
  echo Cai Python tu https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) roi chay lai file nay.
  pause
  exit /b 1
)
echo Dung Python: !PYEXE!

if not exist "env\Scripts\python.exe" (
  echo Dang tao moi truong rieng cho tool ^(thu muc env^)...
  !PYEXE! -m venv env
  if errorlevel 1 (
    echo [LOI] Khong tao duoc moi truong Python.
    pause
    exit /b 1
  )
)

echo Dang cai thu vien: Pillow, numpy, ffmpeg, anthropic...
"env\Scripts\python.exe" -m pip install --upgrade pip >nul
"env\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [LOI] Cai thu vien that bai. Kiem tra mang Internet roi chay lai.
  pause
  exit /b 1
)

echo Kiem tra giong doc Kokoro ^(dung chung voi Horror Studio^)...
if exist "E:\LocalTTS\env_en\Scripts\python.exe" (
  echo   OK: E:\LocalTTS\env_en\Scripts\python.exe
) else (
  echo   [CANH BAO] Khong thay Kokoro o E:\LocalTTS. Mo app, vao tab "3. Giong doc ^& cai dat" de chon duong dan.
)

echo Tao loi tat tren Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\Money Studio.lnk'); $s.TargetPath='%~dp0env\Scripts\pythonw.exe'; $s.Arguments='\"%~dp0app\main.py\"'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0assets\icon.ico'; $s.Description='Money Studio - Broke Ben'; $s.Save()"

echo.
echo ================================================
echo   XONG! Mo app bang loi tat "Money Studio" tren Desktop
echo   hoac nhay dup file "Money Studio.bat".
echo ================================================
pause
