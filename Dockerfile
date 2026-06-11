FROM python:3.11-slim

WORKDIR /app

# Force fresh install every time
COPY requirements.txt .
COPY admin_panel/requirements.txt admin_panel/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r admin_panel/requirements.txt

COPY . .

RUN mkdir -p /data

ENV DATABASE_PATH=/data/office.db
ENV PYTHONUNBUFFERED=1

CMD ["bash", "start.sh"]
