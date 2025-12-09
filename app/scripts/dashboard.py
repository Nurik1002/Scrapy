#!/usr/bin/env python3
"""
All-in-One Scraper Dashboard
Combines DB monitoring, worker status, and live metrics
"""

import asyncio
import asyncpg
import redis
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# ANSI Colors and Styles
class C:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'
    
    # Box drawing
    TL = '╔'
    TR = '╗'
    BL = '╚'
    BR = '╝'
    H = '═'
    V = '║'
    T = '╦'
    B = '╩'

def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

def box(title, width=40):
    """Create a box header"""
    return f"{C.TL}{C.H*(width-2)}{C.TR}\n{C.V} {title:<{width-4}} {C.V}\n{C.BL}{C.H*(width-2)}{C.BR}"

async def get_db_metrics():
    """Get comprehensive database metrics"""
    try:
        conn = await asyncpg.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5434)),
            user='scraper',
            password=os.getenv('DB_PASSWORD', 'scraper123'),
            database='uzum_scraping'
        )
        
        metrics = {}
        
        # Table counts
        tables = {
            'products': "SELECT COUNT(*) FROM products",
            'skus': "SELECT COUNT(*) FROM skus",
            'sellers': "SELECT COUNT(*) FROM sellers",
            'categories': "SELECT COUNT(*) FROM categories",
            'price_history': "SELECT COUNT(*) FROM price_history",
            'uzex_lots': "SELECT COUNT(*) FROM uzex_lots",
            'uzex_items': "SELECT COUNT(*) FROM uzex_lot_items"
        }
        
        for name, query in tables.items():
            try:
                metrics[name] = await conn.fetchval(query)
            except:
                metrics[name] = 0
        
        # Database size
        metrics['db_size'] = await conn.fetchval(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )
        
        # Recent activity
        metrics['recent_1h'] = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE updated_at > NOW() - INTERVAL '1 hour'"
        )
        metrics['recent_24h'] = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE updated_at > NOW() - INTERVAL '24 hours'"
        )
        
        # Platform breakdown
        metrics['uzum_products'] = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE platform='uzum'"
        )
        metrics['yandex_products'] = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE platform='yandex'"
        ) or 0
        
        await conn.close()
        return metrics
        
    except Exception as e:
        return {'error': str(e)}

def get_redis_metrics():
    """Get Redis metrics"""
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        checkpoints = {}
        for key in r.scan_iter('checkpoint:*'):
            checkpoints[key] = r.get(key)
        
        return {
            'connected': True,
            'keys': r.dbsize(),
            'checkpoints': checkpoints,
            'memory': r.info('memory').get('used_memory_human', 'N/A')
        }
    except Exception as e:
        return {'connected': False, 'error': str(e)}

def get_worker_status():
    """Get Celery worker status"""
    try:
        result = subprocess.run(
            ['celery', '-A', 'src.workers.celery_app', 'inspect', 'ping'],
            capture_output=True,
            text=True,
            timeout=5,
            cwd='/home/ubuntu/Nurgeldi/Retriever/Scrapy/app'
        )
        if 'pong' in result.stdout.lower():
            return {'status': 'online', 'workers': result.stdout.count('pong')}
        return {'status': 'offline'}
    except:
        return {'status': 'unknown'}

