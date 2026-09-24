#!/usr/bin/env bash
# ==============================================================================
# meta_creator — Launcher Script
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Port 3070 is also used by the Windows VM's QEMU host-forward. Keep 3070 as
# the normal default, but automatically move the native Linux dashboard when
# that port belongs to another listener (or is already a live Meta Creator).
port_in_use() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -H -ltn "sport = :$port" 2>/dev/null | grep -q .
        return $?
    fi
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    fi
    return 1
}

meta_creator_responding() {
    local port="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS --max-time 1 "http://127.0.0.1:$port/api/meta-insta/status" >/dev/null 2>&1
        return $?
    fi
    return 1
}

if [ -n "${PORT:-}" ]; then
    :
else
    PORT=3070
    if port_in_use "$PORT"; then
        if meta_creator_responding "$PORT"; then
            echo "[*] Meta Creator is already running at http://localhost:$PORT"
            exit 0
        fi
        PORT=3080
        while port_in_use "$PORT"; do
            if meta_creator_responding "$PORT"; then
                echo "[*] Meta Creator is already running at http://localhost:$PORT"
                exit 0
            fi
            PORT=$((PORT + 1))
        done
        echo "[!] Port 3070 is occupied by another listener (often the Windows VM/QEMU forward); using $PORT."
    fi
fi
export PORT

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
