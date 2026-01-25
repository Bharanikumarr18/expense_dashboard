#!/bin/bash

APP_DIR="/home/bharani-kumar/Documents/expense_dashboard"
CHROME_PROFILE="$APP_DIR/chrome-profile"
PORT=8501

cd "$APP_DIR" || exit 1

source "$APP_DIR/venv/bin/activate"

# Kill any previous streamlit
pkill -f "streamlit run" 2>/dev/null

# Start streamlit
streamlit run "$APP_DIR/main.py" --server.headless true --server.port $PORT &

# Wait until server is ready
for i in {1..20}; do
  nc -z localhost $PORT && break
  sleep 1
done

# Open as desktop-style app (NO browser UI)
google-chrome \
  --user-data-dir="$CHROME_PROFILE" \
  --app=http://localhost:$PORT \
google-chrome \
  --user-data-dir="$CHROME_PROFILE" \
  --app=http://localhost:$PORT \
