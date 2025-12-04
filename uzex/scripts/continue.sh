#!/bin/bash
echo "Resuming/Starting scraping with persistence..."

# Ensure crawls directory exists for state persistence
mkdir -p ../crawls

echo "Starting Auction Spider (Resumable)..."
docker-compose exec -T scraper scrapy crawl auctions -s JOBDIR=crawls/auctions-1

echo "Starting Shop Spider (Resumable)..."
docker-compose exec -T scraper scrapy crawl shops -s JOBDIR=crawls/shops-1

echo "Scraping jobs initiated."
