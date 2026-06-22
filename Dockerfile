FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

COPY docker-cron /etc/cron.d/release-monitor
RUN chmod 0644 /etc/cron.d/release-monitor \
    && crontab /etc/cron.d/release-monitor

CMD ["cron", "-f"]
