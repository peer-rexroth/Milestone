#!/bin/bash
# Builds the folder that gets published (Cloudflare Pages: build command ./build-site.sh, output directory dist).
# Only the app's own files go in — not tests, docs or scripts.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
rm -rf dist
mkdir dist
cp index.html sw.js manifest.json _headers dist/
cp -R icons dist/icons
echo "Built dist/ ($(ls dist | wc -l | tr -d ' ') entries)"
