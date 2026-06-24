# Root Dockerfile — used when Railway service root is the repo root (not backend/).
# If your Railway Root Directory is set to "backend", Railway uses backend/Dockerfile instead.
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=./data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
