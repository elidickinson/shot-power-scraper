#!/bin/bash
set -e

EXTENSIONS_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMP_BUILD_DIR="/tmp/uBlock"

echo "Updating uBlock Lite with latest filter lists..."

# Check if we already have the repo cloned
if [ -d "$TEMP_BUILD_DIR" ]; then
    echo "Updating existing uBlock repository..."
    cd "$TEMP_BUILD_DIR"
    git pull origin master
    git submodule update --init
else
    echo "Cloning uBlock repository..."
    cd /tmp
    git clone https://github.com/gorhill/uBlock.git
    cd uBlock
    git submodule update --init
fi

echo "Cleaning old cached assets to fetch latest filter lists..."
cd "$TEMP_BUILD_DIR"
make cleanassets

echo "Building uBlock Lite for Chromium (this may take 2-3 minutes)..."
make mv3-chromium

echo "Backing up current version..."
[ -d "$EXTENSIONS_DIR/ublock-lite-backup" ] && rm -rf "$EXTENSIONS_DIR/ublock-lite-backup"
[ -d "$EXTENSIONS_DIR/ublock-lite-custom" ] && mv "$EXTENSIONS_DIR/ublock-lite-custom" "$EXTENSIONS_DIR/ublock-lite-backup"

echo "Installing new version..."
cp -r "$TEMP_BUILD_DIR/dist/build/uBOLite.chromium" "$EXTENSIONS_DIR/ublock-lite-custom"

NEW_VERSION=$(grep '"version"' "$EXTENSIONS_DIR/ublock-lite-custom/manifest.json" | cut -d'"' -f4)
echo "✓ Updated to version $NEW_VERSION with latest filter lists"
