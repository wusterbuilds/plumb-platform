from celery import Celery

from app.config import settings
import app.prompts.registration  # noqa: F401 — registers all prompts on import

celery_app = Celery(
    "plumb",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # one task at a time per worker
    beat_schedule={
        "check-inbox": {
            "task": "app.email.monitor.check_inbox",
            "schedule": settings.GMAIL_POLL_INTERVAL_SECONDS,
        },
    },
)

# Import task modules so they register with celery_app
import app.tasks.classify  # noqa: F401, E402
import app.tasks.extract  # noqa: F401, E402
import app.tasks.cross_reference  # noqa: F401, E402
import app.tasks.pipeline  # noqa: F401, E402
import app.tasks.model_building  # noqa: F401, E402
import app.tasks.market_enrichment  # noqa: F401, E402
import app.tasks.om_generation  # noqa: F401, E402
import app.email.monitor  # noqa: F401, E402 — registers check_inbox + email tasks
