#!/bin/bash
# VoiceCoach 2.0 Setup Script

echo "🚀 VoiceCoach 2.0 Setup"
echo "======================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# OpenAI Configuration (optional - for LLM features)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ORG_ID=your_openai_org_id_here

# Google Gemini Configuration (optional - for LLM features)
GEMINI_API_KEY=your_gemini_api_key_here
EOF
    echo "✅ Created .env file. Edit it with your API keys if you want LLM features."
else
    echo "✅ .env file already exists"
fi

# Start backend
echo "🔧 Starting backend (FastAPI)..."
cd backend
source ../venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 5

# Start frontend
echo "🎨 Starting frontend (React)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "🎉 VoiceCoach 2.0 is starting up!"
echo "================================="
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend API: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "💡 To stop the services:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "⚠️  Note: LLM features require API keys in .env file"
