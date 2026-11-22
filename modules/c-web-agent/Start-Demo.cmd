@echo off
setlocal
cd /d "%~dp0" || exit /b 1

for %%P in (".venv\Scripts\python.exe" "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "python.exe") do (
    "%%~P" -c "import sys,pydantic; sys.exit(0 if sys.version_info >= (3,11) and pydantic.VERSION.startswith('2.') else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "demo_python=%%~P"
        goto :launch
    )
)
echo Python 3.11+ with Pydantic 2 is required. See README.md. 1>&2
exit /b 1

:launch
"%demo_python%" "backend\offline_demo.py"
exit /b %errorlevel%
