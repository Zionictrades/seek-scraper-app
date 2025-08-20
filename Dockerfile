FROM python:3.11-slim

WORKDIR /app

# Install system deps required by Playwright / browsers
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates wget gnupg libnss3 libatk1.0-0 libxss1 libasound2 libgtk-3-0 libgbm-dev \
      fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

# copy project files
COPY . /app

# install python deps
RUN python -m pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

ENV PYTHONUNBUFFERED=1

# install Playwright browsers (downloads browser binaries)
RUN python -m playwright install --with-deps

EXPOSE 8000

# shell form so $PORT is expanded by the container shell (Render sets $PORT)
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT