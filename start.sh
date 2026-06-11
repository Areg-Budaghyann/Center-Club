#!/bin/bash
# Render sets $PORT for the public-facing process (must be Streamlit).
# The bot also starts an HTTP health-check server — give it a different port
# so it doesn't clash with Streamlit on $PORT.
STREAMLIT_PORT="${PORT:-10000}"
PORT=8080 python bot.py &
streamlit run admin_panel/streamlit_app.py \
  --server.port "$STREAMLIT_PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
