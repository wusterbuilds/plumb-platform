# Plumb Platform API

FastAPI, PostgreSQL, Redis, Celery, and S3-compatible storage power the Plumb deal-processing and review pipeline.

```bash
cp .env.example .env
docker compose up -d
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the development API reference. See the repository root [README](../README.md) for the full stack and safety notes.
