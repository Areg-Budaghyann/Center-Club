#!/bin/bash
# Start both bot and admin panel in the same container
uvicorn admin_panel.main:app --host 0.0.0.0 --port ${ADMIN_PORT:-8080} &
python bot.py
