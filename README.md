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

For stealth features to work when running in headless mode (the default) you must run this command once to set up the correct user agent:

    shot-power-scraper set-default-user-agent


### Ad and Popup Blocking

This fork has a simple custom ad blocking extension. If called with --ad-block it blocks most ads and with --popup-block it blocks most modal dialogs, popups and cookie consent banners.

    shot-power-scraper --ad-block https://example.com

This can be enabled by default using the `config` command.

## ⚠️ Important: Differences from Original shot-scraper

This fork has significant differences from the original.

### 🚫 **Commands That Don't Work**
- `shot-power-scraper har` - HAR file recording is not implemented.
- `shot-power-scraper accessibility` - Returns placeholder data only.

### 🔄 **Commands With Limited Functionality**
- Console logging (`--log-console`) - Basic CDP implementation, may miss some message types.
- Browser selection (`--browser`) - Only Chrome/Chromium is supported.
- The `--log-requests` option is not implemented.

### ⚠️ **Missing Features from Original**
- **Multi-browser support** - Firefox and WebKit/Safari automation is not available.
- **Advanced network features** - HAR recording and request interception are not available.

## 📋 **Command Status**

- ✅ `shot`: Fully Implemented (except `--log-requests`)
- ✅ `multi`: Fully Implemented (except HAR options)
- ✅ `pdf`: Fully Implemented
- ✅ `javascript`: Fully Implemented
- ✅ `html`: Fully Implemented
- ✅ `auth`: Fully Implemented
- ✅ `install`: Fully Implemented. Checks for a valid browser and prints the path.
- ✅ `set-default-user-agent`: Fully Implemented
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
