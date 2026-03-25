#!/bin/bash
# Start admin panel in background, then start bot
python -m uvicorn admin_panel.main:app --host 0.0.0.0 --port ${ADMIN_PORT:-8080} &
python bot.py
