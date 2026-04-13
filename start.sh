#!/bin/bash
# Start the TradeBot backend API server
cd /app/backend
exec uvicorn src.dashboard.app:app --host 0.0.0.0 --port ${PORT:-8000}
