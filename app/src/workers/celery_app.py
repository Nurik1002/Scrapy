"""
Celery Application - Task queue configuration for NON-STOP scraping.
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
    
    # Task settings for long-running tasks
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # NO TIME LIMITS - Tasks run forever for continuous scraping
    task_soft_time_limit=None,  # NO LIMIT - Runs forever
    task_time_limit=None,       # NO LIMIT - Runs forever

    # Result settings
    result_expires=3600,
    
    # Error handling
    task_annotations={
        '*': {'rate_limit': '100/s'}
    },
)

# Auto-discover tasks (including new continuous_scraper and maintenance_tasks)
celery_app.autodiscover_tasks([
    'src.workers.download_tasks',
    'src.workers.process_tasks',
    'src.workers.analytics_tasks',
    'src.workers.continuous_scraper',     # NEW: Continuous scraping
    'src.workers.maintenance_tasks',       # NEW: Maintenance tasks
    'src.workers.olx_tasks',               # OLX scraper tasks
    # Yandex removed - requires residential proxies ($50-70/mo) which we're not using
])

# ==============================================================================
# Beat schedule for NON-STOP 24/7 scraping operation
# ==============================================================================
# DISABLED: Switched to pure continuous non-stop scraping mode
# All scrapers run continuously without cron scheduling

# celery_app.conf.beat_schedule = {
#     # All schedules disabled - using continuous_scan tasks instead
# }
