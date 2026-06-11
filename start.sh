#!/bin/bash
# Bot runs in background; Streamlit panel serves on $PORT (Render's exposed port)
python bot.py &
streamlit run admin_panel/streamlit_app.py \
  --server.port "${PORT:-8501}" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
