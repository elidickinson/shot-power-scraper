#!/bin/bash
set -e

# Default to cleaning assets
CLEAN_ASSETS=1

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --use-cache)
            CLEAN_ASSETS=0
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

EXTENSIONS_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$EXTENSIONS_DIR/uBlock"
CUSTOM_RULES="$EXTENSIONS_DIR/ad-block-custom-rules.txt"

echo "Updating uBlock Lite with latest filter lists..."

# Check if we already have the repo cloned
if [ -d "$BUILD_DIR" ]; then
    echo "Updating existing uBlock repository..."
    cd "$BUILD_DIR"
    git pull origin master
    git submodule update --init
else
    echo "Cloning uBlock repository..."
    cd "$EXTENSIONS_DIR"
    git clone https://github.com/gorhill/uBlock.git
    cd uBlock
    git submodule update --init
fi

cd "$BUILD_DIR"

# Inject custom rules if they exist
if [ -f "$CUSTOM_RULES" ] && [ -s "$CUSTOM_RULES" ]; then
    echo "Adding custom filter rules from $CUSTOM_RULES..."

    # Add custom rules to assets.json if not already there
    if ! grep -q "shot-power-scraper-custom" assets/assets.json; then
        echo "Registering custom ruleset in assets.json..."
        # Create backup
        cp assets/assets.json assets/assets.json.backup

        # Add our custom list entry (insert before the closing brace of contentFiltering)
        python3 -c "
import json
with open('assets/assets.json') as f:
    assets = json.load(f)

# Add custom filter list
assets['shot-power-scraper-custom'] = {
    'content': 'filters',
    'contentURL': [
        'file://$CUSTOM_RULES'
    ],
    'title': 'Shot Power Scraper Custom Rules'
}

with open('assets/assets.json', 'w') as f:
    json.dump(assets, f, indent=2)
"
    fi

    # Copy custom rules to a location uBlock can access during build
    mkdir -p dist/filters
    cp "$CUSTOM_RULES" dist/filters/custom-rules.txt

    # Update the path in assets.json to use the copied file
    sed -i.bak "s|file://$CUSTOM_RULES|file://$(pwd)/dist/filters/custom-rules.txt|g" assets/assets.json
fi

if [ $CLEAN_ASSETS -eq 1 ]; then
    echo "Cleaning old cached assets to fetch latest filter lists..."
    make cleanassets
else
    echo "Skipping asset cleanup (--use-cache flag provided)"
fi

echo "Building uBlock Lite for Chromium (this may take 2-3 minutes)..."
make mv3-chromium

# Restore original assets.json if we modified it
if [ -f "assets/assets.json.backup" ]; then
    mv assets/assets.json.backup assets/assets.json
fi

echo "Backing up current version..."
[ -d "$EXTENSIONS_DIR/ublock-lite-backup" ] && rm -rf "$EXTENSIONS_DIR/ublock-lite-backup"
[ -d "$EXTENSIONS_DIR/ublock-lite-custom" ] && mv "$EXTENSIONS_DIR/ublock-lite-custom" "$EXTENSIONS_DIR/ublock-lite-backup"

echo "Installing new version..."
cp -r "$BUILD_DIR/dist/build/uBOLite.chromium" "$EXTENSIONS_DIR/ublock-lite-custom"

NEW_VERSION=$(grep '"version"' "$EXTENSIONS_DIR/ublock-lite-custom/manifest.json" | cut -d'"' -f4)
echo "✓ Updated to version $NEW_VERSION with latest filter lists"

if [ -f "$CUSTOM_RULES" ] && [ -s "$CUSTOM_RULES" ]; then
    echo "✓ Custom rules from ad-block-custom-rules.txt included"
fi
