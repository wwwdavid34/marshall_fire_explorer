#!/usr/bin/env bash
set -euo pipefail

echo "→ Pushing results to R2..."
aws s3 sync data/results/ s3://dm-prod-data/results/ \
    --endpoint-url "https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com" \
    --delete

echo "→ Building frontend..."
cd frontend && npm ci && npm run build && cd ..

echo "→ Deploying to Cloudflare Pages..."
npx wrangler pages deploy frontend/dist \
    --project-name marshall-fire \
    --commit-dirty=true

echo "✓ Live at https://marshallfire.yourdomain.com"
