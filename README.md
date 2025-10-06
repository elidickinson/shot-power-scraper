# shot-power-scraper

> A command-line utility for taking automated screenshots of websites, powered by **nodriver** for enhanced stealth and anti-detection capabilities.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/elidickinson/shot-power-scraper/blob/main/LICENSE)

This is a fork of Simon Willison's excellent [shot-scraper](https://github.com/simonw/shot-scraper), migrated from Playwright to [nodriver](https://github.com/ultrafunkamsterdam/nodriver). This provides powerful, built-in bypass capabilities for CAPTCHAs and services like Cloudflare.

## Installation

The easiest way to install this tool is with `uv`:

```bash
uv tool install git+https://github.com/elidickinson/shot-power-scraper.git
```

Then run the `install` command to verify that it can find your browser:
```bash
shot-power-scraper install
```

**Requirements**: Google Chrome or Chromium must be installed on your system. No separate driver installation is required.

## Taking your first screenshot

You can take a screenshot of a web page like this:

    shot-power-scraper https://datasette.io/

This will create a screenshot in a file called `datasette-io.png`.

## Different Output Formats

Beyond screenshots, `shot-power-scraper` supports multiple output formats:

### Screenshots (default)
```bash
shot-power-scraper https://example.com/          # Creates example-com.png
```

### PDF Documents
```bash
shot-power-scraper pdf https://example.com/      # Creates example-com.pdf
```

### HTML Source
```bash
shot-power-scraper html https://example.com/     # Outputs HTML to stdout
shot-power-scraper html https://example.com/ -o page.html
```

### MHTML Web Archives
```bash
shot-power-scraper mhtml https://example.com/    # Creates example-com.mhtml
shot-power-scraper mhtml https://example.com/ -o archive.mhtml
```

MHTML (MIME HTML) archives contain the complete web page including all embedded resources like images, CSS, and JavaScript in a single file - perfect for offline viewing or archival purposes.

## Anti-Detection Features

This fork includes comprehensive stealth capabilities that make it much harder to detect than standard automation tools.

### Enhanced Stealth with nodriver

Unlike Playwright and other automation frameworks, **nodriver** provides built-in anti-detection that bypasses most bot detection systems by removing automation markers, simulating natural browser behavior, and masking its fingerprint.

### Required: Set Up Stealth User Agent

For stealth features to work when running in headless mode (the default) you must run the install command once to set up the correct user agent:

    shot-power-scraper install


### Ad and Popup Blocking

This fork includes Chrome extensions for blocking ads and popups during screenshot capture. Use `--ad-block` to block advertisements and `--popup-block` to block modal dialogs, popups and cookie consent banners.

    shot-power-scraper --ad-block --popup-block https://example.com

This can be enabled by default using the `config` command. For detailed information about the extensions, custom filter rules, and architecture, see [EXTENSIONS.md](EXTENSIONS.md).

## ⚠️ Important: Differences from Original shot-scraper

This fork has some important differences from the original. It only supports Chrome/Chromium and some features aren't fully implemented.

### 🚫 **Commands & Features That Don't Work**
- `shot-power-scraper accessibility` - Not implemented.
- `--log-requests` option is not implemented.
- Selectors like `-s` don't currently work correctly with screenshots
- `--quality` to specify JPEG quality not implemented.

### 🔄 **Commands With Limited Functionality**
- Console logging (`--log-console`) - Basic CDP implementation, may miss some message types.
- Browser selection (`--browser`) - Only Chrome/Chromium is supported.

## 📋 **Command Status**

- ✅ `shot`: Fully Implemented (except `--log-requests`)
- ✅ `multi`: Fully Implemented
- ✅ `pdf`: Fully Implemented
- ✅ `javascript`: Fully Implemented
- ✅ `html`: Fully Implemented
- ✅ `mhtml`: Fully Implemented - Create MHTML web page archives
- ✅ `har`: Fully Implemented - Record HTTP Archive files
- ✅ `auth`: Fully Implemented
- ✅ `install`: Fully Implemented - also sets up user agent for stealth mode
- ✅ `config`: Fully Implemented

## Configuration & Defaults

`shot-power-scraper` stores default settings in `~/.config/shot-power-scraper/config.json`. These settings are used unless overridden by command-line options.

### Configuration Commands
```bash
# Set default ad and popup blocking
shot-power-scraper config --ad-block true --popup-block true

# View current settings
shot-power-scraper config --show

# Clear all settings
shot-power-scraper config --clear
```

## Examples

The following examples demonstrate concepts that can be adapted for shot-power-scraper.

