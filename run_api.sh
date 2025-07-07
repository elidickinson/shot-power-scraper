#!/bin/bash
# Run the Shot Scraper API Server

set -e

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements-api.txt
fi

# Load environment variables if .env exists
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the server
echo "Starting Shot Scraper API Server..."
echo "API docs available at: http://${HOST:-127.0.0.1}:${PORT:-8000}/docs"
python api_server.py