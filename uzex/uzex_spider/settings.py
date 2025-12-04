BOT_NAME = 'uzex_spider'

SPIDER_MODULES = ['uzex_spider.spiders']
NEWSPIDER_MODULE = 'uzex_spider.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
DOWNLOAD_DELAY = 0.5
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'en-US,en;q=0.9',
  'Content-Type': 'application/json',
}

# Enable or disable spider middlewares
#SPIDER_MIDDLEWARES = {
#    'uzex_spider.middlewares.UzexSpiderSpiderMiddleware': 543,
#}

# Enable or disable downloader middlewares
#DOWNLOADER_MIDDLEWARES = {
#    'uzex_spider.middlewares.UzexSpiderDownloaderMiddleware': 543,
#}

# Configure item pipelines
ITEM_PIPELINES = {
   'uzex_spider.pipelines.PostgresPipeline': 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Database settings
DATABASE_URL = "postgresql://uzex_user:uzex_password@db:5432/uzex_db"
