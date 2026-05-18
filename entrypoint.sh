#!/bin/bash
set -e

echo "========================================="
echo " WhatsApp MCP Server - Docker Container"
echo "========================================="

# Start the Go WhatsApp bridge in the background
echo "[1/2] Starting WhatsApp Bridge..."
cd /app/whatsapp-bridge
./whatsapp-bridge &
BRIDGE_PID=$!

# Wait for the bridge REST API to become available
echo "[1/2] Waiting for bridge API to be ready..."
RETRIES=0
MAX_RETRIES=30
until curl -s http://localhost:8080/api/send > /dev/null 2>&1 || [ $RETRIES -eq $MAX_RETRIES ]; do
    RETRIES=$((RETRIES + 1))
    sleep 2
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    echo "[WARN] Bridge API health check timed out. Continuing anyway (bridge may still be waiting for QR scan)..."
fi

echo "[2/2] Starting Python MCP Server..."
cd /app/whatsapp-mcp-server
uv run main.py &
MCP_PID=$!

echo "========================================="
echo " Both services are running!"
echo " Bridge PID: $BRIDGE_PID"
echo " MCP Server PID: $MCP_PID"
echo "========================================="

# Trap signals for graceful shutdown
cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $MCP_PID 2>/dev/null || true
    kill $BRIDGE_PID 2>/dev/null || true
    wait $BRIDGE_PID 2>/dev/null || true
    wait $MCP_PID 2>/dev/null || true
    echo "All services stopped."
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for either process to exit
wait -n $BRIDGE_PID $MCP_PID
EXIT_CODE=$?

echo "A service exited with code $EXIT_CODE. Shutting down..."
cleanup
