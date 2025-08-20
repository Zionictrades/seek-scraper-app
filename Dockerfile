FROM python:3.11-slim

ARG CACHEBUST=20250820
WORKDIR /app

# OS deps required by Chromium / Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates wget gnupg libnss3 libatk1.0-0 libxss1 libasound2 libgtk-3-0 libgbm-dev fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to maximise cache hits
COPY requirements.txt /app/requirements.txt

# Python deps
RUN python -m pip install --upgrade pip
RUN if [ -f /app/requirements.txt ]; then pip install -r /app/requirements.txt; fi

# Copy app source
COPY . /app

# Ensure Playwright browsers are installed AFTER playwright is installed
RUN python -m playwright install --with-deps

ENV PYTHONUNBUFFERED=1
EXPOSE 10000

# Use shell form so $PORT is expanded by the container
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]