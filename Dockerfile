FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json /frontend/package.json
COPY frontend/package-lock.json /frontend/package-lock.json
RUN npm ci

COPY frontend /frontend
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app
COPY --from=frontend-builder /frontend/dist /app/batch_downloader/static

EXPOSE 8000
CMD ["uvicorn", "batch_downloader.main:app", "--host", "0.0.0.0", "--port", "8000"]
