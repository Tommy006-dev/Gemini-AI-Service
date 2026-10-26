@echo off
rem Chuyen ve thu muc chua file nay (de click o dau cung chay duoc)
cd /d "%~dp0"

rem ---- 0. Kiem tra Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Hay cai Python va tick "Add Python to PATH".
    pause
    exit /b 1
)

rem ---- 1. Kiem tra GEMINI_API_KEY trong .env ----
findstr /R /C:"^GEMINI_API_KEY=..*" ".env" >nul 2>nul
if errorlevel 1 (
    echo [LOI] Chua co GEMINI_API_KEY trong file .env
    echo Mo file .env va them dong: GEMINI_API_KEY=key_cua_ban
    pause
    exit /b 1
)

rem ---- 2. Tao venv + cai thu vien (chi lan dau) ----
if not exist ".venv\Scripts\python.exe" (
    echo Dang tao moi truong ao .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [LOI] Tao venv that bai.
        pause
        exit /b 1
    )
)
if not exist ".venv\deps_ok.txt" (
    echo Dang cai thu vien, lan dau co the mat vai phut ...
    ".venv\Scripts\python.exe" -m pip install google-genai fastapi uvicorn httpx python-multipart python-dotenv tzdata
    if errorlevel 1 (
        echo [LOI] Cai thu vien that bai. Kiem tra ket noi mang roi chay lai.
        pause
        exit /b 1
    )
    echo ok > ".venv\deps_ok.txt"
)

rem ---- 3. Khoi tao database (an toan khi chay lai) ----
".venv\Scripts\python.exe" dp.py

rem ---- 4. Mo 2 service, moi service 1 cua so rieng ----
start "AI Service (8001)" cmd /k ".venv\Scripts\python.exe -m uvicorn ai_service:app --port 8001"
start "Blog Service (8000)" cmd /k ".venv\Scripts\python.exe -m uvicorn blog_service:app --port 8000"

rem ---- 5. Doi service len roi mo giao dien ----
timeout /t 4 /nobreak >nul
start "" "%~dp0frontend.html"