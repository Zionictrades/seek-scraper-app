FROM python:3.11-slim

WORKDIR /app

# copy project
COPY . /app

# install dependencies:
# - If you have requirements.txt it will be used.
# - Otherwise adapt this line to your project's installer (poetry, pipenv, etc).
RUN python -m pip install --upgrade pip \
    && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

ENV PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]