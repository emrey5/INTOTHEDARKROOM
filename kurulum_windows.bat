@echo off
cd /d "%~dp0"
echo PromptVideo Studyo icin gerekli paketler kuruluyor...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Python bulunamadi ya da kurulum basarisiz. Python 3.10+ kurun: winget install Python.Python.3.12
  pause
  exit /b 1
)
echo.
echo Kurulum tamam. Uygulamayi acmak icin calistir.bat dosyasina cift tiklayin.
echo Daha iyi senaryo icin (ucretsiz): https://ollama.com  sonra:  ollama pull qwen3:8b
pause
