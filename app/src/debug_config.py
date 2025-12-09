"""
Project-Wide Debug Configuration - Comprehensive debugging for Scrapy Marketplace Platform

This module provides comprehensive debugging configuration for the entire
Scrapy Marketplace Analytics Platform, making it easy to enable detailed
logging for troubleshooting, monitoring, and development.

Key Features:
- Project-wide debug logging control
- Component-specific filtering (core, platforms, workers, api)
- Multiple output formats (console, file, both)
- Colored console output for better readability
- Preset configurations for common scenarios
- Integration with existing logging infrastructure

Usage:
    from src.debug_config import enable_project_debug, disable_project_debug

    # Enable full project debug
    enable_project_debug()

    # Enable debug for specific components
    enable_project_debug(components=['core', 'platforms'])

    # Production-safe debug (file only)
    enable_project_debug(log_to_console=False, log_to_file=True)
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

# Import Yandex-specific debug config for integration
try:
    from .platforms.yandex.debug_config import ColoredFormatter, YandexDebugConfig
except ImportError:
    # Fallback if Yandex module not available
    class ColoredFormatter(logging.Formatter):
        """Simple colored formatter fallback."""

        COLORS = {
            "DEBUG": "\033[36m",
            "INFO": "\033[32m",
            "WARNING": "\033[33m",
            "ERROR": "\033[31m",
            "CRITICAL": "\033[35m",
        }
        RESET = "\033[0m"

        def format(self, record):
            if record.levelname in self.COLORS:
                record.levelname = (
                    f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
                )
            return super().format(record)

    YandexDebugConfig = None


class ProjectDebugConfig:
    """
    Comprehensive debug configuration for the entire Scrapy platform.

    Manages debug logging across all project components with granular control
    and multiple output options.
    """

    # All project debug loggers organized by component
    PROJECT_LOGGERS = {
        "core": {
            "debug": [
                "src.core.database.debug",
                "src.core.bulk_ops.debug",
                "src.core.checkpoint.debug",
                "src.core.redis_client.debug",
                "src.core.config.debug",
                "src.core.models.debug",
            ],
            "standard": [
                "src.core.database",
                "src.core.bulk_ops",
                "src.core.checkpoint",
                "src.core.redis_client",
                "src.core.config",
                "src.core.models",
            ],
        },
        "platforms": {
            "debug": [
                "src.platforms.base.debug",
                "src.platforms.uzum.client.debug",
                "src.platforms.uzum.downloader.debug",
                "src.platforms.uzum.parser.debug",
                "src.platforms.yandex.client.debug",
                "src.platforms.yandex.platform.debug",
                "src.platforms.yandex.category_walker.debug",
                "src.platforms.yandex.attribute_mapper.debug",
                "src.platforms.yandex.parser.debug",
                "src.platforms.uzex.client.debug",
                "src.platforms.uzex.scraper.debug",
                "src.platforms.uzex.models.debug",
            ],
            "standard": [
                "src.platforms.base",
                "src.platforms.uzum.client",
                "src.platforms.uzum.downloader",
                "src.platforms.uzum.parser",
                "src.platforms.yandex.client",
                "src.platforms.yandex.platform",
                "src.platforms.yandex.category_walker",
                "src.platforms.yandex.attribute_mapper",
                "src.platforms.yandex.parser",
                "src.platforms.uzex.client",
                "src.platforms.uzex.scraper",
                "src.platforms.uzex.models",
            ],
        },
        "workers": {
            "debug": [
                "src.workers.celery_app.debug",
                "src.workers.download_tasks.debug",
                "src.workers.process_tasks.debug",
                "src.workers.analytics_tasks.debug",
                "src.workers.maintenance_tasks.debug",
                "src.workers.continuous_scraper.debug",
                "src.workers.yandex_tasks.debug",
            ],
            "standard": [
                "src.workers.celery_app",
                "src.workers.download_tasks",
                "src.workers.process_tasks",
                "src.workers.analytics_tasks",
                "src.workers.maintenance_tasks",
                "src.workers.continuous_scraper",
                "src.workers.yandex_tasks",
            ],
        },
        "api": {
            "debug": [
                "src.api.main.debug",
                "src.api.routers.products.debug",
                "src.api.routers.sellers.debug",
                "src.api.routers.analytics.debug",
                "src.api.routers.stats.debug",
            ],
            "standard": [
                "src.api.main",
                "src.api.routers.products",
                "src.api.routers.sellers",
                "src.api.routers.analytics",
                "src.api.routers.stats",
            ],
        },
        "schemas": {
            "debug": [
                "src.schemas.ecommerce.debug",
                "src.schemas.classifieds.debug",
                "src.schemas.procurement.debug",
            ],
            "standard": [
                "src.schemas.ecommerce",
                "src.schemas.classifieds",
                "src.schemas.procurement",
            ],
        },
    }

    # SQLAlchemy and external library loggers
    EXTERNAL_LOGGERS = {
        "sqlalchemy": [
            "sqlalchemy.engine",
            "sqlalchemy.pool",
            "sqlalchemy.dialects",
            "sqlalchemy.orm",
        ],
        "celery": [
            "celery.app",
            "celery.worker",
            "celery.beat",
            "celery.task",
        ],
        "fastapi": [
            "fastapi",
            "uvicorn",
            "uvicorn.access",
            "uvicorn.error",
        ],
        "http": [
            "aiohttp.client",
            "aiohttp.server",
            "httpx",
            "urllib3",
        ],
    }

    def __init__(self):
        self.handlers = []
        self.original_levels = {}
        self.yandex_debug_config = None

        # Initialize Yandex debug config if available
        if YandexDebugConfig:
            self.yandex_debug_config = YandexDebugConfig()

    def enable_project_debug(
        self,
        components: Optional[List[str]] = None,
        log_to_file: bool = False,
        log_file: Optional[str] = None,
        log_to_console: bool = True,
        include_standard_logs: bool = True,
        include_external_libs: bool = False,
        external_lib_level: str = "INFO",
        max_file_size: str = "100MB",
        backup_count: int = 5,
        console_level: str = "DEBUG",
        file_level: str = "DEBUG",
    ):
        """
        Enable comprehensive debug logging for the project.

        Args:
            components: List of components to debug ['core', 'platforms', 'workers', 'api', 'schemas']
                       (None = all components)
            log_to_file: Enable file logging
            log_file: Custom log file path
            log_to_console: Enable console logging
            include_standard_logs: Include standard (INFO level) logs
            include_external_libs: Include external library debug logs
            external_lib_level: Log level for external libraries
            max_file_size: Maximum size per log file (with rotation)
            backup_count: Number of backup files to keep
            console_level: Log level for console output
            file_level: Log level for file output
        """
        print("🚀 Enabling Scrapy project-wide debug logging...")

        # Default to all components if none specified
        if components is None:
            components = list(self.PROJECT_LOGGERS.keys())
            print(f"📦 Enabling debug for ALL components: {components}")
        else:
            print(f"📦 Enabling debug for selected components: {components}")

        # Validate components
        invalid_components = [c for c in components if c not in self.PROJECT_LOGGERS]
        if invalid_components:
            print(f"⚠️  Invalid components ignored: {invalid_components}")
            components = [c for c in components if c in self.PROJECT_LOGGERS]

        # Gather loggers to configure
        debug_loggers = []
        standard_loggers = []

        for component in components:
            debug_loggers.extend(self.PROJECT_LOGGERS[component]["debug"])
            standard_loggers.extend(self.PROJECT_LOGGERS[component]["standard"])

        print(f"🔧 Configuring {len(debug_loggers)} debug loggers")
        print(f"📊 Configuring {len(standard_loggers)} standard loggers")

        # Store original levels for restoration
        all_loggers = debug_loggers + standard_loggers
        for logger_name in all_loggers:
            logger = logging.getLogger(logger_name)
            self.original_levels[logger_name] = logger.level

        # Create handlers
        self._create_handlers(
            log_to_console,
            log_to_file,
            log_file,
            console_level,
            file_level,
            max_file_size,
            backup_count,
        )

        # Configure debug loggers (most verbose)
        self._configure_loggers(debug_loggers, logging.DEBUG)

        # Configure standard loggers (less verbose)
        if include_standard_logs:
            self._configure_loggers(standard_loggers, logging.INFO)
            print(f"✅ Enabled INFO level for {len(standard_loggers)} standard loggers")

        # Configure external library loggers
        if include_external_libs:
            self._configure_external_loggers(external_lib_level)

        # Special handling for Yandex platform
        if "platforms" in components and self.yandex_debug_config:
            print("🔍 Integrating Yandex-specific debug configuration...")
            # The Yandex debug config will be managed separately to avoid conflicts

        print("✅ Project-wide debug logging enabled successfully!")
        self._print_debug_summary(components, include_external_libs)

    def _create_handlers(
        self,
        log_to_console,
        log_to_file,
        log_file,
        console_level,
        file_level,
        max_file_size,
        backup_count,
    ):
        """Create logging handlers for console and/or file output."""

        # Console handler with colors
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, console_level.upper()))
            console_formatter = ColoredFormatter(
                fmt="%(asctime)s | %(name)-30s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%H:%M:%S",
            )
            console_handler.setFormatter(console_formatter)
            self.handlers.append(console_handler)
            print(f"📺 Console logging enabled (level: {console_level})")

        # File handler with rotation
        if log_to_file:
            if not log_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = f"scrapy_debug_{timestamp}.log"

            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self._parse_size(max_file_size),
                backupCount=backup_count,
            )
            file_handler.setLevel(getattr(logging, file_level.upper()))
            file_formatter = logging.Formatter(
                fmt="%(asctime)s | %(name)-30s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            self.handlers.append(file_handler)
            print(f"📄 File logging enabled: {log_file} (level: {file_level})")

    def _configure_loggers(self, logger_names: List[str], level: int):
        """Configure a list of loggers with the specified level."""
        for logger_name in logger_names:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)

            # Remove existing handlers to avoid duplicates
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

            # Add our handlers
            for handler in self.handlers:
                logger.addHandler(handler)

            logger.propagate = False  # Prevent duplicate messages

    def _configure_external_loggers(self, level: str):
        """Configure external library loggers."""
        level_obj = getattr(logging, level.upper())
        external_count = 0

        for lib_name, loggers in self.EXTERNAL_LOGGERS.items():
            for logger_name in loggers:
                logger = logging.getLogger(logger_name)
                self.original_levels[logger_name] = logger.level
                logger.setLevel(level_obj)

                for handler in self.handlers:
                    if handler not in logger.handlers:
                        logger.addHandler(handler)

                external_count += 1

        print(f"🔗 Enabled {level} level for {external_count} external library loggers")

    def _print_debug_summary(self, components: List[str], include_external: bool):
        """Print a summary of enabled debug categories."""
        print("\n🎯 Debug categories enabled:")

        category_descriptions = {
            "core": "🗄️  Core (database, bulk ops, checkpoints, config)",
            "platforms": "🏪 Platforms (Uzum, Yandex, UZEX scrapers)",
            "workers": "⚙️  Workers (Celery background tasks)",
            "api": "🌐 API (FastAPI endpoints and routers)",
            "schemas": "📊 Schemas (database models and migrations)",
        }

        for component in components:
            if component in category_descriptions:
                print(f"   {category_descriptions[component]}")

        if include_external:
            print("   🔗 External Libraries (SQLAlchemy, Celery, FastAPI)")

        print("\n💡 Use disable_project_debug() to restore original logging levels")

    def disable_project_debug(self):
        """Disable project-wide debug logging and restore original levels."""
        print("🔇 Disabling project-wide debug logging...")

        # Restore original levels
        for logger_name, original_level in self.original_levels.items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(original_level)

            # Remove our handlers
            for handler in self.handlers:
                if handler in logger.handlers:
                    logger.removeHandler(handler)

            logger.propagate = True  # Restore normal propagation

        # Close handlers
        for handler in self.handlers:
            handler.close()

        self.handlers.clear()
        self.original_levels.clear()

        # Disable Yandex debug if it was enabled
        if self.yandex_debug_config:
            try:
                self.yandex_debug_config.disable_debug()
            except Exception as e:
                print(f"⚠️  Note: Could not disable Yandex debug config: {e}")

        print("✅ Project-wide debug logging disabled, original levels restored")

    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '100MB' into bytes."""
        size_str = size_str.upper()

        if size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)  # Assume bytes

    def get_debug_status(self) -> Dict[str, any]:
        """Get comprehensive debug status for all components."""
        status = {
            "handlers_active": len(self.handlers),
            "loggers_configured": len(self.original_levels),
            "components": {},
        }

        for component, loggers in self.PROJECT_LOGGERS.items():
            component_status = {"debug_loggers": {}, "standard_loggers": {}}

            for logger_name in loggers["debug"]:
                logger = logging.getLogger(logger_name)
                component_status["debug_loggers"][logger_name] = {
                    "level": logging.getLevelName(logger.level),
                    "handlers": len(logger.handlers),
                    "propagate": logger.propagate,
                }

            for logger_name in loggers["standard"]:
                logger = logging.getLogger(logger_name)
                component_status["standard_loggers"][logger_name] = {
                    "level": logging.getLevelName(logger.level),
                    "handlers": len(logger.handlers),
                    "propagate": logger.propagate,
                }

            status["components"][component] = component_status

        return status


# Global debug configuration instance
_project_debug = ProjectDebugConfig()


# Convenience functions
def enable_project_debug(**kwargs):
    """Enable project-wide debug logging."""
    return _project_debug.enable_project_debug(**kwargs)


def disable_project_debug():
    """Disable project-wide debug logging."""
    return _project_debug.disable_project_debug()


def get_debug_status():
    """Get current debug status."""
    return _project_debug.get_debug_status()


# Preset configurations
def enable_core_debug():
    """Enable debug only for core modules (database, bulk_ops, etc.)."""
    enable_project_debug(
        components=["core"],
        log_to_console=True,
        log_to_file=True,
        include_standard_logs=True,
    )


def enable_platforms_debug():
    """Enable debug for all platform scrapers."""
    enable_project_debug(
        components=["platforms"],
        log_to_console=True,
        log_to_file=True,
        include_standard_logs=True,
    )


def enable_workers_debug():
    """Enable debug for Celery workers and background tasks."""
    enable_project_debug(
        components=["workers"],
        log_to_console=True,
        log_to_file=True,
        include_standard_logs=True,
    )


def enable_api_debug():
    """Enable debug for FastAPI endpoints."""
    enable_project_debug(
        components=["api"],
        log_to_console=True,
        log_to_file=False,
        include_standard_logs=True,
    )


def enable_full_debug():
    """Enable comprehensive debug logging for entire project."""
    enable_project_debug(
        log_to_console=True,
        log_to_file=True,
        include_standard_logs=True,
        include_external_libs=True,
        max_file_size="200MB",
        backup_count=10,
    )


def enable_production_debug():
    """Enable debug logging suitable for production (file only, no console spam)."""
    enable_project_debug(
        log_to_console=False,
        log_to_file=True,
        include_standard_logs=True,
        include_external_libs=False,
        max_file_size="500MB",
        backup_count=20,
        file_level="INFO",  # Less verbose for production
    )


def enable_development_debug():
    """Enable debug configuration optimized for development."""
    enable_project_debug(
        log_to_console=True,
        log_to_file=True,
        include_standard_logs=True,
        include_external_libs=True,
        external_lib_level="WARNING",  # Reduce external noise
        console_level="DEBUG",
        file_level="DEBUG",
    )


# Context managers for temporary debug enabling
class DebugContext:
    """Context manager for temporary debug enabling."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        enable_project_debug(**self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        disable_project_debug()


def debug_context(**kwargs):
    """Create a debug context manager."""
    return DebugContext(**kwargs)


# Special debug contexts
def core_debug_context():
    """Context manager for core debugging."""
    return DebugContext(components=["core"])


def platform_debug_context(platform: str = None):
    """Context manager for platform debugging."""
    kwargs = {"components": ["platforms"]}
    if platform:
        # Could add platform-specific filtering here
        pass
    return DebugContext(**kwargs)


def worker_debug_context():
    """Context manager for worker debugging."""
    return DebugContext(components=["workers"])


# Example usage and testing
if __name__ == "__main__":
    import time

    print("🧪 Testing Scrapy project-wide debug configuration...")

    # Test development debug
    print("\n1️⃣ Testing development debug configuration...")
    enable_development_debug()

    # Get some loggers and test them
    core_logger = logging.getLogger("src.core.database.debug")
    platform_logger = logging.getLogger("src.platforms.yandex.client.debug")
    worker_logger = logging.getLogger("src.workers.download_tasks.debug")

    core_logger.debug("🗄️  This is a core debug message")
    platform_logger.debug("🏪 This is a platform debug message")
    worker_logger.debug("⚙️  This is a worker debug message")

    print("\n📊 Debug status:")
    import json

    status = get_debug_status()
    # Print a summary instead of full status (too large)
    print(f"Active handlers: {status['handlers_active']}")
    print(f"Configured loggers: {status['loggers_configured']}")
    print(f"Components: {list(status['components'].keys())}")

    time.sleep(2)

    print("\n2️⃣ Testing context manager...")
    with debug_context(components=["core"], log_to_console=True, log_to_file=False):
        core_logger.debug("🔧 This is a context manager debug message")

    time.sleep(1)

    disable_project_debug()
    print("🧪 Test completed!")
