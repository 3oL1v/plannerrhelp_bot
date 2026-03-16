# Planner Help Bot

Telegram planner MVP in a single repository:

- `backend/`: FastAPI API + aiogram bot + APScheduler + SQLAlchemy/Alembic
- `miniapp/`: React + Vite Telegram Mini App
- one deployable Railway service, static mini app served by FastAPI

## Features

- Bot flows: `/start`, today summary, quick task/event creation, inbox capture, basic settings
- Mini App pages: Today, Week, Inbox, Task details, Event details, Settings, More
- API: auth bootstrap, dashboards, inbox/tasks/events/categories/settings CRUD
- Scheduler: due reminders and morning digest jobs
- Deploy-ready: Dockerfile + Railway healthcheck + webhook support

## Local run

1. Create `.env` from `.env.example`.
2. Set at least:
   - `DATABASE_URL`
   - `TELEGRAM_BOT_TOKEN`
   - `APP_SECRET`
3. Backend:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

4. Mini App in separate terminal:

```bash
cd miniapp
npm install
npm run build
```

The backend serves the built app from `backend/app/static`. For local Telegram bot testing, keep `TELEGRAM_USE_POLLING=true`.

## Railway

1. Create a Railway project from this GitHub repo.
2. Add a Railway PostgreSQL plugin.
3. Set env vars:
   - `ENVIRONMENT=production`
   - `APP_SECRET`
   - `APP_BASE_URL=https://<your-service>.up.railway.app`
   - `WEBAPP_URL=https://<your-service>.up.railway.app`
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_WEBHOOK_SECRET`
   - `ENABLE_SCHEDULER=true`
   - `TELEGRAM_USE_POLLING=false`
4. Deploy. The Dockerfile runs `alembic upgrade head` before `uvicorn`.
5. In Telegram BotFather set the Mini App URL to your Railway domain. On startup the app registers its webhook automatically.

## API summary

- `POST /api/v1/auth/telegram/init`
- `GET /api/v1/dashboard/today`
- `GET /api/v1/dashboard/week`
- `GET/POST/PATCH/DELETE /api/v1/inbox`
- `POST /api/v1/inbox/{id}/convert-to-task`
- `POST /api/v1/inbox/{id}/convert-to-event`
- `GET/POST/PATCH/DELETE /api/v1/tasks`
- `POST /api/v1/tasks/{id}/complete`
- `POST /api/v1/tasks/{id}/reschedule`
- `GET/POST/PATCH/DELETE /api/v1/events`
- `POST /api/v1/events/{id}/reschedule`
- `GET/POST/PATCH/DELETE /api/v1/categories`
- `GET/PATCH /api/v1/settings`
- `GET /health`
