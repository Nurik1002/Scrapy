#!/usr/bin/env python3
"""
Celery Worker Real-time Monitor
Displays active tasks, worker status, and queue health
"""

import os
import sys
import time
import subprocess
from datetime import datetime

# ANSI Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def run_celery_command(command):
    """Run a celery inspect command"""
    try:
        result = subprocess.run(
            f"celery -A src.workers.celery_app inspect {command}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def get_worker_stats():
    """Get worker statistics"""
    stats = run_celery_command("stats")
    active = run_celery_command("active")
    scheduled = run_celery_command("scheduled")
    registered = run_celery_command("registered")
    
    return {
        'stats': stats,
        'active': active,
        'scheduled': scheduled,
        'registered': registered
    }

def monitor_loop():
    """Main monitoring loop"""
    while True:
        clear_screen()
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*100}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'🔧 CELERY WORKER MONITOR'.center(100)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{datetime.now().strftime('%Y-%m-%d %H:%M:%S').center(100)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*100}{Colors.END}\n")
        
        data = get_worker_stats()
        
        # Active Tasks
        print(f"{Colors.BOLD}⚡ ACTIVE TASKS{Colors.END}")
        print("─" * 100)
        if "empty" in data['active'].lower() or not data['active'].strip():
            print(f"{Colors.YELLOW}  No active tasks{Colors.END}")
        else:
            print(data['active'])
        
       # Scheduled Tasks
        print(f"\n{Colors.BOLD}📅 SCHEDULED TASKS{Colors.END}")
        print("─" * 100)
        if "empty" in data['scheduled'].lower() or not data['scheduled'].strip():
            print(f"{Colors.GREEN}  No scheduled tasks{Colors.END}")
        else:
            print(data['scheduled'])
        
        # Worker Stats
        print(f"\n{Colors.BOLD}📊 WORKER STATISTICS{Colors.END}")
        print("─" * 100)
        if "Error" in data['stats']:
            print(f"{Colors.RED}  {data['stats']}{Colors.END}")
        else:
            print(data['stats'])
        
        # Registered Tasks
        print(f"\n{Colors.BOLD}📋 REGISTERED TASKS{Colors.END}")
        print("─" * 100)
        if data['registered']:
            # Extract task names
            lines = data['registered'].split('\n')
            for line in lines:
                if 'src.' in line:
                    print(f"{Colors.GREEN}  • {line.strip()}{Colors.END}")
        
        print(f"\n{Colors.BOLD}Press Ctrl+C to exit{Colors.END}")
        print("Refreshing in 5 seconds...")
        
        time.sleep(5)

def main():
    try:
        monitor_loop()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Worker monitor stopped{Colors.END}")
    except Exception as e:
        print(f"\n\n{Colors.RED}Fatal error: {e}{Colors.END}")
        sys.exit(1)

if __name__ == "__main__":
    main()
