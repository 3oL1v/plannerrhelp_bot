# Project Notes

- Keep the implementation as a single-service MVP: one FastAPI app, one integrated Telegram bot, one React mini app served by the backend.
- Prefer replacing broken code over layering workarounds.
- Before pushing, run backend migration, mini app build, and a basic application startup check.
