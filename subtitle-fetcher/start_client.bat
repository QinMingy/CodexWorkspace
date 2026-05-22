@echo off
setlocal

cd /d "%~dp0"

echo [1/5] Checking Python...
call :detect_python

if not defined PY_CMD (
  echo [WARN] Python was not found.
  call :install_python
  call :detect_python
  if not defined PY_CMD (
    echo [FAIL] Python is still not available after the install attempt.
    echo Please install Python 3.10 or newer manually, then run this file again.
    echo Download page: https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
)

%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if not %errorlevel%==0 (
  echo [WARN] Python 3.10 or newer is required.
  %PY_CMD% --version
  call :install_python
  call :detect_python
  %PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
  if not %errorlevel%==0 (
    echo [FAIL] Python 3.10 or newer is still not available.
    echo Please install Python 3.10 or newer manually, then run this file again.
    echo Download page: https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
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
exit /b 0

:detect_python
set "PY_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PY_CMD=py -3"

if not defined PY_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=python"
)
exit /b 0

:install_python
where winget >nul 2>nul
if not %errorlevel%==0 (
  echo [FAIL] winget was not found, so Python cannot be installed automatically.
  echo Please install Python 3.10 or newer manually:
  echo https://www.python.org/downloads/windows/
  exit /b 1
)

echo Installing Python with winget...
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
if not %errorlevel%==0 (
  echo [FAIL] winget could not install Python automatically.
  echo Please install Python 3.10 or newer manually:
  echo https://www.python.org/downloads/windows/
  exit /b 1
)

echo Python install finished. Refreshing PATH for this window...
set "PATH=%LocalAppData%\Programs\Python\Python312\;%LocalAppData%\Programs\Python\Python312\Scripts\;%PATH%"
exit /b 0
