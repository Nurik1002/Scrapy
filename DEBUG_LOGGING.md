# Debug Logging Guide - Scrapy Marketplace Analytics Platform

## 🎯 Overview

This guide covers the comprehensive debug logging system implemented across the entire Scrapy Marketplace Analytics Platform. The debug logging system provides detailed troubleshooting capabilities for all components including core modules, platform scrapers, workers, and API endpoints.

## 🚀 Quick Start

### Enable Full Project Debug

```python
# Enable comprehensive debug logging
from src.debug_config import enable_full_debug, disable_project_debug

# Turn on all debug logging
enable_full_debug()

# Your code here...
# All debug messages will be shown

# Turn off when done
disable_project_debug()
```

### Enable Debug for Specific Components

```python
from src.debug_config import enable_project_debug

# Debug only database and platform operations
enable_project_debug(
    components=['core', 'platforms'],
    log_to_console=True,
    log_to_file=True
)
```

## 📦 Components Available

### Core Components (`core`)
- **Database** (`src.core.database.debug`) - Connection management, session handling, multi-database operations
- **Bulk Operations** (`src.core.bulk_ops.debug`) - High-performance database bulk inserts and upserts
- **Checkpoints** (`src.core.checkpoint.debug`) - Progress tracking and resume capabilities
- **Redis Client** (`src.core.redis_client.debug`) - Redis connection and operations

### Platform Scrapers (`platforms`)
- **Uzum** (`src.platforms.uzum.*.debug`) - Uzum.uz API client, parsing, downloading
- **Yandex** (`src.platforms.yandex.*.debug`) - Yandex Market scraping with anti-bot evasion
- **UZEX** (`src.platforms.uzex.*.debug`) - Government procurement platform scraping
- **Base Platform** (`src.platforms.base.debug`) - Abstract platform interface

### Background Workers (`workers`)
- **Download Tasks** (`src.workers.download_tasks.debug`) - Product downloading workers
- **Process Tasks** (`src.workers.process_tasks.debug`) - Data processing workers
- **Analytics Tasks** (`src.workers.analytics_tasks.debug`) - Analytics computation workers
- **Yandex Tasks** (`src.workers.yandex_tasks.debug`) - Yandex-specific background tasks

### API Endpoints (`api`)
- **Main API** (`src.api.main.debug`) - FastAPI application setup
- **Product Routes** (`src.api.routers.products.debug`) - Product API endpoints
- **Seller Routes** (`src.api.routers.sellers.debug`) - Seller API endpoints
- **Analytics Routes** (`src.api.routers.analytics.debug`) - Analytics API endpoints

### Database Schemas (`schemas`)
- **Ecommerce Schema** (`src.schemas.ecommerce.debug`) - B2C platform data models
- **Classifieds Schema** (`src.schemas.classifieds.debug`) - C2C platform data models
- **Procurement Schema** (`src.schemas.procurement.debug`) - B2B platform data models

## 🔧 Usage Examples

### 1. Development Debugging

```python
from src.debug_config import enable_development_debug

# Optimized for development work
enable_development_debug()

# This enables:
# - Console output with colors
# - File logging
# - Standard logs included
# - External libraries at WARNING level (reduces noise)
```

### 2. Production Troubleshooting

```python
from src.debug_config import enable_production_debug

# Safe for production - file logging only
enable_production_debug()

# This enables:
# - File logging only (no console spam)
# - INFO level for less verbosity
# - Large log files with rotation
# - No external library debug logs
```

### 3. Component-Specific Debugging

#### Database Issues
```python
from src.debug_config import enable_core_debug

enable_core_debug()
# Now debug database connections, bulk operations, checkpoints
```

#### Platform Scraping Issues
```python
from src.debug_config import enable_platforms_debug

enable_platforms_debug()
# Debug all platform scrapers (Uzum, Yandex, UZEX)
```

#### Worker/Celery Issues
```python
from src.debug_config import enable_workers_debug

enable_workers_debug()
# Debug background tasks and Celery workers
```

#### API Issues
```python
from src.debug_config import enable_api_debug

enable_api_debug()
# Debug FastAPI endpoints and routing
```

### 4. Yandex-Specific Debugging

