@echo off
setlocal

set "ROOT=%~dp0"

if not exist "%ROOT%frontend\node_modules" (
    echo Frontend dependencies are missing. Run "npm install" in the frontend folder first.
    exit /b 1
)

start "WorthRot Backend" /D "%ROOT%" cmd /k "set PORT=5000 && python main.py"
start "WorthRot Frontend" /D "%ROOT%frontend" cmd /k "npm run dev"
