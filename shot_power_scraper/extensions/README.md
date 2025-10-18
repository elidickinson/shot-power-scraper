# Browser Extensions

This directory contains browser extensions used by shot-power-scraper.

## Directory Structure

```
extensions/
├── uBlock/                          # uBlock Origin source (gitignored)
├── ublock-lite-custom/              # Built uBlock Lite extension (committed)
├── ublock-lite-backup/              # Backup from last rebuild (gitignored)
├── shot-power-scraper-ad-blocker/   # Old ad blocker (deprecated)
├── shot-power-scraper-popup-blocker/# Popup/cookie notice blocker
├── bypass-paywalls-chrome-clean-master/ # Paywall bypass
├── custom-rules.txt                 # Your custom filter rules
├── update-ublock.sh                 # Rebuild script
└── CUSTOM_FILTERS.md                # Documentation
```

## uBlock/ Directory (Not in Git)

This directory contains the **uBlock Origin source code** used to build uBlock Lite.

**What should be here:**
```bash
git clone https://github.com/gorhill/uBlock.git
cd uBlock
git submodule update --init
```

**Why it's gitignored:**
- Large repository (~500MB with history)
- Only needed by developers rebuilding the extension
- Regular users get the pre-built `ublock-lite-custom/` extension

**If it's missing:**
The `update-ublock.sh` script will automatically clone it on first run.

## Extensions Loaded by shot-power-scraper

### Ad Blocking: `--ad-block`
Loads `ublock-lite-custom/` - uBlock Origin Lite (Manifest V3)

### Popup Blocking: `--popup-block`
Loads `shot-power-scraper-popup-blocker/` - Cookie notices, popups

### Paywall Bypass: `--paywall-block`
Loads `bypass-paywalls-chrome-clean-master/` - Paywall bypass extension

## Rebuilding uBlock Lite

```bash
# Update filter lists and rebuild
./update-ublock.sh

# Add custom rules before rebuilding
vim custom-rules.txt
./update-ublock.sh
```

The script:
1. Updates `uBlock/` source from GitHub
2. Injects your `custom-rules.txt` (if present)
3. Compiles filter lists to Declarative Net Request format
4. Backs up current `ublock-lite-custom/`
5. Installs newly built extension

## First-Time Setup

If you just cloned this repo:

**Option 1: Use pre-built extension (most users)**
```bash
# Just use it - ublock-lite-custom/ is already committed
shot-power-scraper 'https://example.com' --ad-block -o test.png
```

**Option 2: Build from source (advanced)**
```bash
# Clone uBlock source
cd shot_power_scraper/extensions
git clone https://github.com/gorhill/uBlock.git
cd uBlock
git submodule update --init

# Or just run the update script - it will clone if missing
./update-ublock.sh
```
