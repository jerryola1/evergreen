#!/bin/bash

# Start development servers for Evergreen Dashboard
echo "🌿 Starting Evergreen Dashboard Development Environment"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copy env.example to .env and configure your values."
    exit 1
fi

# Load environment variables
source .env

echo "📊 Starting Backend API on port ${BACKEND_PORT:-8000}..."
cd web/backend
python -m venv venv 2>/dev/null || true
source venv/bin/activate || source venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${BACKEND_PORT:-8000} --reload &
BACKEND_PID=$!

cd ../..

echo "🎨 Starting Frontend on port ${FRONTEND_PORT:-5173}..."
cd web/frontend
npm install
npm run dev &
FRONTEND_PID=$!

cd ../..

echo "✅ Development servers started!"
echo "📊 Backend API: http://localhost:${BACKEND_PORT:-8000}"
echo "🎨 Frontend: http://localhost:${FRONTEND_PORT:-5173}"
echo "📖 API Docs: http://localhost:${BACKEND_PORT:-8000}/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for interrupt signal
trap "echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait 