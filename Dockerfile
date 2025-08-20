FROM python:3.11-slim

# cache-bust to force rebuild when needed
ARG CACHEBUST=20250820
WORKDIR /app

# OS deps required by browsers / Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates wget gnupg libnss3 libatk1.0-0 libxss1 libasound2 libgtk-3-0 libgbm-dev fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

# copy project and install python deps
COPY . /app
RUN python -m pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

ENV PYTHONUNBUFFERED=1

# install Playwright browsers (must run after pip install)
RUN python -m playwright install --with-deps

EXPOSE 8000

# shell form so $PORT is expanded by the container shell (Render sets $PORT)
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT