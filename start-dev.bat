@echo off
echo 🌿 Starting Evergreen Dashboard Development Environment

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  .env file not found. Copy env.example to .env and configure your values.
    pause
    exit /b 1
)

echo 📊 Starting Backend API...
cd web\backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt
start "Backend API" cmd /k "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

cd ..\..

echo 🎨 Starting Frontend...
cd web\frontend
call npm install
start "Frontend" cmd /k "npm run dev"

cd ..\..

echo ✅ Development servers started!
echo 📊 Backend API: http://localhost:8000
echo 🎨 Frontend: http://localhost:5173
echo 📖 API Docs: http://localhost:8000/docs
echo.
echo Press any key to exit...
pause 