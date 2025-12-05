# Uzum.uz Scraper

High-performance scraper for `uzum.uz` using **Scrapy**, **Playwright**, and **PostgreSQL**.

## Features
- **Hybrid Strategy**: Uses Playwright for category discovery (bypassing Cloudflare) and direct API for high-speed product extraction.
- **PostgreSQL Storage**: Stores Products, Sellers, and Price History in a structured database.
- **Analytics**: Includes scripts to generate reports on Sellers and Prices.
- **Dockerized**: Easy deployment with Docker Compose.

## 🚀 Quick Start

1.  **Start the Stack**:
    ```bash
    cd uzum
    ./scripts/start.sh
    ```

2.  **Run the Spider**:
    ```bash
    docker-compose exec scraper scrapy crawl uzum
    ```

3.  **View Analytics**:
    ```bash
    # Install tabulate locally if needed: pip install tabulate psycopg2-binary
    python scripts/run_analytics.py
    ```

## Project Structure
- `uzum_spider/`: Scrapy project.
    - `spiders/uzum.py`: The main spider.
    - `models.py`: SQLAlchemy database models.
    - `pipelines.py`: Saves data to Postgres.
- `scripts/`: Helper scripts.
- `docker-compose.yml`: Production stack.

## Database Schema
- **products**: Product details (title, specs, images).
- **sellers**: Seller info (name, rating).
- **price_history**: Historical prices for products.
