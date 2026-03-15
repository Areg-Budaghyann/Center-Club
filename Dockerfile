FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# SQLite database will be written to /data (mount a volume here in production)
ENV DATABASE_PATH=/data/office.db

# Default port for webhook mode
EXPOSE 8443

CMD ["python", "bot.py"]
