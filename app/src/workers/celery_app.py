"""
Celery Application - Task queue configuration.
"""
from celery import Celery
from celery.schedules import crontab

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config import settings


# Create Celery app
celery_app = Celery(
    "uzum_analytics",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

# Configuration
celery_app.conf.update(
    task_serializer=settings.celery.task_serializer,
    result_serializer=settings.celery.result_serializer,
    accept_content=settings.celery.accept_content,
    timezone=settings.celery.timezone,
    enable_utc=settings.celery.enable_utc,
    
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    
    # Result settings
    result_expires=3600,
    
    # Error handling
    task_annotations={
        '*': {'rate_limit': '100/s'}
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks([
    'src.workers.download_tasks',
    'src.workers.process_tasks',
    'src.workers.analytics_tasks',
])

# Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    # Full scan every 6 hours
    'full-scan-every-6h': {
        'task': 'src.workers.download_tasks.scan_id_range',
        'schedule': crontab(hour='*/6', minute=0),
        'args': ('uzum', 1, 3000000, 100000),  # Platform, start, end, target
    },
    
    # Process raw files every 30 minutes
    'process-raw-every-30m': {
        'task': 'src.workers.process_tasks.process_pending',
        'schedule': crontab(minute='*/30'),
        'args': ('uzum',),
    },
    
    # Daily analytics at 3 AM
    'daily-analytics-3am': {
        'task': 'src.workers.analytics_tasks.calculate_daily_stats',
        'schedule': crontab(hour=3, minute=0),
        'args': ('uzum',),
    },
    
    # Price change alerts every hour
    'price-alerts-hourly': {
        'task': 'src.workers.analytics_tasks.detect_price_changes',
        'schedule': crontab(minute=0),
        'args': ('uzum',),
    },
}
