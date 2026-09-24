#!/usr/bin/env bash
# ==============================================================================
# meta_creator — Launcher Script
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${PORT:-3070}"

echo "======================================================="
echo "  Meta Creator — Dedicated Anti-Detect Creation Engine "
echo "======================================================="
echo "[*] Directory: $DIR"
echo "[*] Dashboard: http://localhost:$PORT"

# Ensure data directory exists
mkdir -p "$DIR/data" "$DIR/profiles" "$DIR/cookies" "$DIR/screens" "$DIR/logs"

# Verify Node.js is installed
if ! command -v node >/dev/null 2>&1; then
    echo "[!] Node.js is not installed. Please install Node.js."
    exit 1
fi

# Launch dashboard server
exec node server.js
