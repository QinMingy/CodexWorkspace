@echo off
setlocal

cd /d "%~dp0"

echo [1/5] Checking Python...
set "PY_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PY_CMD=py -3"

if not defined PY_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=python"
)

if not defined PY_CMD (
  echo [FAIL] Python was not found.
  echo Please install Python 3.10 or newer, then run this file again.
  pause
  exit /b 1
)

%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if not %errorlevel%==0 (
  echo [FAIL] Python 3.10 or newer is required.
  %PY_CMD% --version
  pause
  exit /b 1
)

echo [2/5] Preparing local virtual environment...
if not exist ".venv\Scripts\python.exe" (
  %PY_CMD% -m venv .venv
  if not %errorlevel%==0 (
    echo [FAIL] Could not create .venv.
    pause
    exit /b 1
  )
)

set "VENV_PY=.venv\Scripts\python.exe"

echo [3/5] Checking and installing dependencies from requirements.txt...
"%VENV_PY%" -m pip install --upgrade pip
if not %errorlevel%==0 (
  echo [FAIL] Could not upgrade pip.
  pause
  exit /b 1
)

"%VENV_PY%" -m pip install -r requirements.txt
if not %errorlevel%==0 (
  echo [FAIL] Could not install dependencies from requirements.txt.
  pause
  exit /b 1
)

echo [4/5] Running environment check...
"%VENV_PY%" -m subtitle_tool check
if not %errorlevel%==0 (
  echo.
  echo [WARN] The tool environment check reported a problem.
  echo Trying to repair dependencies from requirements.txt, then checking again...
  echo.
  "%VENV_PY%" -m pip install -r requirements.txt
  if not %errorlevel%==0 (
    echo [FAIL] Could not repair dependencies from requirements.txt.
    pause
    exit /b 1
  )
  "%VENV_PY%" -m subtitle_tool check
  if not %errorlevel%==0 (
    echo.
    echo [FAIL] Environment check still failed after installing dependencies.
    echo Please review the messages above. Network access, Python setup, or yt-dlp availability may need attention.
    pause
    exit /b 1
  )
  echo.
)

echo [5/5] Starting visual client...
echo Your browser should open automatically. If it does not, visit the local URL shown below.
"%VENV_PY%" -m streamlit run app.py --server.headless false

endlocal
