# shot-power-scraper

> A command-line utility for taking automated screenshots of websites, powered by **nodriver** for enhanced stealth and anti-detection capabilities.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/shot-scraper/blob/master/LICENSE)

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
- `shot-power-scraper har` - Not implemented.
- `shot-power-scraper accessibility` - Not implemented.
- `--log-requests` option is not implemented.
- Selectors like `-s` don't currently work correctly with screenshots
- `--quality` to specify JPEG quality not implemented.

### 🔄 **Commands With Limited Functionality**
- Console logging (`--log-console`) - Basic CDP implementation, may miss some message types.
- Browser selection (`--browser`) - Only Chrome/Chromium is supported.

## 📋 **Command Status**

- ✅ `shot`: Fully Implemented (except `--log-requests`)
- ✅ `multi`: Fully Implemented (except HAR options)
- ✅ `pdf`: Fully Implemented
- ✅ `javascript`: Fully Implemented
- ✅ `html`: Fully Implemented
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

The following examples use the original `shot-scraper`, but the concepts can be adapted for this fork.

- The [shot-scraper-demo](https://github.com/simonw/shot-scraper-demo) repository uses the tool to capture recently spotted owls in El Granada, CA.
- The [Datasette Documentation](https://docs.datasette.io/en/latest/) uses screenshots taken by `shot-scraper`.
- Ben Welsh built [@newshomepages](https://twitter.com/newshomepages), a Twitter bot that uses `shot-scraper` and GitHub Actions to take and publish screenshots of news homepages.
- [scrape-hacker-news-by-domain](https://github.com/simonw/scrape-hacker-news-by-domain) uses `shot-scraper javascript` to scrape a web page.

## Code Architecture: `shot-power-scraper shot` Execution Path

This section outlines the major code path and functions called when executing `shot-power-scraper shot ...`.

### Entry Point and Flow
1. **CLI Entry** (`cli.py:shot()`) - Parse arguments, create centralized `ShotConfig` object with all parameters
2. **Browser Command** (`cli.py:run_browser_command()`) - Orchestrate browser lifecycle using `shot_config`
3. **Extension Setup** (`browser.py:setup_blocking_extensions()`) - Configure ad/popup blocking based on `shot_config`
4. **Browser Context** (`browser.py:create_browser_context()`) - Initialize nodriver browser using `shot_config` parameters
5. **Screenshot Execution** (`cli.py:execute_shot()`) - Handle interactive mode and viewport
6. **Core Screenshot** (`screenshot.py:take_shot()`) - Main screenshot logic with `shot_config`
7. **Page Setup** (`page_utils.py:navigate_to_page()`) - Navigate, wait, handle errors using `shot_config`
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
