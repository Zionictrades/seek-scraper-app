FROM python:3.11-slim

ARG CACHEBUST=20250820
WORKDIR /app

# OS deps required by Playwright / Chromium
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates wget gnupg libnss3 libatk1.0-0 libxss1 libasound2 libgtk-3-0 libgbm-dev fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install python deps (copy requirements first for cache)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip
RUN pip install -r /app/requirements.txt

# Copy app
COPY . /app

# Install Playwright browsers (must run after playwright package is installed)
RUN python -m playwright install --with-deps

ENV PYTHONUNBUFFERED=1

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]