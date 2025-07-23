# Browser Extensions

shot-power-scraper includes Chrome extensions for blocking ads and popups during screenshot capture.

## Extensions

- **shot-scraper-ad-blocker**: Blocks advertisements using AdGuard Base filter lists
- **shot-scraper-popup-blocker**: Blocks cookie notices, popups, and newsletter prompts using specialized filter lists

Both extensions can be loaded simultaneously for comprehensive blocking.

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

This downloads filter lists, converts them to Chrome's DNR format, and copies all files to create complete extension directories.

## Architecture

- **Shared Source**: `extensions/blocker-shared/` contains all common code
- **Generated Extensions**: `extensions/shot-scraper-{ad,popup}-blocker/` are build artifacts
- **Filter Lists**: Downloaded from AdGuard, EasyList, and other sources
- **Build Script**: `build.sh` handles downloading, conversion, and file copying

## Usage

Extensions load automatically when using `--ad-block` or `--popup-block` flags:

```bash
shot-power-scraper example.com --ad-block --popup-block -o output.png
```

Chrome loads extensions via `--load-extension` flag with required permission bypass.

## Files

Each generated extension contains:
- `manifest.json` - Extension configuration  
- `background.js` - Service worker with blocking logic and console logging
- `content.js` - Content script for cosmetic blocking
- `content.css` - CSS styles for content script
- `rules.json` - Network blocking rules specific to extension type (DNR format)
- `cosmetic-{ad-block,popup-block}-rules.json` - CSS hiding rules specific to extension type
- `popup.html` & `popup.js` - Extension popup interface

Each extension loads only its specific rule files:
- **Ad Blocker**: `rules.json` from `ad-block-rules.json`, cosmetic rules from `cosmetic-ad-block-rules.json`
- **Popup Blocker**: `rules.json` from `popup-block-rules.json`, cosmetic rules from `cosmetic-popup-block-rules.json`

**Note**: Files in generated extension directories should not be edited directly - they're overwritten on each build.