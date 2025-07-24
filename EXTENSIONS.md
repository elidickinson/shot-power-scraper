# Browser Extensions

shot-power-scraper includes Chrome extensions for blocking ads and popups during screenshot capture.

## Extensions

- **shot-scraper-ad-blocker**: Blocks advertisements using AdGuard Base filter lists
- **shot-scraper-popup-blocker**: Blocks cookie notices, popups, and newsletter prompts using specialized filter lists  
- **bypass-paywalls-chrome-clean-master**: Third-party extension for bypassing paywalls (automatically downloaded)

All extensions can be loaded simultaneously for comprehensive blocking.

## How They Work

Extensions use Chrome's [Declarative Net Request API](https://developer.chrome.com/docs/extensions/reference/declarativeNetRequest/) to:
- Block network requests before they load (ads, trackers, popups)
- Hide page elements via CSS injection (cosmetic blocking)
- Track and report blocked items via console logging

## Building Extensions

Extensions are auto-generated from the shared source in `extensions/blocker-shared/`:

```bash
cd extensions/blocker-shared
./build.sh
```

This downloads filter lists, converts them to Chrome's DNR format, downloads the Bypass Paywalls Clean extension, patches it to enable custom sites by default, and copies all files to create complete extension directories.

## Bypass Paywalls Clean Extension

The build script automatically downloads and patches the Bypass Paywalls Clean extension to enable all custom sites by default.

### Automatic Patching

By default, the build script modifies the extension to:
- Enable access to all websites (`*://*/*` permission) without user opt-in
- Activate custom sites (1,500+ additional news sites) automatically 
- Skip the manual opt-in process that normally requires user permission

### Build Options

```bash
# Default behavior - downloads and patches extension
./build.sh

# Skip patching - keeps original extension behavior
./build.sh --no-patch-paywall

# Force redownload and patch
./build.sh --force
```

### What Gets Patched

- **`manifest.json`**: Moves `*://*/*` from optional to required permissions
- **`background.js`**: Sets `customOptIn: true` in storage defaults

Backup files (`.backup`) are created before patching. The patched extension provides full paywall bypass coverage (2,400+ sites) without requiring manual user configuration.

## Custom Filter Rules

You can add your own blocking rules without modifying downloaded filter lists:

### Custom Files
- **`custom-ad-block-filters.txt`** - Your custom ad blocking rules
- **`custom-popup-block-filters.txt`** - Your custom popup/cookie blocking rules

### Adding Rules
Edit the custom files directly in `extensions/blocker-shared/`:

```bash
cd extensions/blocker-shared
# Add custom ad blocking rules
echo "||annoying-ads.example.com^" >> custom-ad-block-filters.txt

# Add custom popup blocking rules  
echo "example.com##div[class*='newsletter-popup']" >> custom-popup-block-filters.txt

# Rebuild extensions to apply changes
./build.sh
```

### Rule Syntax
Custom filter files support standard [Adblock Plus filter syntax](https://adblockplus.org/filter-cheatsheet):
- **Network rules**: `||domain.com^` blocks network requests
- **Cosmetic rules**: `example.com##.selector` hides page elements
- **Comments**: Lines starting with `!` are ignored

Custom rules are processed alongside downloaded filter lists during the build process.

## Supported Rule Types

### Network Blocking Rules
All standard ABP network rules are supported via Chrome's Declarative Net Request API:
- **Block requests**: `||ads.example.com^`
- **Block specific paths**: `||example.com/ads/*`
- **Domain exceptions**: `@@||example.com^$domain=trusted.com`
- **Resource type filtering**: `||tracker.com^$script,image`
- **Third-party blocking**: `||analytics.com^$third-party`

### Cosmetic Rules (Element Hiding)
**✅ Supported (Common in Filter Lists):**
- **Basic element hiding**: `example.com##.ad-banner`
- **Universal hiding**: `##.popup`
- **Element unhiding**: `example.com#@#.content` 
- **ID selectors**: `##div[id="newsletter"]`
- **Class selectors**: `##div[class*="popup"]`
- **Attribute selectors**: `##div[data-ad="true"]`
- **CSS combinators**: `##.container > .ad`
- **Complex :not() selectors**: `##.cookiebar:not(body):not(html)`
- **Long domain exclusion lists**: `~domain1.com,~domain2.com##.banner`
- **Selectors up to 1000 characters**

**❌ Not Supported (Advanced ABP/uBlock Features):**
- **Element removal**: `##selector:remove()` and `##selector { remove: true; }`
- **Text matching**: `##div:has-text("Advertisement")`
- **CSS property matching**: `##div:matches-css(display: block)`
- **CSS injection**: `##selector:style(display: block !important)`
- **XPath selectors**: `##xpath(//div[@class="ad"])`
- **Shadow DOM**: `##div >>> .shadow-ad`

### JavaScript Injection Rules
**✅ Supported functions:**
- **Remove class**: `example.com##+js(rc, class-name)`
- **Set property**: `example.com##+js(set, window.ads, false)`
- **Disable eval**: `example.com##+js(noeval)`

**❌ Not Supported:**
- Most other uBlock Origin scriptlets
- Custom JavaScript code execution
- Complex DOM manipulation functions

### Rule Processing Notes
- Rules are validated and processed at build time, not runtime
- Invalid rules are automatically filtered out and reported
- Selectors over 1000 characters are rejected for performance
- JavaScript injection is limited to safe, predefined functions
- **Coverage**: ~98% of cosmetic rules in analyzed filter lists are supported
- **Unsupported rules**: Primarily uBlock Origin element removal and procedural cosmetic features

## Architecture

- **Shared Source**: `extensions/blocker-shared/` contains all common code
- **Generated Extensions**: `extensions/shot-scraper-{ad,popup}-blocker/` are build artifacts
- **Third-party Extension**: `extensions/bypass-paywalls-chrome-clean-master/` downloaded from external source
- **Filter Lists**: Downloaded from AdGuard, EasyList, and other sources
- **Build Script**: `build.sh` handles downloading, conversion, and file copying

## Usage

Extensions load automatically when using blocking flags:

```bash
# Use individual blocking options
shot-power-scraper example.com --ad-block -o output.png
shot-power-scraper example.com --popup-block -o output.png  
shot-power-scraper example.com --paywall-block -o output.png

# Combine multiple blocking options
shot-power-scraper example.com --ad-block --popup-block --paywall-block -o output.png
```

Chrome loads extensions via `--load-extension` flag with required permission bypass.

## Files

Each generated extension contains:
- `manifest.json` - Extension configuration  
- `background.js` - Service worker with blocking logic and console logging
- `content.js` - Content script for cosmetic blocking
- `content.css` - CSS styles for content script
- `network-rules.json` - Network blocking rules (DNR format)
- `cosmetic-rules.json` - CSS hiding rules
- `popup.html` & `popup.js` - Extension popup interface

Each built extension contains only its specific rule files:
- **Ad Blocker**: `network-rules.json` (from `ad-block-rules.json`), `cosmetic-rules.json` (from `cosmetic-ad-block-rules.json`)
- **Popup Blocker**: `network-rules.json` (from `popup-block-rules.json`), `cosmetic-rules.json` (from `cosmetic-popup-block-rules.json`)

The paywall bypass extension is different:
- **Bypass Paywalls Clean**: Third-party extension automatically downloaded and patched
- Downloaded and patched during build process to enable custom sites by default
- Uses its own manifest.json and rule files

**Note**: Files in generated extension directories should not be edited directly - they're overwritten on each build. The paywall extension is automatically patched during the build process to enable all features by default.