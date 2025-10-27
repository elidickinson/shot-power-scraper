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
    if [ $CLEAN_ASSETS -eq 1 ]; then
        echo "Updating existing uBlock repository..."
        cd "$BUILD_DIR"
        git pull origin master
        git submodule update --init
    else
        echo "Using cached uBlock repository (--use-cache flag provided)..."
        cd "$BUILD_DIR"
    fi
else
    echo "Cloning uBlock repository..."
    cd "$EXTENSIONS_DIR"
    git clone https://github.com/gorhill/uBlock.git
    cd uBlock
    git submodule update --init
fi

cd "$BUILD_DIR"

# Enable desired filter lists in rulesets.json before building
echo "Configuring filter list selections..."
cp platform/mv3/rulesets.json platform/mv3/rulesets.json.backup

# Enable annoyance filters and block-lan
python3 -c "
import json
with open('platform/mv3/rulesets.json') as f:
    rulesets = json.load(f)

# List of filter IDs to enable
filters_to_enable = [
    'block-lan',
    'annoyances-cookies',
    'annoyances-overlays',
    'annoyances-widgets',
    # 'annoyances-others',  -- this blocked content on https://www.thedial.world/
    'annoyances-notifications'
]

# Enable the specified filters
for ruleset in rulesets:
    if ruleset['id'] in filters_to_enable:
        ruleset['enabled'] = True
        print(f\"Enabled: {ruleset['id']}\")

with open('platform/mv3/rulesets.json', 'w') as f:
    json.dump(rulesets, f, indent=2)
"

# Inject custom rules if they exist
CUSTOM_RULES_ENABLED=0
if [ -f "$CUSTOM_RULES" ] && [ -s "$CUSTOM_RULES" ]; then
    echo "Adding custom filter rules from $CUSTOM_RULES..."
    CUSTOM_RULES_ENABLED=1

    # Remove existing custom entry if present, then add fresh
    echo "Registering custom ruleset in rulesets.json..."

    # Use a fake HTTPS URL - we'll pre-populate the cache
    CUSTOM_URL="https://shot-power-scraper.local/custom-rules.txt"

    # Remove old entry and add fresh one
    python3 -c "
import json
with open('platform/mv3/rulesets.json') as f:
    rulesets = json.load(f)

# Remove any existing custom rules entry
rulesets = [r for r in rulesets if r.get('id') != 'shot-power-scraper-custom']

# Add custom filter list entry
rulesets.append({
    'id': 'shot-power-scraper-custom',
    'name': 'Shot Power Scraper Custom Rules',
    'group': 'default',
    'enabled': True,
    'urls': ['$CUSTOM_URL']
})

with open('platform/mv3/rulesets.json', 'w') as f:
    json.dump(rulesets, f, indent=2)
"
fi

if [ $CLEAN_ASSETS -eq 1 ]; then
    echo "Cleaning old cached assets to fetch latest filter lists..."
    make cleanassets
else
    echo "Skipping asset cleanup (--use-cache flag provided)"
fi

# Pre-populate cache with custom rules AFTER cleanassets
if [ $CUSTOM_RULES_ENABLED -eq 1 ]; then
    # The cache filename is the URL with https:// removed and / replaced with _
    mkdir -p dist/build/mv3-data
    CACHE_FILENAME="shot-power-scraper.local_custom-rules.txt"
    cp "$CUSTOM_RULES" "dist/build/mv3-data/$CACHE_FILENAME"
    echo "Custom rules cached at dist/build/mv3-data/$CACHE_FILENAME"
fi

echo "Building uBlock Lite for Chromium (this may take 2-3 minutes)..."
make mv3-chromium

# Set default filtering mode to "Complete" instead of "Optimal"
echo "Setting default filtering mode to 'Complete'..."
MODE_MANAGER="dist/build/uBOLite.chromium/js/mode-manager.js"
if [ -f "$MODE_MANAGER" ]; then
    sed -i.bak "s/optimal: \[ 'all-urls' \],/optimal: [],/" "$MODE_MANAGER"
    sed -i.bak "s/complete: \[\],/complete: [ 'all-urls' ],/" "$MODE_MANAGER"
    rm "${MODE_MANAGER}.bak"
    echo "✓ Default filtering mode set to 'Complete'"
else
    echo "Warning: Could not find mode-manager.js to set default filtering mode"
fi

# Restore original rulesets.json if we modified it
if [ -f "platform/mv3/rulesets.json.backup" ]; then
    mv platform/mv3/rulesets.json.backup platform/mv3/rulesets.json
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
