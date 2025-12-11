"""
Continuous Scraper - Non-stop scraping with automatic restart and recovery.

Features:
- Endless loop that cycles through all product IDs
- Automatic resume from checkpoint after crashes/restarts
- Self-healing with retry on errors
- Progress tracking and monitoring
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

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


@shared_task(bind=True, max_retries=None)  # NO TIME LIMIT - Runs forever, infinite retries
def continuous_scan(
    self,
    platform: str = "uzum",
    batch_target: int = 10000,
    pause_between_cycles: int = 60,  # 1 min pause between full cycles
    max_id: int = 3000000
) -> dict:
    """
    Continuously scan products in endless loop - RUNS FOREVER, NEVER STOPS.

    This task runs FOREVER, cycling through product IDs and resuming
    automatically after any crash or restart. NO time limits, NO stopping.

    Args:
        platform: Target platform (uzum, uzex)
        batch_target: Products to find per mini-batch before checkpoint
        pause_between_cycles: Seconds to wait between full cycles
        max_id: Maximum product ID to scan

    Returns:
        Status dict (only on graceful stop - never happens)
    """
    logger.info(f"🚀 Starting CONTINUOUS scan for {platform}")
    
    async def do_continuous_scan():
        from src.core.checkpoint import get_checkpoint_manager
        
        # Get checkpoint for resume
        checkpoint = await get_checkpoint_manager(platform, "continuous")
        saved = await checkpoint.load_checkpoint()
        
        current_position = saved.get("last_id", 1) if saved else 1
        total_found = saved.get("total_found", 0) if saved else 0
        cycles_completed = saved.get("cycles", 0) if saved else 0
        
        logger.info(f"📍 Resuming from ID {current_position:,}, {cycles_completed} cycles done, {total_found:,} total found")
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while True:  # Endless loop
            try:
                if platform == "uzum":
                    from src.platforms.uzum import UzumDownloader
                    
                    # Scan a chunk of 100k IDs at a time
                    chunk_end = min(current_position + 100000, max_id)
                    
                    downloader = UzumDownloader(concurrency=50, db_batch_size=100)
                    stats = await downloader.download_range(
                        start_id=current_position,
                        end_id=chunk_end,
                        target=batch_target,
                        resume=False  # We manage resume ourselves
                    )
                    
                    total_found += stats.found
                    current_position = stats.last_id
                    consecutive_errors = 0  # Reset on success
                    
                    # Save checkpoint
                    await checkpoint.save_checkpoint({
                        "last_id": current_position,
                        "total_found": total_found,
                        "cycles": cycles_completed,
                        "last_run": datetime.now(timezone.utc).isoformat(),
                        "rate": stats.rate,
                    })
                    
                    logger.info(
                        f"📊 Progress: ID {current_position:,} / {max_id:,} | "
                        f"Total found: {total_found:,} | "
                        f"This batch: {stats.found:,} | "
                        f"Rate: {stats.rate:.0f}/sec"
                    )
                    
                    # Check if we've completed a full cycle
                    if current_position >= max_id:
                        cycles_completed += 1
                        current_position = 1  # Restart from beginning
                        
                        logger.info(
                            f"🔄 CYCLE {cycles_completed} COMPLETE! "
                            f"Total products: {total_found:,}. "
                            f"Pausing {pause_between_cycles}s before next cycle..."
                        )
                        
                        await checkpoint.save_checkpoint({
                            "last_id": 1,
                            "total_found": total_found,
                            "cycles": cycles_completed,
                            "cycle_completed_at": datetime.now(timezone.utc).isoformat(),
                        })
                        
                        await asyncio.sleep(pause_between_cycles)
                    
                    # Small delay between batches to prevent overload
                    await asyncio.sleep(5)
                    
                elif platform == "uzex":
                    from src.platforms.uzex import UzexDownloader

                    downloader = UzexDownloader(batch_size=100)
                    stats = await downloader.download_lots(
                        lot_type="auction",
                        status="completed",
                        target=batch_target,
                        start_from=current_position,
                        resume=True,
                        skip_existing=False  # Re-download to update & catch new lots
                    )
                    
                    total_found += stats.found
                    current_position += 10000  # Move to next range
                    consecutive_errors = 0
                    
                    await checkpoint.save_checkpoint({
                        "last_id": current_position,
                        "total_found": total_found,
                        "cycles": cycles_completed,
                        "last_run": datetime.now(timezone.utc).isoformat(),
                    })
                    
                    logger.info(f"📊 UZEX Progress: {total_found:,} lots found")
                    
                    # UZEX has less data, longer pause
                    await asyncio.sleep(60)
                    
                    if current_position >= max_id:
                        cycles_completed += 1
                        current_position = 1
                        await asyncio.sleep(pause_between_cycles)
                        
                else:
                    raise ValueError(f"Unknown platform: {platform}")
                    
            except asyncio.CancelledError:
                logger.info("⏹️ Continuous scan cancelled gracefully")
                break
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"❌ Error in continuous scan (attempt {consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"🔴 Circuit breaker: {max_consecutive_errors} consecutive errors, pausing 5 minutes...")
                    await asyncio.sleep(300)  # 5 min cooldown
                    consecutive_errors = 0
                else:
                    # Exponential backoff
                    wait_time = min(60 * (2 ** consecutive_errors), 300)
                    logger.info(f"⏳ Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                continue  # Don't break, just retry
        
        return {
            "status": "stopped",
            "position": current_position,
            "total_found": total_found,
            "cycles": cycles_completed,
        }
    
    try:
        return run_async(do_continuous_scan())
    except Exception as e:
        logger.error(f"Fatal error in continuous_scan: {e}. Task will retry in 60s.")
        raise self.retry(exc=e, countdown=60)


@shared_task
def check_continuous_status(platform: str = "uzum") -> dict:
    """
    Check the status of continuous scraping.
    
    Returns:
        Status dict with progress information
    """
    async def do_check():
        from src.core.checkpoint import get_checkpoint_manager
        
        checkpoint = await get_checkpoint_manager(platform, "continuous")
        saved = await checkpoint.load_checkpoint()
        
        if not saved:
            return {"status": "not_started", "platform": platform}
        
        last_run = saved.get("last_run")
        if last_run:
            last_run_dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
            if last_run_dt.tzinfo is None:
                last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - last_run_dt).total_seconds()
        else:
            age = None
        
        return {
            "status": "running" if age and age < 3600 else "stale",
            "platform": platform,
            "last_id": saved.get("last_id"),
            "total_found": saved.get("total_found"),
            "cycles": saved.get("cycles"),
            "last_run": last_run,
            "age_seconds": age,
        }
    
    return run_async(do_check())


@shared_task
def restart_if_stale(platform: str = "uzum", max_stale_seconds: int = 3600) -> dict:
    """
    Restart continuous scraping if it appears to be stuck.
    
    Args:
        platform: Platform to check
        max_stale_seconds: Consider stale if no update for this long
        
    Returns:
        Action taken
    """
    status = check_continuous_status(platform)
    
    if status.get("age_seconds", 0) > max_stale_seconds or status.get("status") == "not_started":
        logger.warning(f"🔄 Continuous scan for {platform} appears stale, restarting...")
        continuous_scan.delay(platform)
        return {"action": "restarted", "platform": platform}
    
    return {"action": "healthy", "platform": platform, "age": status.get("age_seconds")}
