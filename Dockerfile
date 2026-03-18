FROM python:3.11-slim

WORKDIR /app

# Force fresh install every time
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

ENV DATABASE_PATH=/data/office.db
ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "bot.py"]
