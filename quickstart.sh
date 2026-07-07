#!/bin/bash
# Quick start script for local development

set -e

echo "🚀 Stripe Webhook Payment Processor - Quick Start"
echo "=================================================="

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.11+ required. Current: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Copy environment file
if [ ! -f ".env" ]; then
    echo "⚙️  Setting up environment configuration..."
    cp .env.example .env
    echo "   Created .env file (using SQLite + local Redis defaults)"
fi

# Check Redis
echo "🔍 Checking Redis connection..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Warning: Redis not running locally"
    echo "   Start Redis with: redis-server"
    echo "   Or use Docker: docker-compose up redis postgres"
else
    echo "✅ Redis is running"
fi

# Initialize database
echo "🗄️  Initializing database..."
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
echo "✅ Database initialized"

# Run tests
echo ""
echo "🧪 Running test suite..."
pytest test_webhook.py -v --tb=short

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the development server:"
echo "  python main.py"
echo ""
echo "Or with auto-reload:"
echo "  uvicorn main:app --reload"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo "ReDoc at: http://localhost:8000/redoc"
