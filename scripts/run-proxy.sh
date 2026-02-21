#!/bin/bash
#
# LiteLLM Proxy Startup Script
# 
# This script starts the LiteLLM proxy server with Chutes routing.
# It loads environment variables and runs the proxy in the background.
#
# Usage:
#   ./run-proxy.sh          # Start proxy on default port 4000
#   ./run-proxy.sh 4001     # Start proxy on custom port
#   ./run-proxy.sh stop    # Stop the running proxy
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
PORT="${1:-${LITELLM_PORT:-4000}}"
HOST="${LITELLM_HOST:-0.0.0.0}"
PID_FILE="/tmp/litellm-proxy.pid"
LOG_FILE="/tmp/litellm-proxy.log"
CONFIG_PATH="${LITELLM_CONFIG_PATH:-../litellm-config.yaml}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to stop the proxy
stop_proxy() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            log_info "Stopping LiteLLM proxy (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
            sleep 2
            # Force kill if still running
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null || true
            fi
            rm -f "$PID_FILE"
            log_info "Proxy stopped."
        else
            log_warn "Proxy process not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        log_warn "No PID file found. Is the proxy running?"
        # Try to find and kill any litellm process
        PIDS=$(pgrep -f "start_litellm.py" 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            log_info "Found running LiteLLM processes: $PIDS"
            echo "$PIDS" | xargs kill 2>/dev/null || true
            log_info "Processes killed."
        fi
    fi
}

# Function to check if proxy is ready
wait_for_proxy() {
    local max_attempts=30
    local attempt=1
    
    log_info "Waiting for proxy to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:${PORT}/health" 2>/dev/null | grep -q "200"; then
            log_info "Proxy is ready!"
            return 0
        fi
        
        # Also try the root endpoint
        if curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:${PORT}/" 2>/dev/null | grep -q "200"; then
            log_info "Proxy is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    log_error "Proxy failed to start within ${max_attempts} seconds"
    return 1
}

# Main command handling
case "${1:-}" in
    stop)
        stop_proxy
        exit 0
        ;;
    restart)
        stop_proxy
        shift
        exec "$0" "$@"
        ;;
    -h|--help)
        echo "Usage: $0 [PORT|stop|restart]"
        echo ""
        echo "Commands:"
        echo "  (none)     Start proxy on default port 4000"
        echo "  PORT       Start proxy on specified port"
        echo "  stop       Stop the running proxy"
        echo "  restart    Restart the proxy"
        echo "  -h, --help Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  LITELLM_PORT      Port to run proxy on (default: 4000)"
        echo "  LITELLM_HOST      Host to bind to (default: 0.0.0.0)"
        echo "  LITELLM_CONFIG_PATH  Path to config file"
        exit 0
        ;;
esac

# Check for .env file in project root
if [ -f "../.env" ]; then
    log_info "Loading environment from ../.env..."
    set -a
    source ../.env
    set +a
else
    log_warn ".env file not found in project root. Using existing environment variables."
fi

# Validate required environment variables
if [ -z "$CHUTES_API_KEY" ]; then
    log_error "CHUTES_API_KEY is not set. Please add it to .env or export it."
    exit 1
fi

if [ -z "$LITELLM_MASTER_KEY" ]; then
    log_warn "LITELLM_MASTER_KEY is not set. The proxy will not be secured!"
fi

# Check if proxy is already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        log_error "Proxy is already running on port $PORT (PID: $PID)"
        log_error "Use '$0 stop' to stop it first"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# Check if port is in use
if netstat -tuln 2>/dev/null | grep -q ":${PORT} " || ss -tuln 2>/dev/null | grep -q ":${PORT} "; then
    log_error "Port $PORT is already in use"
    exit 1
fi

log_info "Starting LiteLLM proxy on ${HOST}:${PORT}..."
log_info "Log file: $LOG_FILE"

# Start the proxy in the background
python3 ../start_litellm.py --port "$PORT" --host "$HOST" --config "$CONFIG_PATH" > "$LOG_FILE" 2>&1 &
PROXY_PID=$!

# Save PID
echo "$PROXY_PID" > "$PID_FILE"

log_info "Proxy started with PID: $PROXY_PID"

# Wait for proxy to be ready
if wait_for_proxy; then
    echo ""
    log_info "========================================"
    log_info "LiteLLM Proxy is now running!"
    log_info "========================================"
    echo ""
    echo "  Local:    http://localhost:${PORT}"
    echo "  Network:  http://${HOST}:${PORT}"
    echo ""
    echo "  Health:   http://localhost:${PORT}/health"
    echo "  Docs:     http://localhost:${PORT}/"
    echo ""
    if [ -n "$LITELLM_MASTER_KEY" ]; then
        echo "  API Key:  Use 'Authorization: Bearer ${LITELLM_MASTER_KEY}' header"
    fi
    echo ""
    echo "Log file: $LOG_FILE"
    echo "PID file: $PID_FILE"
    echo ""
    echo "To stop: $0 stop"
else
    log_error "Failed to start proxy. Check log: $LOG_FILE"
    echo ""
    echo "Last 20 lines of log:"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
