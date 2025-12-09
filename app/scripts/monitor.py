#!/usr/bin/env python3
"""
Real-time Multi-Platform Scraper Monitor
Terminal-based monitoring for Uzum, Yandex, OLX, and UZEX scrapers
"""

import asyncio
import asyncpg
import redis
import os
import sys
from datetime import datetime,timedelta
from collections import defaultdict
import time

# ANSI Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def print_header(title):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")

async def get_db_stats():
    """Get database statistics"""
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5434)),
        'user': os.getenv('DB_USER', 'scraper'),
        'password': os.getenv('DB_PASSWORD', 'scraper123'),
        'database': os.getenv('DB_NAME', 'uzum_scraping')
    }
    
    try:
        conn = await asyncpg.connect(**db_config)
        
        # Table counts
        tables = {}
       
        # Uzum tables
        tables['products'] = await conn.fetchval("SELECT COUNT(*) FROM products WHERE platform='uzum'")
        tables['skus'] = await conn.fetchval("SELECT COUNT(*) FROM skus")
        tables['sellers'] = await conn.fetchval("SELECT COUNT(*) FROM sellers WHERE platform='uzum'")
        tables['categories'] = await conn.fetchval("SELECT COUNT(*) FROM categories WHERE platform='uzum'")
        tables['price_history'] = await conn.fetchval("SELECT COUNT(*) FROM price_history")
        
        # UZEX tables
        tables['uzex_lots'] = await conn.fetchval("SELECT COUNT(*) FROM uzex_lots")
        tables['uzex_items'] = await conn.fetchval("SELECT COUNT(*) FROM uzex_lot_items")
        
        # Database size
        db_size = await conn.fetchval("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """)
        
        # Recent activity (last hour)
        recent = await conn.fetch("""
            SELECT 
                COUNT(*) as count,
                MAX(updated_at) as last_update
            FROM products 
            WHERE updated_at > NOW() - INTERVAL '1 hour'
        """)
        
        await conn.close()
        
        return {
            'tables': tables,
            'db_size': db_size,
            'recent_updates': recent[0]['count'] if recent else 0,
            'last_update': recent[0]['last_update'] if recent else None
        }
    except Exception as e:
        return {'error': str(e)}

def get_redis_stats():
    """Get Redis checkpoint statistics"""
    try:
        r = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )
        
        # Get all checkpoint keys
        checkpoints = {}
        for key in r.scan_iter('checkpoint:*'):
            checkpoints[key] = r.get(key)
        
        return {
            'connected': True,
            'checkpoints': checkpoints,
            'keys_count': r.dbsize()
        }
    except Exception as e:
        return {'connected': False, 'error': str(e)}

async def monitor_loop():
    """Main monitoring loop"""
    while True:
        clear_screen()
        print_header(f"🔍 Scraper Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Database Stats
        print(f"{Colors.BOLD}📊 DATABASE STATISTICS{Colors.END}")
        print("─" * 80)
        
        db_stats = await get_db_stats()
        if 'error' in db_stats:
            print(f"{Colors.RED}❌ Database Error: {db_stats['error']}{Colors.END}")
        else:
            print(f"{Colors.GREEN}Database Size:{Colors.END} {db_stats['db_size']}")
            print(f"{Colors.GREEN}Recent Updates:{Colors.END} {db_stats['recent_updates']} in last hour")
            if db_stats['last_update']:
                print(f"{Colors.GREEN}Last Update:{Colors.END} {db_stats['last_update']}")
            
            print(f"\n{Colors.BOLD}Table Counts:{Colors.END}")
            for table, count in db_stats['tables'].items():
                formatted_count = f"{count:,}"
                print(f"  • {table:<20} {formatted_count:>15}")
        
        # Redis Stats
        print(f"\n{Colors.BOLD}🔴 REDIS CHECKPOINTS{Colors.END}")
        print("─" * 80)
        
        redis_stats = get_redis_stats()
        if not redis_stats['connected']:
            print(f"{Colors.RED}❌ Redis Error: {redis_stats.get('error', 'Unknown')}{Colors.END}")
        else:
            print(f"{Colors.GREEN}Status:{Colors.END} Connected")
            print(f"{Colors.GREEN}Total Keys:{Colors.END} {redis_stats['keys_count']}")
            
            if redis_stats['checkpoints']:
                print(f"\n{Colors.BOLD}Active Checkpoints:{Colors.END}")
                for key, value in redis_stats['checkpoints'].items():
                    platform = key.split(':')[1] if ':' in key else 'unknown'
                    print(f"  • {platform:<15} {value}")
            else:
                print(f"{Colors.YELLOW}  No active checkpoints{Colors.END}")
        
        # Scraper Status (from rate calculations)
        print(f"\n{Colors.BOLD}⚡ SCRAPER PERFORMANCE{Colors.END}")
        print("─" * 80)
        
        if 'error' not in db_stats and db_stats['recent_updates'] > 0:
            rate = db_stats['recent_updates'] / 60  # per minute
            print(f"{Colors.GREEN}Current Rate:{Colors.END} {rate:.1f} products/min")
            print(f"{Colors.GREEN}Projected Hour:{Colors.END} {rate * 60:.0f} products")
            print(f"{Colors.GREEN}Projected Day:{Colors.END} {rate * 60 * 24:,.0f} products")
        else:
            print(f"{Colors.YELLOW}No recent activity{Colors.END}")
        
        print(f"\n{Colors.BOLD}Press Ctrl+C to exit{Colors.END}")
        print("Refreshing in 5 seconds...")
        
        await asyncio.sleep(5)

async def main():
    try:
        await monitor_loop()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Monitor stopped by user{Colors.END}")
    except Exception as e:
        print(f"\n\n{Colors.RED}Fatal error: {e}{Colors.END}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
