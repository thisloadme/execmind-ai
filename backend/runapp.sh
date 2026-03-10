#!/bin/bash

# Default port to 8001 if no parameter is provided
PORT=${1:-8001}

# Activate virtual environment
source venv/bin/activate

# Add current directory to PYTHONPATH
export PYTHONPATH=.

# Run uvicorn server
uvicorn app.main:app --host 0.0.0.0 --port $PORT
