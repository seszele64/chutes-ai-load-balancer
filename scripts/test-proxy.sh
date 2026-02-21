#!/bin/bash
#
# LiteLLM Proxy Test Script
#
# This script makes a test request to the LiteLLM proxy to verify
# it's working correctly and shows which chute was selected.
#
# Usage:
#   ./test-proxy.sh              # Run default test
#   ./test-proxy.sh --stream    # Test streaming response
#   ./test-proxy.sh --chat      # Send a custom message
#   ./test-proxy.sh --health    # Just check health
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
PORT="${LITELLM_PORT:-4000}"
HOST="${LITELLM_HOST:-0.0.0.0}"
BASE_URL="http://localhost:${PORT}"

# Load environment variables if .env exists
if [ -f ".env" ]; then
    source .env
fi

API_KEY="${LITELLM_MASTER_KEY:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

# Function to check health
check_health() {
    log_test "Checking proxy health..."
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${API_KEY}" "${BASE_URL}/health" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ]; then
        log_success "Health check passed (HTTP $HTTP_CODE)"
        
        # Try to get health details
        HEALTH_RESPONSE=$(curl -s -H "Authorization: Bearer ${API_KEY}" "${BASE_URL}/health" 2>/dev/null || echo "{}")
        if command -v python3 &> /dev/null; then
            echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
        else
            echo "$HEALTH_RESPONSE"
        fi
        return 0
    else
        log_error "Health check failed (HTTP $HTTP_CODE)"
        return 1
    fi
}

# Function to get model info
get_model_info() {
    log_test "Getting model info..."
    
    # Try the info endpoint
    RESPONSE=$(curl -s -H "Authorization: Bearer ${API_KEY}" "${BASE_URL}/info" 2>/dev/null || echo "{}")
    
    if [ -n "$RESPONSE" ]; then
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    else
        log_warn "Could not get model info"
    fi
}

# Function to make a test request
make_test_request() {
    local stream=false
    local custom_message=""
    local test_type="chat"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --stream)
                stream=true
                shift
                ;;
            --chat)
                test_type="chat"
                custom_message="${2:-}"
                shift 2
                ;;
            --health)
                check_health
                exit 0
                ;;
            *)
                shift
                ;;
        esac
    done
    
    # Check if proxy is running
    log_test "Checking if proxy is running on port $PORT..."
    if ! curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${API_KEY}" "${BASE_URL}/health" 2>/dev/null | grep -q "200"; then
        log_error "Proxy is not running on port $PORT"
        log_info "Start it with: ./run-proxy.sh"
        exit 1
    fi
    
    log_success "Proxy is running!"
    echo ""
    
    # Check health
    check_health
    echo ""
    
    # Build the request
    local messages='[
        {
            "role": "user",
            "content": "Say 'Hello from LiteLLM proxy!' and nothing else. Keep it very short."
        }
    ]'
    
    if [ -n "$custom_message" ]; then
        messages=$(cat <<EOF
[
    {
        "role": "user",
        "content": "$custom_message"
    }
]
EOF
)
    fi
    
    local request_body=$(cat <<EOF
{
    "model": "chutes-models",
    "messages": $messages,
    "temperature": 0.7,
    "max_tokens": 100
}
EOF
)
    
    # Make the request
    log_test "Sending test request to /v1/chat/completions..."
    echo ""
    
    local curl_cmd="curl -s -X POST"
    curl_cmd="$curl_cmd '${BASE_URL}/v1/chat/completions'"
    curl_cmd="$curl_cmd -H 'Content-Type: application/json'"
    
    if [ -n "$API_KEY" ]; then
        curl_cmd="$curl_cmd -H 'Authorization: Bearer ${API_KEY}'"
    fi
    
    if [ "$stream" = true ]; then
        curl_cmd="$curl_cmd -H 'Accept: text/event-stream'"
        log_test "Testing streaming response..."
    fi
    
    curl_cmd="$curl_cmd -d '${request_body}'"
    
    if [ "$stream" = true ]; then
        # Streaming response
        eval $curl_cmd | while IFS= read -r line; do
            if [[ $line == data:* ]]; then
                echo "$line" | sed 's/data: //' | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    if 'choices' in data and data['choices']:
        delta = data['choices'][0].get('delta', {})
        if 'content' in delta:
            print(delta['content'], end='', flush=True)
except:
                    pass
" 2>/dev/null || echo "$line"
            fi
        done
        echo ""
    else
        # Regular response
        response=$(eval $curl_cmd)
        
        # Pretty print the response
        if command -v python3 &> /dev/null; then
            echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        else
            echo "$response"
        fi
        
        echo ""
        
        # Extract and display relevant info
        if command -v python3 &> /dev/null; then
            log_test "Response Analysis:"
            echo "----------------------------------------"
            
            # Parse response
            id=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id', 'N/A'))" 2>/dev/null || echo "N/A")
            model=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('model', 'N/A'))" 2>/dev/null || echo "N/A")
            created=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('created', 'N/A'))" 2>/dev/null || echo "N/A")
            
            content=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:200])" 2>/dev/null || echo "N/A")
            finish_reason=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('choices', [{}])[0].get('finish_reason', 'N/A'))" 2>/dev/null || echo "N/A")
            
            usage_prompt=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('usage', {}).get('prompt_tokens', 'N/A'))" 2>/dev/null || echo "N/A")
            usage_completion=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('usage', {}).get('completion_tokens', 'N/A'))" 2>/dev/null || echo "N/A")
            usage_total=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('usage', {}).get('total_tokens', 'N/A'))" 2>/dev/null || echo "N/A")
            
            echo "  Response ID:    $id"
            echo "  Model:          $model"
            echo "  Created:        $created"
            echo "  Finish Reason:  $finish_reason"
            echo ""
            echo "  Usage:"
            echo "    Prompt Tokens:     $usage_prompt"
            echo "    Completion Tokens: $usage_completion"
            echo "    Total Tokens:      $usage_total"
            echo ""
            echo "  Content Preview:"
            echo "  $content"
            echo "----------------------------------------"
        fi
    fi
    
    # Check for errors
    if echo "$response" | grep -q '"error"'; then
        log_error "Request returned an error!"
        return 1
    else
        log_success "Test request completed!"
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --health       Only check health endpoint"
    echo "  --stream       Test streaming response"
    echo "  --chat [MSG]   Send custom message"
    echo "  -h, --help     Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                  # Run default test"
    echo "  $0 --health         # Just check if proxy is healthy"
    echo "  $0 --stream         # Test streaming"
    echo "  $0 --chat 'Hi!'     # Send custom message"
}

# Main
case "${1:-}" in
    -h|--help)
        show_usage
        exit 0
        ;;
    *)
        make_test_request "$@"
        ;;
esac
