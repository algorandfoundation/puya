#!/bin/bash

# Function to display usage information
function show_usage {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -i, --interval SECONDS   Monitoring interval in seconds (default: 1)"
    echo "  -v, --verbose            Show more detailed thread info"
    echo "  -h, --help               Show this help message"
    exit 1
}

# Default values
INTERVAL=1
VERBOSE=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Function to find the PID of the Puya daemon
function find_puya_pid {
    ps aux | grep -i "puya.*daemon" | grep -v grep | awk '{print $2}' | head -1
}

# Function to get detailed thread info using spindump
function get_thread_details {
    local PID=$1
    if [[ $VERBOSE -eq 1 ]]; then
        echo "Detailed thread information (first 10 lines):"
        sudo spindump $PID -stdout | grep -A 10 "Thread"
    fi
}

# Main monitoring loop
echo "Starting Puya daemon thread monitor..."
echo "Press Ctrl+C to stop monitoring"
echo ""

PID=$(find_puya_pid)
if [[ -z "$PID" ]]; then
    echo "No Puya daemon process found. Is it running?"
    exit 1
fi

echo "Monitoring Puya daemon process with PID $PID"
echo "Time       | Threads | CPU%"
echo "-----------+---------+------"

while true; do
    # Get thread count using ps
    THREAD_COUNT=$(ps -M $PID 2>/dev/null | wc -l)
    THREAD_COUNT=$((THREAD_COUNT-1))  # Subtract header line
    
    # Get CPU usage
    CPU_USAGE=$(ps -p $PID -o %cpu | tail -1 | tr -d ' ')
    
    # Format current time
    CURRENT_TIME=$(date +"%H:%M:%S")
    
    # Print the information
    printf "%-10s | %-7s | %-5s\n" "$CURRENT_TIME" "$THREAD_COUNT" "$CPU_USAGE"
    
    # Get detailed thread info if verbose mode is enabled
    if [[ $VERBOSE -eq 1 && $((SECONDS % 5)) -eq 0 ]]; then
        get_thread_details $PID
    fi
    
    # Check if the process is still running
    if ! ps -p $PID > /dev/null; then
        echo "Puya daemon process with PID $PID is no longer running. Exiting."
        exit 0
    fi
    
    # Sleep for the specified interval
    sleep $INTERVAL
done 
