@echo off
cd /d "%~dp0"
echo PromptVideo.exe olusturuluyor (birkac dakika surer)...
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean PromptVideo.spec
if errorlevel 1 ( pause & exit /b 1 )
echo.
echo Hazir: dist\PromptVideo\PromptVideo.exe
echo Kurulum dosyasi (Setup.exe) icin Inno Setup ile kurulum.iss dosyasini derleyin: https://jrsoftware.org/isinfo.php
pause
