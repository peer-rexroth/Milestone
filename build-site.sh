#!/bin/bash
# Builds the folder that gets published (Cloudflare Pages: build command ./build-site.sh, output directory dist).
# Only the app's own files go in — not tests, docs or scripts.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
rm -rf dist
mkdir dist
cp index.html sw.js manifest.json _headers dist/
# The build id is a hash of the page; the page and version.json carry the same id, and that is how an installed app knows a newer build exists.
BUILD_ID="$(shasum -a 256 index.html | cut -c1-12)"
sed -i.bak "s/__BUILD_ID__/$BUILD_ID/" dist/index.html && rm dist/index.html.bak
printf '{"id":"%s"}\n' "$BUILD_ID" > dist/version.json
cp -R icons dist/icons
cp robots.txt dist/
cp -R .well-known dist/.well-known
echo "Built dist/ ($(ls dist | wc -l | tr -d ' ') entries)"
