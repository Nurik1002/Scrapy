#!/bin/bash
# Real-time Log Aggregator
# Tails multiple log files with color-coded output

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}==================================================================${NC}"
echo -e "${CYAN}           REAL-TIME LOG AGGREGATOR${NC}"
echo -e "${CYAN}==================================================================${NC}"
echo ""

# Create logs directory
mkdir -p logs

# Function to cleanup background jobs
cleanup() {
    echo -e "\n${YELLOW}Stopping log monitoring...${NC}"
    jobs -p | xargs -r kill 2>/dev/null
    exit 0
}

trap cleanup INT TERM

echo -e "${GREEN}Starting log monitoring...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Tail docker compose logs with color coding
docker-compose logs -f --tail=100 2>&1 | while read line; do
    if echo "$line" | grep -qi "error\|exception\|failed"; then
        echo -e "${RED}$line${NC}"
    elif echo "$line" | grep -qi "warning\|warn"; then
        echo -e "${YELLOW}$line${NC}"
    elif echo "$line" | grep -qi "success\|completed\|saved"; then
        echo -e "${GREEN}$line${NC}"
    elif echo "$line" | grep -qi "yandex"; then
        echo -e "${CYAN}$line${NC}"
    elif echo "$line" | grep -qi "uzum"; then
        echo -e "${BLUE}$line${NC}"
    elif echo "$line" | grep -qi "uzex"; then
        echo -e "${MAGENTA}$line${NC}"
    else
        echo "$line"
    fi
done