def get_docker_status():
    """Get Docker container status"""
    try:
        result = subprocess.run(
            ['docker-compose', 'ps', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=5,
            cwd='/home/ubuntu/Nurgeldi/Retriever/Scrapy/app'
        )
        # Simplified parsing
        containers = {}
        for line in result.stdout.split('\n'):
            if 'postgres' in line.lower():
                containers['postgres'] = 'running' if 'Up' in line or 'running' in line else 'stopped'
            if 'redis' in line.lower():
                containers['redis'] = 'running' if 'Up' in line or 'running' in line else 'stopped'
            if 'celery' in line.lower():
                containers['celery'] = 'running' if 'Up' in line or 'running' in line else 'stopped'
        return containers
    except:
        return {}

async def dashboard():
    """Main dashboard display"""
    while True:
        clear()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Header
        print(f"{C.BOLD}{C.CYAN}")
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║                    🎯 SCRAPER MONITORING DASHBOARD                           ║")
        print(f"║                         {now}                            ║")
        print("╚══════════════════════════════════════════════════════════════════════════════╝")
        print(f"{C.END}")
        
        # Get all metrics
        db = await get_db_metrics()
        redis_m = get_redis_metrics()
        workers = get_worker_status()
        docker = get_docker_status()
        
        # Row 1: Service Status
        print(f"\n{C.BOLD}📡 SERVICES{C.END}")
        print("─" * 80)
        
        services = [
            ('PostgreSQL', docker.get('postgres', 'unknown')),
            ('Redis', docker.get('redis', 'unknown')),
            ('Celery Workers', workers.get('status', 'unknown')),
        ]
        
        for name, status in services:
            if status in ['running', 'online']:
                icon = f"{C.GREEN}●{C.END}"
            elif status == 'stopped':
                icon = f"{C.RED}●{C.END}"
            else:
                icon = f"{C.YELLOW}●{C.END}"
            print(f"  {icon} {name}: {status}")
        
        # Row 2: Database Metrics
        print(f"\n{C.BOLD}📊 DATABASE{C.END}")
        print("─" * 80)
        
        if 'error' in db:
            print(f"  {C.RED}Error: {db['error']}{C.END}")
        else:
            print(f"  Size: {C.CYAN}{db.get('db_size', 'N/A')}{C.END}")
            print(f"  Updates (1h): {C.GREEN}{db.get('recent_1h', 0):,}{C.END}")
            print(f"  Updates (24h): {C.GREEN}{db.get('recent_24h', 0):,}{C.END}")
            
            print(f"\n  {C.BOLD}Table Counts:{C.END}")
            row1 = f"  Products: {db.get('products', 0):>10,}  |  SKUs: {db.get('skus', 0):>12,}  |  Sellers: {db.get('sellers', 0):>8,}"
            row2 = f"  Categories: {db.get('categories', 0):>7,}  |  Price History: {db.get('price_history', 0):>7,}"
            row3 = f"  UZEX Lots: {db.get('uzex_lots', 0):>8,}  |  UZEX Items: {db.get('uzex_items', 0):>10,}"
            print(row1)
            print(row2)
            print(row3)
            
            print(f"\n  {C.BOLD}By Platform:{C.END}")
            print(f"  Uzum: {db.get('uzum_products', 0):,}  |  Yandex: {db.get('yandex_products', 0):,}")
        
        # Row 3: Redis
        print(f"\n{C.BOLD}🔴 REDIS{C.END}")
        print("─" * 80)
        
        if not redis_m.get('connected'):
            print(f"  {C.RED}Disconnected{C.END}")
        else:
            print(f"  Memory: {redis_m.get('memory', 'N/A')}")
            print(f"  Keys: {redis_m.get('keys', 0)}")
            
            if redis_m.get('checkpoints'):
                print(f"  {C.BOLD}Checkpoints:{C.END}")
                for key, val in redis_m['checkpoints'].items():
                    print(f"    • {key}: {val}")
        
        # Row 4: Rate Calculation
        print(f"\n{C.BOLD}⚡ PERFORMANCE{C.END}")
        print("─" * 80)
        
        if 'error' not in db and db.get('recent_1h', 0) > 0:
            rate_min = db['recent_1h'] / 60
            rate_hour = db['recent_1h']
            rate_day = rate_hour * 24
            
            print(f"  Rate: {C.GREEN}{rate_min:.1f}/min{C.END} | {rate_hour:,}/hour | {rate_day:,.0f}/day (projected)")
        else:
            print(f"  {C.YELLOW}No recent activity{C.END}")
        
        # Footer
        print(f"\n{C.DIM}Refreshing every 5 seconds... Press Ctrl+C to exit{C.END}")
        
        await asyncio.sleep(5)

def main():
    try:
        asyncio.run(dashboard())
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Dashboard closed{C.END}")

if __name__ == "__main__":
    main()