```python
# Import both project-wide and Yandex-specific debug
from src.debug_config import enable_project_debug
from src.platforms.yandex.debug_config import enable_debug as enable_yandex_debug

# Enable project-wide platforms debug
enable_project_debug(components=['platforms'])

# Additionally enable detailed Yandex debugging
enable_yandex_debug(
    component_filter=['client', 'category_walker', 'attribute_mapper'],
    log_to_file=True
)
```

### 5. Context Managers (Temporary Debug)

```python
from src.debug_config import debug_context, core_debug_context

# Temporary debugging for a specific operation
with debug_context(components=['core'], log_to_console=True):
    # Your database operations here
    # Debug logging is automatically enabled and disabled
    pass

# Specialized context managers
with core_debug_context():
    # Core debugging only
    pass
```

### 6. Custom Debug Configuration

```python
from src.debug_config import enable_project_debug

enable_project_debug(
    components=['core', 'platforms'],           # Which components
    log_to_console=True,                       # Console output
    log_to_file=True,                          # File output
    log_file='custom_debug.log',               # Custom file name
    include_standard_logs=True,                # Include INFO logs
    include_external_libs=False,               # Skip SQLAlchemy/Celery logs
    console_level='DEBUG',                     # Console verbosity
    file_level='INFO',                         # File verbosity (less verbose)
    max_file_size='50MB',                      # Log rotation
    backup_count=3                             # Keep 3 backup files
)
```

## 📊 Understanding Debug Output

### Console Output Format
```
14:23:45 | src.platforms.yandex.client.debug | DEBUG    | fetch_product:245 | Fetching Yandex product: 1779261899
14:23:45 | src.platforms.yandex.client.debug | DEBUG    | fetch_product:249 | Product URL: https://market.yandex.uz/product--makita/1779261899
14:23:47 | src.platforms.yandex.client.debug | DEBUG    | _fetch_html:295   | Response status: 200, headers: {'content-type': 'text/html'}
```

**Format**: `timestamp | logger_name | level | function:line | message`

### File Output Format
```
2024-12-08 14:23:45 | src.platforms.yandex.client.debug | DEBUG    | fetch_product:245 | Fetching Yandex product: 1779261899
```

### Debug Message Types

#### Database Operations
```
src.core.database.debug | Creating session for database: 'ecommerce'
src.core.database.debug | Session created for 'ecommerce', yielding to context
src.core.database.debug | Session for 'ecommerce' completed successfully, committing
```

#### Platform Scraping
```
src.platforms.yandex.client.debug | Fetching HTML from: https://market.yandex.uz/product--...
src.platforms.yandex.parser.debug | Extracting product from LD+JSON for 1779261899
src.platforms.yandex.attribute_mapper.debug | Mapping 15 attributes for category 'electronics_smartphones'
```

#### Worker Tasks
```
src.workers.yandex_tasks.debug | Processing discovered product: 1779261899
src.workers.yandex_tasks.debug | Queuing product 1779261899 for detailed scraping
```

## 🎯 Troubleshooting Common Issues

### Issue: No Debug Output

**Problem**: Enabled debug but seeing no messages.

**Solutions**:
```python
# 1. Check if debug is actually enabled
from src.debug_config import get_debug_status
status = get_debug_status()
print(f"Active handlers: {status['handlers_active']}")
print(f"Configured loggers: {status['loggers_configured']}")

# 2. Verify component names
enable_project_debug(components=['platforms'])  # Correct
# enable_project_debug(components=['platform'])   # Wrong - no 's'

# 3. Check logger name matches
import logging
logger = logging.getLogger('src.platforms.yandex.client.debug')
logger.debug('Test message')
```

### Issue: Too Much Output

**Problem**: Debug output is overwhelming.

**Solutions**:
```python
# 1. Use component filtering
enable_project_debug(components=['core'])  # Only core, not everything

# 2. Reduce external library noise
enable_project_debug(
    include_external_libs=True,
    external_lib_level='WARNING'  # Only warnings/errors from SQLAlchemy etc
)

# 3. Use file-only logging for detailed debug
enable_project_debug(
    log_to_console=False,  # No console spam
    log_to_file=True,      # Detailed file logs
    console_level='INFO'   # Only important console messages
)
```

### Issue: File Permissions

**Problem**: Cannot write to log file.

**Solutions**:
```python
# 1. Specify writable directory
enable_project_debug(
    log_to_file=True,
    log_file='/tmp/scrapy_debug.log'  # Use /tmp or another writable location
)

# 2. Create directory first
from pathlib import Path
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
enable_project_debug(log_file='logs/debug.log')
```

