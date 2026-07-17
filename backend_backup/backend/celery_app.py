from celery import Celery
from backend.config import settings

celery_app = Celery(
    "enterprise_market_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Optional configuration, see the application user guide.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Add any specific celery configurations here
)

# In FastAPI we explicitly load our modules that contain tasks
celery_app.autodiscover_tasks(["backend.tasks"])
