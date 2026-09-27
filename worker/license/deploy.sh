#!/usr/bin/env bash
# Deploy the licensing Worker + its signing secret in one step.
#
#   1. Sets the Worker secret LICENSE_SIGNING_KEY from .signing_key.pem
#      (the matching PUBLIC key ships in core/licenseConfig.js + license_mgr.py).
#   2. Deploys worker/license/src via wrangler.
#
# Auth (one of):
#   * wrangler login                      # browser OAuth, once
#   * export CLOUDFLARE_API_TOKEN=...     # token with Workers Scripts:Edit + Workers KV/Secrets
#
# Usage:  ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

KEY=".signing_key.pem"
if [ ! -f "$KEY" ]; then
  echo "[deploy] ERROR: $KEY not found — regenerate with:"
  echo "  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out $KEY"
  exit 1
fi

echo "[deploy] setting secret LICENSE_SIGNING_KEY (from $KEY)..."
cat "$KEY" | npx --yes wrangler secret put LICENSE_SIGNING_KEY

echo "[deploy] deploying Worker (src/index.js + src/lib/sign.js, name=nova-license)..."
npx --yes wrangler deploy

echo "[deploy] done. Sanity check:"
curl -s https://nova-license.ahasiffff.workers.dev/ || true
echo
