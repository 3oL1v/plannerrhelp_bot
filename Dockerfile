FROM node:20-alpine AS frontend-build

WORKDIR /app/miniapp
COPY miniapp/package*.json ./
RUN npm install
COPY miniapp ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY .env.example /app/.env.example
COPY --from=frontend-build /app/backend/app/static /app/backend/app/static

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
