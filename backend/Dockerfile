FROM python:3.11-slim

WORKDIR /app

# copy project files
COPY . /app

# install python deps if requirements.txt exists
RUN python -m pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# shell form so $PORT is expanded by the container shell (Render will set $PORT)
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT