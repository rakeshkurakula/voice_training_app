#!/bin/bash

# run.sh - VoiceCoach application controller with PID file management
# Usage: ./run.sh [start|stop|status|restart]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="/tmp/voicecoach.pid"
APP_SCRIPT="${SCRIPT_DIR}/main.py"
LOG_FILE="${SCRIPT_DIR}/logs/app.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure logs directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Cleanup function to remove PID file on exit
cleanup() {
    if [[ -f "$PID_FILE" ]]; then
        echo -e "${YELLOW}Cleaning up PID file...${NC}"
        rm -f "$PID_FILE"
    fi
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Function to check if process is running
is_running() {
    if [[ ! -f "$PID_FILE" ]]; then
        return 1
    fi
    
    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
    
    if [[ -z "$pid" ]]; then
        return 1
    fi
    
    # Check if process is actually running
    if ps -p "$pid" > /dev/null 2>&1; then
        return 0
    else
        # PID file exists but process is not running, clean it up
        echo -e "${YELLOW}Stale PID file found, removing...${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to start the application
start_app() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE")
        echo -e "${YELLOW}VoiceCoach is already running with PID $pid${NC}"
        return 0
    fi
    
    echo -e "${BLUE}Starting VoiceCoach...${NC}"
    
    # Check if main.py exists
    if [[ ! -f "$APP_SCRIPT" ]]; then
        echo -e "${RED}Error: $APP_SCRIPT not found${NC}"
        exit 1
    fi
    
    # Start the application in background
    nohup python "$APP_SCRIPT" >> "$LOG_FILE" 2>&1 &
    local pid=$!
    
    # Write PID to file
    echo "$pid" > "$PID_FILE"
    
    # Give the process a moment to start
    sleep 2
    
    # Verify it's still running
    if is_running; then
        echo -e "${GREEN}VoiceCoach started successfully with PID $pid${NC}"
        echo -e "${BLUE}Logs: tail -f $LOG_FILE${NC}"
    else
        echo -e "${RED}Failed to start VoiceCoach${NC}"
        echo -e "${BLUE}Check logs: $LOG_FILE${NC}"
        exit 1
    fi
}

# Function to stop the application
stop_app() {
    if ! is_running; then
        echo -e "${YELLOW}VoiceCoach is not running${NC}"
        return 0
    fi
    
    local pid
    pid=$(cat "$PID_FILE")
    
    echo -e "${BLUE}Stopping VoiceCoach (PID: $pid)...${NC}"
    
    # Try graceful termination first
    if kill "$pid" 2>/dev/null; then
        # Wait up to 10 seconds for graceful shutdown
        local count=0
        while [[ $count -lt 10 ]] && ps -p "$pid" > /dev/null 2>&1; do
            sleep 1
            ((count++))
        done
        
        # If still running, force kill
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}Graceful shutdown failed, forcing termination...${NC}"
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi
    
    # Clean up PID file
    rm -f "$PID_FILE"
    
    echo -e "${GREEN}VoiceCoach stopped${NC}"
}

# Function to show application status
show_status() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE")
        echo -e "${GREEN}VoiceCoach is running${NC}"
        echo -e "${BLUE}PID: $pid${NC}"
        echo -e "${BLUE}PID file: $PID_FILE${NC}"
        echo -e "${BLUE}Log file: $LOG_FILE${NC}"
        
        # Show process info if available
        if command -v ps >/dev/null 2>&1; then
            echo -e "${BLUE}Process info:${NC}"
            ps -p "$pid" -o pid,ppid,etime,pcpu,pmem,command 2>/dev/null || true
        fi
    else
        echo -e "${RED}VoiceCoach is not running${NC}"
        if [[ -f "$PID_FILE" ]]; then
            echo -e "${YELLOW}Warning: PID file exists but process is not running${NC}"
        fi
    fi
}

# Function to restart the application
restart_app() {
    echo -e "${BLUE}Restarting VoiceCoach...${NC}"
    stop_app
    sleep 1
    start_app
}

# Main script logic
case "${1:-}" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    status)
        show_status
        ;;
    restart)
        restart_app
        ;;
    "")
        # Default to start if no argument provided
        start_app
        ;;
    *)
        echo -e "${RED}Usage: $0 {start|stop|status|restart}${NC}"
        echo ""
        echo "Commands:"
        echo "  start    - Start VoiceCoach application"
        echo "  stop     - Stop VoiceCoach application"
        echo "  status   - Show application status"
        echo "  restart  - Restart VoiceCoach application"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 stop"
        echo "  $0 status"
        echo "  $0 restart"
        exit 1
        ;;
esac
