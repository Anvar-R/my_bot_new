
import logging
from celery import Celery
from model import predict_bytes
from prometheus_client import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

celery = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery.conf.update(
    result_expires=300,
    worker_max_tasks_per_child=50,
)

TASK_COUNT = Counter("imagebot_tasks_total", "Total Celery tasks")

@celery.task
def classify_image(image_bytes):
    TASK_COUNT.inc()
    logger.info("Task started")
    result = predict_bytes(image_bytes)
    logger.info(f"Task finished: {result}")
    return result
