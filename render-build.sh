#!/usr/bin/env bash
# exit on error
set -o errexit

# Install npm dependencies
npm install

# Download matching Chrome binary to local project cache folder
export PUPPETEER_CACHE_DIR=./.puppeteer_cache
npx puppeteer browsers install chrome@146.0.7680.31
