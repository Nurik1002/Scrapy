"""
Maintenance Tasks - Keep the system healthy for 24/7 operation.

Features:
- Automatic VACUUM for database optimization
- Health checks with metrics logging
- Stuck task detection and restart
"""
import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task
def vacuum_tables() -> dict:
    """
    Run VACUUM ANALYZE on high-churn tables.
    
    Should be run daily during low-activity periods.
    
    Returns:
        Results for each table
    """
    from sqlalchemy import create_engine, text
    from src.core.config import settings
    
    tables = ['products', 'skus', 'sellers', 'price_history']
    results = {}
    
    # Need raw connection for VACUUM (can't run in transaction)
    engine = create_engine(settings.database.url, isolation_level="AUTOCOMMIT")
    
    with engine.connect() as conn:
        for table in tables:
            try:
                start = datetime.now()
                conn.execute(text(f"VACUUM ANALYZE {table}"))
                elapsed = (datetime.now() - start).total_seconds()
                results[table] = {"status": "success", "elapsed_seconds": elapsed}
                logger.info(f"✅ VACUUM ANALYZE {table} completed in {elapsed:.1f}s")
            except Exception as e:
                results[table] = {"status": "error", "error": str(e)}
                logger.error(f"❌ VACUUM {table} failed: {e}")
    
    engine.dispose()
    return results


@shared_task
def health_check() -> dict:
    """
    Check system health and log metrics.
    
    Should be run hourly to monitor system status.
    
    Returns:
        Health metrics
    """
    import psutil
    
    async def do_check():
        from src.core.database import get_session
        from sqlalchemy import text
        
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # System metrics
        try:
            metrics["system"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
            }
        except Exception as e:
            metrics["system"] = {"error": str(e)}
        
        # Database metrics
        try:
            async with get_session() as session:
                # Row counts
                for table in ['products', 'sellers', 'skus', 'price_history', 'categories']:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    metrics[f"count_{table}"] = result.scalar()
                
                # Database size
                result = await session.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                )
                metrics["db_size"] = result.scalar()
                
                # Connection count
                result = await session.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                metrics["active_connections"] = result.scalar()
                
        except Exception as e:
            metrics["database_error"] = str(e)
        
        # Scraping status
        try:
            from src.core.checkpoint import get_checkpoint_manager
            
            for platform in ['uzum', 'uzex']:
                checkpoint = await get_checkpoint_manager(platform, "continuous")
                saved = await checkpoint.load_checkpoint()
                if saved:
                    metrics[f"scraper_{platform}"] = {
                        "last_id": saved.get("last_id"),
                        "total_found": saved.get("total_found"),
                        "cycles": saved.get("cycles"),
                        "last_run": saved.get("last_run"),
                    }
                await checkpoint.close()
        except Exception as e:
            metrics["scraper_error"] = str(e)
        
        return metrics
    
    metrics = run_async(do_check())
    
    # Log summary
    logger.info(
        f"📊 Health Check: "
        f"Products={metrics.get('count_products', '?'):,} | "
        f"CPU={metrics.get('system', {}).get('cpu_percent', '?')}% | "
        f"Memory={metrics.get('system', {}).get('memory_percent', '?')}% | "
        f"DB={metrics.get('db_size', '?')}"
    )
    
    return metrics


@shared_task
def cleanup_old_price_history(days_to_keep: int = 90) -> dict:
    """
    Archive or delete old price history records.
    
    Args:
        days_to_keep: Keep records from last N days
        
    Returns:
        Cleanup results
    """
    async def do_cleanup():
        from src.core.database import get_session
        from sqlalchemy import text
        
        async with get_session() as session:
            # Get count before
            result = await session.execute(text("SELECT COUNT(*) FROM price_history"))
            before_count = result.scalar()
            
            # Delete old records
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date - timedelta(days=days_to_keep)
            
            result = await session.execute(
                text("DELETE FROM price_history WHERE recorded_at < :cutoff"),
                {"cutoff": cutoff_date}
            )
            deleted = result.rowcount
            
            await session.commit()
            
            return {
                "before_count": before_count,
                "deleted": deleted,
                "after_count": before_count - deleted,
                "cutoff_date": cutoff_date.isoformat(),
            }
    
    from datetime import timedelta
    
    result = run_async(do_cleanup())
    logger.info(f"🗑️ Cleanup: Deleted {result['deleted']:,} old price history records")
    return result


@shared_task
def ensure_scrapers_running() -> dict:
    """
    Ensure continuous scrapers are running, restart if needed.
    
    Should be run every few hours as a failsafe.
    
    Returns:
        Actions taken
    """
    from src.workers.continuous_scraper import restart_if_stale
    
    results = {}
    
    for platform in ['uzum', 'uzex']:
        result = restart_if_stale(platform, max_stale_seconds=7200)  # 2 hours
        results[platform] = result
        
    logger.info(f"🔍 Scraper check: {results}")
    return results
