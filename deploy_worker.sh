#!/usr/bin/env bash
# ==============================================================================
#  Meta Creator — Cloudflare Worker Build & Deploy Script
#  Deploys the D1 Licensing & Ledger Authority to https://nova-license.ahasiffff.workers.dev
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$SCRIPT_DIR/worker/license"

echo "===================================================================="
echo "  Deploying Cloudflare Licensing Worker (nova-license)"
echo "===================================================================="
echo ""

cd "$WORKER_DIR"

# 1. Build single-file bundle from src/* modules
echo "[*] Step 1: Compiling src/* modules into dist/worker.js..."
node scripts/build-worker.js

echo ""
echo "[*] Step 2: Deploying to Cloudflare Workers via Wrangler..."
npx --yes wrangler deploy

echo ""
echo "[✅] Deployment complete!"
echo "     Worker URL: https://nova-license.ahasiffff.workers.dev"
echo "     Admin UI:   https://nova-license.ahasiffff.workers.dev/admin"
echo "===================================================================="
