FROM python:3.11-slim

WORKDIR /app

# copy project files
COPY . /app

# Install OS deps required by Playwright and common system libraries used by browsers
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxrandr2 \
    libxss1 \
    libasound2 \
    libgbm1 \
    libgtk-3-0 \
    libxcomposite1 \
    libxdamage1 \
    libx11-xcb1 \
  && rm -rf /var/lib/apt/lists/*

# install python deps if requirements.txt exists
RUN python -m pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Verify playwright package and install browsers with verbose output. This
# prints package info (so Render logs show whether 'playwright' was installed)
# and tries a per-browser fallback if the combined install fails.
RUN python - <<'PY'
import importlib, sys, subprocess
print('=== Playwright verification starting ===')
spec = importlib.util.find_spec('playwright')
print('playwright package found:', bool(spec))
try:
  import playwright
  print('playwright version:', getattr(playwright, '__version__', 'unknown'))
except Exception as e:
  print('playwright import failed (this may be fine if package not yet installed):', e)
print('Running: python -m playwright install --with-deps')
ret = subprocess.call([sys.executable, '-m', 'playwright', 'install', '--with-deps'])
if ret != 0:
  print('playwright install --with-deps failed (exit code', ret, '). Attempting per-browser installs...')
  for b in ('chromium', 'firefox', 'webkit'):
    print('Installing browser:', b)
    subprocess.call([sys.executable, '-m', 'playwright', 'install', b])
print('=== Playwright verification complete ===')
PY
# Debug: list Playwright cache and common install paths so build logs show whether browsers are present
RUN echo '=== DEBUG: Playwright cache root ===' && ls -la /root/.cache || true
RUN echo '=== DEBUG: ms-playwright dir ===' && ls -la /root/.cache/ms-playwright || true
RUN echo '=== DEBUG: /usr/local/share ===' && ls -la /usr/local/share || true
RUN if python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('playwright') else 1)"; then \
    python -m playwright install --with-deps; \
  fi

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# shell form so $PORT is expanded by the container shell (Render will set $PORT)
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT