"""
Debug Configuration for Yandex Platform

This module provides comprehensive debugging configuration for the Yandex Market
integration, making it easy to enable detailed logging for troubleshooting and
monitoring.

Usage:
    from src.platforms.yandex.debug_config import enable_debug, disable_debug

    # Enable debug logging
    enable_debug()

    # Enable with file output
    enable_debug(log_to_file=True, log_file="yandex_debug.log")

    # Disable debug logging
    disable_debug()
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output to make debug logs easier to read."""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        return super().format(record)


class YandexDebugConfig:
    """Configuration manager for Yandex platform debug logging."""

    # All Yandex debug loggers
    DEBUG_LOGGERS = [
        "src.platforms.yandex.client.debug",
        "src.platforms.yandex.platform.debug",
        "src.platforms.yandex.category_walker.debug",
        "src.platforms.yandex.attribute_mapper.debug",
        "src.platforms.yandex.parser.debug",
        "src.workers.yandex_tasks.debug",
    ]

    # Standard loggers (less verbose)
    STANDARD_LOGGERS = [
        "src.platforms.yandex.client",
        "src.platforms.yandex.platform",
        "src.platforms.yandex.category_walker",
        "src.platforms.yandex.attribute_mapper",
        "src.platforms.yandex.parser",
        "src.workers.yandex_tasks",
    ]

    def __init__(self):
        self.handlers = []
        self.original_levels = {}

    def enable_debug(
        self,
        log_to_file: bool = False,
        log_file: Optional[str] = None,
        log_to_console: bool = True,
        include_standard_logs: bool = True,
        max_file_size: str = "50MB",
        backup_count: int = 3,
        component_filter: Optional[List[str]] = None,
    ):
        """
        Enable comprehensive debug logging for Yandex platform.

        Args:
            log_to_file: Enable file logging
            log_file: Custom log file path (default: auto-generated)
            log_to_console: Enable console logging
            include_standard_logs: Include standard (INFO level) logs
            max_file_size: Maximum size per log file (with rotation)
            backup_count: Number of backup files to keep
            component_filter: Only enable debug for specific components
                            (client, platform, category_walker, attribute_mapper, parser, tasks)
        """
        print("🔍 Enabling Yandex platform debug logging...")

        # Filter loggers if component filter is specified
        debug_loggers = self.DEBUG_LOGGERS
        standard_loggers = self.STANDARD_LOGGERS

        if component_filter:
            filtered_debug = []
            filtered_standard = []

            for component in component_filter:
                filtered_debug.extend(
                    [logger for logger in debug_loggers if component in logger]
                )
                filtered_standard.extend(
                    [logger for logger in standard_loggers if component in logger]
                )

            debug_loggers = filtered_debug
            standard_loggers = filtered_standard
            print(f"📋 Filtered to components: {component_filter}")

        # Store original levels for restoration
        for logger_name in debug_loggers + standard_loggers:
            logger = logging.getLogger(logger_name)
            self.original_levels[logger_name] = logger.level

        # Console handler with colors
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = ColoredFormatter(
                fmt="%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%H:%M:%S",
            )
            console_handler.setFormatter(console_formatter)
            self.handlers.append(console_handler)
            print("📺 Console logging enabled with colors")

        # File handler with rotation
        if log_to_file:
            if not log_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = f"yandex_debug_{timestamp}.log"

            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self._parse_size(max_file_size),
                backupCount=backup_count,
            )
            file_formatter = logging.Formatter(
                fmt="%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            self.handlers.append(file_handler)
            print(f"📄 File logging enabled: {log_file}")

        # Configure debug loggers (most verbose)
        for logger_name in debug_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)

            # Remove existing handlers to avoid duplicates
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

            # Add our handlers
            for handler in self.handlers:
                logger.addHandler(handler)

            logger.propagate = False  # Prevent duplicate messages

        print(f"🔧 Enabled DEBUG level for {len(debug_loggers)} debug loggers")

        # Configure standard loggers (less verbose)
        if include_standard_logs:
            for logger_name in standard_loggers:
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.INFO)

                # Add handlers if not already present
                for handler in self.handlers:
                    if handler not in logger.handlers:
                        logger.addHandler(handler)

                logger.propagate = False

            print(f"📊 Enabled INFO level for {len(standard_loggers)} standard loggers")

        print("✅ Yandex debug logging enabled successfully!")
        print("\n🎯 Debug categories enabled:")
        print("   🌐 HTTP Client (requests, responses, rate limiting)")
        print("   🏗️  Platform (three-tier scraping, data flow)")
        print("   🚶 Category Walker (product discovery, pagination)")
        print("   🔄 Attribute Mapper (Uzbek key mapping, normalization)")
        print("   📊 Parser (JSON extraction, data parsing)")
        print("   ⚙️  Worker Tasks (Celery job processing)")

    def disable_debug(self):
        """Disable debug logging and restore original levels."""
        print("🔇 Disabling Yandex platform debug logging...")

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

        print("✅ Debug logging disabled, original levels restored")

    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '50MB' into bytes."""
        size_str = size_str.upper()

        if size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)  # Assume bytes

    def get_logger_status(self) -> dict:
        """Get current status of all Yandex loggers."""
        status = {
            "debug_loggers": {},
            "standard_loggers": {},
            "handlers_active": len(self.handlers),
        }

        for logger_name in self.DEBUG_LOGGERS:
            logger = logging.getLogger(logger_name)
            status["debug_loggers"][logger_name] = {
                "level": logging.getLevelName(logger.level),
                "handlers": len(logger.handlers),
                "propagate": logger.propagate,
            }

        for logger_name in self.STANDARD_LOGGERS:
            logger = logging.getLogger(logger_name)
            status["standard_loggers"][logger_name] = {
                "level": logging.getLevelName(logger.level),
                "handlers": len(logger.handlers),
                "propagate": logger.propagate,
            }

        return status


# Global instance
_debug_config = YandexDebugConfig()


# Convenience functions
def enable_debug(**kwargs):
    """Enable Yandex platform debug logging."""
    return _debug_config.enable_debug(**kwargs)


def disable_debug():
    """Disable Yandex platform debug logging."""
    return _debug_config.disable_debug()


def get_logger_status():
    """Get current logger status."""
    return _debug_config.get_logger_status()


# Preset configurations
def enable_minimal_debug():
    """Enable debug for core components only (client, platform)."""
    enable_debug(
        log_to_console=True,
        log_to_file=False,
        component_filter=["client", "platform"],
        include_standard_logs=False,
    )


def enable_discovery_debug():
    """Enable debug for product discovery (category_walker, parser)."""
    enable_debug(
        log_to_console=True,
        log_to_file=True,
        component_filter=["category_walker", "parser", "attribute_mapper"],
        include_standard_logs=True,
    )


def enable_full_debug():
    """Enable comprehensive debug logging with file output."""
    enable_debug(
        log_to_console=True,
        log_to_file=True,
        include_standard_logs=True,
        max_file_size="100MB",
        backup_count=5,
    )


def enable_production_debug():
    """Enable debug logging suitable for production (file only)."""
    enable_debug(
        log_to_console=False,
        log_to_file=True,
        include_standard_logs=True,
        max_file_size="200MB",
        backup_count=10,
    )


# Context managers for temporary debug enabling
class DebugContext:
    """Context manager for temporary debug enabling."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        enable_debug(**self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        disable_debug()


def debug_context(**kwargs):
    """Create a debug context manager."""
    return DebugContext(**kwargs)


# Example usage
if __name__ == "__main__":
    import time

    print("🧪 Testing Yandex debug configuration...")

    # Test basic debug
    enable_minimal_debug()

    # Get a logger and test it
    test_logger = logging.getLogger("src.platforms.yandex.client.debug")
    test_logger.debug("This is a test debug message")
    test_logger.info("This is a test info message")

    print("\n📊 Logger status:")
    import json

    status = get_logger_status()
    print(json.dumps(status, indent=2))

    time.sleep(1)

    disable_debug()
    print("🧪 Test completed!")