- Examples of similar usage patterns can be found in projects that use the original shot-scraper as a reference
- The concepts demonstrated in [shot-scraper-demo](https://github.com/simonw/shot-scraper-demo) can be adapted for shot-power-scraper
- The [Datasette Documentation](https://docs.datasette.io/en/latest/) shows how screenshots can be integrated into documentation workflows
- Projects like [@newshomepages](https://twitter.com/newshomepages) demonstrate automated screenshot workflows
- [scrape-hacker-news-by-domain](https://github.com/simonw/scrape-hacker-news-by-domain) shows JavaScript execution patterns that can be adapted

## Code Architecture: `shot-power-scraper shot` Execution Path

This section outlines the major code path and functions called when executing `shot-power-scraper shot ...`.

### Entry Point and Flow
1. **CLI Entry** (`cli.py:shot()`) - Parse arguments, create centralized `ShotConfig` object with all parameters
2. **Browser Command** (`cli.py:run_browser_command()`) - Orchestrate browser lifecycle using `shot_config`
3. **Extension Setup** (`browser.py:setup_blocking_extensions()`) - Configure ad/popup blocking based on `shot_config`
4. **Browser Context** (`browser.py:create_browser_context()`) - Initialize nodriver browser using `shot_config` parameters
5. **Screenshot Execution** (`cli.py:execute_shot()`) - Handle interactive mode and viewport
6. **Core Screenshot** (`screenshot.py:take_shot()`) - Main screenshot logic with `shot_config`
7. **Page Setup** (`page_utils.py:create_tab_context()` + `navigate_to_url()`) - Create tab context, navigate, wait, handle errors using `shot_config`
8. **Screenshot Capture** (`screenshot.py:_save_screenshot()`) - Take and save image
9. **Browser Cleanup** (`browser.py:cleanup_browser()`) - Stop browser and cleanup
10. **Async Wrapper** (`cli.py:run_nodriver_async()`) - Setup nodriver event loop

### Key Modules and Responsibilities
- **cli.py** - Main entry point, CLI parsing, command orchestration
- **shot_config.py** - Centralized configuration object with all parameters (browser, screenshot, execution options) and config file management
- **browser.py** - Browser instance management, extension setup, cleanup
- **screenshot.py** - Core screenshot logic, selector handling, image capture
- **page_utils.py** - Page navigation, error detection, Cloudflare handling, JavaScript execution
- **utils.py** - Utility functions for filename generation, URL processing, GitHub script loading

### Architecture Design
- **Centralized Configuration**: All parameters (browser options, screenshot settings, execution flags) are consolidated in `ShotConfig`
- **Simplified Interfaces**: `run_browser_command()` takes just `command_func` and `shot_config` parameters
- **Config File Integration**: Configuration file loading and defaults are handled directly in `ShotConfig.__init__()`
- **Consistent Pattern**: All CLI commands follow the same `ShotConfig` → `run_browser_command()` pattern

### Major Operations
- Configuration parsing, validation, and config file fallback handling
- Browser context initialization with anti-detection features using consolidated configuration
- Optional extension loading for ad/popup blocking
- Page navigation with error detection and Cloudflare bypass
- JavaScript execution and custom waiting conditions
- Element selector processing (CSS/JS selectors)
- Screenshot capture (full page or element-specific)
- Optional HTML content saving
- Comprehensive cleanup of browser and temporary files

The architecture is fully async-based using nodriver for enhanced stealth capabilities and automatic anti-detection. All configuration is centralized through `ShotConfig` for consistency and maintainability.

## How It Works: Understanding Execution Order

### Standard Screenshot Sequence

1. **CLI Parsing** (`cli.py:shot()`) - Parse command-line arguments and create `ShotConfig`
2. **Browser Initialization** (`browser.py:create_browser_context()`) - Start nodriver browser with stealth features
3. **Tab Creation** (`page_utils.py:create_tab_context()`) - Create new tab and configure user agent
4. **Page Navigation** (`page_utils.py:navigate_to_url()`) - Navigate to target URL and wait for load
5. **Viewport Setup** (`page_utils.py:navigate_to_url()`) - Set viewport dimensions if width/height explicitly specified (not full page)
6. **Error Detection** - Check for Chrome error pages and DNS failures
7. **Cloudflare Handling** - Detect and wait for Cloudflare challenge bypass
8. **Wait Operations** - Apply `--wait` delay and `--wait-for` conditions
9. **JavaScript Execution** - Execute any provided JavaScript code
10. **Lazy Loading** (`page_utils.py:trigger_lazy_load()`) - Trigger lazy-loaded content if requested
11. **Viewport Expansion** - Apply viewport expansion when blocking extensions are enabled
12. **Screenshot Capture** (`screenshot.py:_save_screenshot()`) - Set final viewport and capture screenshot
13. **HTML Saving** - Save HTML content if `--save-html` specified
14. **Browser Cleanup** (`browser.py:cleanup_browser()`) - Stop browser and clean up temporary files

### Feature Interaction Notes

- **Dual Viewport Approach**:
  - **Window Size** (`set_window_size`) - Controls physical browser window dimensions (important for `--interactive` and `--devtools` modes)
  - **Viewport Metrics** (`set_device_metrics_override`) - Controls page layout dimensions for rendering and screenshot capture
- **Viewport Timing**: Viewport metrics are set immediately after navigation (step 5) if width/height explicitly specified (not full page), aiding lazy loading of images
- **Extension Effects**: Ad/popup blocking may require viewport expansion to fix intersection observer behavior (step 11)
- **Lazy Loading**: Only runs if `--trigger-lazy-load` is specified, after viewport setup but before final screenshot capture
- **Full Page Screenshots**: Skip early viewport setup; use calculated document height for viewport dimensions during screenshot capture (step 12)
- **Selector Screenshots**: Process JavaScript selectors before taking element-specific screenshots

### Error Handling Flow

- HTTP errors are checked after navigation and can trigger `--skip` (exit silently) or `--fail` (exit with error)
- Navigation errors are detected and can be handled with the same skip/fail logic
- Cloudflare challenges are automatically detected and waited for (unless disabled)
- All errors fail loudly with exceptions for debugging unless explicitly configured otherwise