### Issue: Performance Impact

**Problem**: Debug logging slowing down the application.

**Solutions**:
```python
# 1. Use production-safe settings
enable_production_debug()  # File only, INFO level

# 2. Disable debug for performance-critical sections
with debug_context(components=['core']):  # Temporary debugging
    # Only debug the problematic section
    pass

# 3. Use component filtering
enable_project_debug(
    components=['platforms'],  # Only debug scrapers, not database
    file_level='INFO'          # Less verbose
)
```

## 🔄 Integration with Existing Code

### Adding Debug to New Modules

```python
import logging

# Standard logger (always include)
logger = logging.getLogger(__name__)

# Debug logger (for detailed troubleshooting)
debug_logger = logging.getLogger(f"{__name__}.debug")

class YourClass:
    def your_method(self, param):
        debug_logger.debug(f"Starting your_method with param: {param}")
        
        try:
            # Your logic here
            result = self.process_data(param)
            debug_logger.debug(f"Processing completed, result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Method failed: {e}")
            debug_logger.debug(f"Method error details: {type(e).__name__}: {str(e)}")
            raise
```

### Best Practices for Debug Messages

#### Good Debug Messages
```python
debug_logger.debug(f"Processing {len(products)} products for platform {platform}")
debug_logger.debug(f"Database query returned {result_count} rows in {elapsed:.2f}s")
debug_logger.debug(f"HTTP request to {url} returned status {status_code}")
debug_logger.debug(f"Parsed {len(attributes)} attributes: {list(attributes.keys())}")
```

#### Avoid These
```python
debug_logger.debug("Processing products")          # Too vague
debug_logger.debug(f"Full data: {huge_object}")    # Too much data
debug_logger.debug("Error occurred")               # Not helpful
```

## 📈 Monitoring and Log Analysis

### Log File Analysis

```bash
# Find errors in debug logs
grep "ERROR" scrapy_debug_*.log

# Monitor real-time debug output
tail -f scrapy_debug.log | grep "yandex"

# Count debug messages by component
grep -c "src.platforms" scrapy_debug.log
grep -c "src.core" scrapy_debug.log
```

### Log Rotation

The debug system automatically rotates log files:
- Default: 100MB per file
- Keeps 5 backup files
- Files named: `scrapy_debug.log`, `scrapy_debug.log.1`, etc.

```python
# Custom rotation settings
enable_project_debug(
    max_file_size='50MB',   # Smaller files
    backup_count=10         # Keep more backups
)
```

## ⚡ Performance Considerations

### Debug Impact
- **Console Logging**: ~5-10% performance impact
- **File Logging**: ~2-3% performance impact  
- **No Handlers**: Minimal impact (debug statements still evaluated)

### Production Usage
```python
# Safe for production (file only, INFO level)
enable_production_debug()

# Or disable completely
disable_project_debug()
```

### Memory Usage
Debug logging uses memory for:
- Log message formatting
- File buffers
- Handler objects

The system automatically:
- Rotates large files
- Limits buffer sizes
- Cleans up closed handlers

## 🆘 Getting Help

### Debug System Status
```python
from src.debug_config import get_debug_status
import json
status = get_debug_status()
print(json.dumps(status, indent=2))
```

### Reset Debug Configuration
```python
from src.debug_config import disable_project_debug

# Reset everything
disable_project_debug()

# Start fresh
enable_project_debug(components=['core'])
```

### Common Commands Summary

| Task | Command |
|------|---------|
| Full debug | `enable_full_debug()` |
| Core only | `enable_core_debug()` |
| Platforms only | `enable_platforms_debug()` |
| Workers only | `enable_workers_debug()` |
| Production safe | `enable_production_debug()` |
| Development | `enable_development_debug()` |
| Turn off | `disable_project_debug()` |
| Check status | `get_debug_status()` |

---

## 📚 Related Documentation

- **Yandex Platform Debug**: `src/platforms/yandex/debug_config.py`
- **Core Database**: `src/core/database.py` 
- **Worker Tasks**: `src/workers/`
- **API Documentation**: `src/api/`
- **Project Configuration**: `src/core/config.py`

---

**🎯 Remember**: Debug logging is a powerful tool, but use it wisely. Enable only what you need, and always disable debug logging when you're done troubleshooting to maintain optimal performance.