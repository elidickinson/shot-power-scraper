# shot-power-scraper (nodriver fork)

> ⚠️ **This is a fork** of Simon Willison's [original shot-scraper](https://github.com/simonw/shot-scraper). Some commands don't work - see [differences section](#️-important-differences-from-original-shot-power-scraper) below.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/shot-scraper/blob/master/LICENSE)

*Original project badges: [PyPI](https://pypi.org/project/shot-scraper/) | [Changelog](https://github.com/simonw/shot-scraper/releases) | [Tests](https://github.com/simonw/shot-scraper/actions?query=workflow%3ATest) | [Discord](https://discord.gg/EE7Hx4Kbny)*

A command-line utility for taking automated screenshots of websites, now powered by **nodriver** for enhanced stealth and anti-detection capabilities.

⚠️ **This is a fork of the original [shot-scraper](https://github.com/simonw/shot-scraper)** that has been migrated from Playwright to [nodriver](https://github.com/ultrafunkamsterdam/nodriver), providing built-in bypass capabilities for CAPTCHAs and Cloudflare bot detection.

## Documentation

- [Full documentation for shot-power-scraper](https://shot-scraper.datasette.io/)
- [Tutorial: Automating screenshots for the Datasette documentation using shot-power-scraper](https://simonwillison.net/2022/Oct/14/automating-screenshots/)
- [Release notes](https://github.com/simonw/shot-scraper/releases)

## Get started with GitHub Actions

To get started without installing any software, use the [shot-scraper-template](https://github.com/simonw/shot-scraper-template) template to create your own GitHub repository which takes screenshots of a page using `shot-power-scraper`. See [Instantly create a GitHub repository to take screenshots of a web page](https://simonwillison.net/2022/Mar/14/shot-scraper-template/) for details.

## Installation

Since this is a fork and not published to PyPI, you need to install it from this repository:

### Option 1: Clone and run directly
```bash
git clone [YOUR_REPOSITORY_URL]
cd shot-power-scraper
pip install click pyyaml nodriver click-default-group
python3 main.py --help
```

### Option 2: Install with uv (recommended)
```bash
git clone [YOUR_REPOSITORY_URL]
cd shot-power-scraper
uv run python3 main.py --help
```

### Option 3: Install as editable package
```bash
git clone [YOUR_REPOSITORY_URL]
cd shot-power-scraper
pip install -e .
shot-power-scraper --help
```

**Requirements**: Chrome or Chromium must be installed on your system. No driver installation required!

## Taking your first screenshot

You can take a screenshot of a web page like this:

    shot-power-scraper https://datasette.io/

This will create a screenshot in a file called `datasette-io.png`.

> **Note**: If you haven't installed the package, use `python3 main.py` instead of `shot-power-scraper` in all commands.

## Anti-Detection Features

This version includes comprehensive stealth capabilities that make it much harder to detect than standard automation tools:

### Enhanced Stealth with nodriver

Unlike Playwright and other automation frameworks, **nodriver** provides built-in anti-detection that bypasses most bot detection systems.

**Why nodriver is stealthier:**
- **No automation markers**: Removes `webdriver` properties and other automation signatures
- **Natural behavior simulation**: Mimics human-like browsing patterns
- **Advanced fingerprint masking**: Hides automation-specific JavaScript properties
- **Evasion techniques**: Built-in methods to avoid detection by anti-bot services

### Required: Set Up Stealth User Agent

**For maximum stealth effectiveness, you must run this command once after installation:**

    shot-power-scraper set-default-user-agent

What this does:
1. Launches Chrome in headless mode to detect your system's actual user agent
2. Finds something like: `Mozilla/5.0 ... HeadlessChrome/129.0.0.0 ...`
3. Changes "HeadlessChrome" to just "Chrome"
4. Saves this as your default user agent in `~/.config/shot-power-scraper/config.json`

Now all your screenshots will use this normal-looking user agent automatically:

    shot-power-scraper https://example.com  # Uses stealth + custom user agent
    shot-power-scraper --user-agent "Custom" https://example.com  # Override when needed

**The combination of nodriver's built-in stealth + proper user agent makes this tool significantly more effective than standard automation frameworks at bypassing bot detection.**

### Cloudflare Bypass
Automatic detection and bypassing of Cloudflare challenges:

    shot-power-scraper https://cloudflare-protected-site.com

The tool automatically:
- Detects Cloudflare "Just a moment..." pages
- Waits for challenges to complete
- Continues with screenshot capture

### Ad Blocking
Built-in ad blocking using Chrome extension technology:

    shot-power-scraper --ad-block https://example.com

Features:
- Blocks ads, trackers, and other unwanted content
- Uses filter lists to identify and block advertising elements
- Works with both single screenshots and multi-shot configurations
- Improves page load times and reduces visual clutter

### Annoyance Manager
Automatic removal of common webpage annoyances:

    shot-power-scraper https://example.com  # Annoyance removal runs automatically

The tool automatically:
- Dismisses cookie consent banners
- Closes newsletter signup popups
- Removes overlay dialogs and modals
- Clicks "No thanks" buttons on subscription prompts
- Handles common UI elements that block content

This ensures cleaner screenshots by removing elements that typically appear on first visit but wouldn't be present for regular users.

Many more options are available, see [Taking a screenshot](https://shot-scraper.datasette.io/en/stable/screenshots.html) for details.

## ⚠️ Important: Differences from Original shot-power-scraper

This fork has significant differences from the original shot-scraper. **Several commands do not work or have limited functionality.**

### 🚫 **Commands That Don't Work**
- `shot-power-scraper pdf` - PDF generation completely not implemented
- `shot-power-scraper har` - HAR file recording completely not implemented  
- `shot-power-scraper accessibility` - Returns placeholder data only ("not implemented")

### 🔄 **Commands With Limited Functionality**
- Console logging (`--log-console`) - Basic CDP implementation, may miss some message types
- Request/response monitoring - Limited network event handling via CDP
- Browser selection (`--browser`) - Only Chrome/Chromium supported (no Firefox/WebKit)
- Configuration system - Only `user_agent`, `ad_block`, and `popup_block` settings implemented

### ⚠️ **Missing Features from Original**
- **Multi-browser support** - Firefox, WebKit/Safari automation removed
- **Advanced network features** - Full HAR recording, request interception, response body capture
- **URL validation** - CLI argument validation marked as TODO

## 📋 **Detailed Command Option Status**

### `shot` command (screenshots) - ✅ **Fully Implemented**
**All options work:**
- `--auth` / `-a` - ✅ Authentication context file
- `--width` - ✅ Browser window width (default: 1280)
- `--height` - ✅ Browser window height (defaults to full page height)
- `--output` / `-o` - ✅ Output file path or `-` for stdout
- `--selector` / `-s` - ✅ CSS selector for element screenshots (multiple supported)
- `--selector-all` - ✅ All elements matching CSS selector
- `--js-selector` - ✅ JavaScript selector for element screenshots
- `--js-selector-all` - ✅ All elements matching JavaScript selector  
- `--padding` / `-p` - ✅ Padding around selected elements (default: 0)
- `--javascript` / `-j` - ✅ Execute JavaScript before screenshot
- `--retina` - ✅ Use device scale factor of 2
- `--scale-factor` - ✅ Custom device scale factor
- `--omit-background` - ✅ Transparent background (PNG only)
- `--quality` - ✅ JPEG quality setting
- `--wait` - ✅ Wait milliseconds before screenshot (default: 250)
- `--wait-for` - ✅ Wait for JavaScript expression to be true
- `--timeout` - ✅ Timeout in milliseconds
- `--interactive` / `-i` - ✅ Interactive mode with manual control
- `--devtools` - ✅ Open with developer tools
- `--log-requests` - ✅ Log requests to file
- `--log-console` - ✅ Log console output to stderr
- `--browser` / `-b` - ✅ Browser selection (Chrome/Chromium only)
- `--browser-arg` - ✅ Additional browser arguments
- `--user-agent` - ✅ Custom user agent string
- `--reduced-motion` - ✅ Emulate reduced motion preference
- `--skip` - ✅ Skip pages with HTTP errors
- `--fail` - ✅ Fail on HTTP errors
- `--bypass-csp` - ✅ Bypass Content Security Policy
- `--silent` - ✅ Suppress output messages
- `--auth-username` - ✅ HTTP Basic auth username
- `--auth-password` - ✅ HTTP Basic auth password
- `--skip-cloudflare-check` - ✅ Skip Cloudflare challenge detection
- `--skip-wait-for-load` - ✅ Skip waiting for window load event
- `--full-page` - ✅ Capture full scrollable page
- `--verbose` - ✅ Verbose logging
- `--save-html` - ✅ Save HTML alongside screenshot
- `--ad-block` / `--no-ad-block` - ✅ Ad blocking toggle
- `--popup-block` / `--no-popup-block` - ✅ Popup blocking toggle

### `multi` command (batch screenshots) - ✅ **Fully Implemented**
**All options work:**
- `--auth` / `-a` - ✅ Authentication context file
- `--retina` - ✅ Use device scale factor of 2
- `--scale-factor` - ✅ Custom device scale factor
- `--timeout` - ✅ Timeout in milliseconds
- `--fail-on-error` - ✅ Fail noisily on error (hidden option)
- `--no-clobber` / `-n` - ✅ Skip existing files
- `--output` / `-o` - ✅ Filter to specific output files
- `--browser` / `-b` - ✅ Browser selection (Chrome/Chromium only)
- `--browser-arg` - ✅ Additional browser arguments
- `--user-agent` - ✅ Custom user agent string
- `--reduced-motion` - ✅ Emulate reduced motion preference
- `--log-console` - ✅ Log console output to stderr
- `--skip` - ✅ Skip pages with HTTP errors
- `--fail` - ✅ Fail on HTTP errors
- `--silent` - ✅ Suppress output messages
- `--auth-username` - ✅ HTTP Basic auth username
- `--auth-password` - ✅ HTTP Basic auth password
- `--leave-server` - ✅ Keep server processes running
- `--verbose` - ✅ Verbose logging
- `--ad-block` / `--no-ad-block` - ✅ Ad blocking toggle
- `--popup-block` / `--no-popup-block` - ✅ Popup blocking toggle
- `--har` - ❌ **Not implemented** (raises abort error)
- `--har-zip` - ❌ **Not implemented** (raises abort error)  
- `--har-file` - ❌ **Not implemented** (raises abort error)

### `javascript` command - ✅ **Fully Implemented**
**All options work:**
- `--input` / `-i` - ✅ JavaScript input file or GitHub script (`gh:user/script`)
- `--auth` / `-a` - ✅ Authentication context file
- `--output` / `-o` - ✅ Output file for JSON results
- `--raw` / `-r` - ✅ Output raw text instead of JSON
- `--browser` / `-b` - ✅ Browser selection (Chrome/Chromium only)
- `--browser-arg` - ✅ Additional browser arguments
- `--user-agent` - ✅ Custom user agent string
- `--reduced-motion` - ✅ Emulate reduced motion preference
- `--log-console` - ✅ Log console output to stderr
- `--skip` - ✅ Skip pages with HTTP errors
- `--fail` - ✅ Fail on HTTP errors
- `--bypass-csp` - ✅ Bypass Content Security Policy
- `--auth-username` - ✅ HTTP Basic auth username
- `--auth-password` - ✅ HTTP Basic auth password

### `html` command - ✅ **Fully Implemented**
**All options work:**
- `--auth` / `-a` - ✅ Authentication context file
- `--output` / `-o` - ✅ Output file path or `-` for stdout
- `--javascript` / `-j` - ✅ Execute JavaScript before capturing HTML
- `--selector` / `-s` - ✅ CSS selector for specific element's outerHTML
- `--wait` - ✅ Wait milliseconds before capture (default: 250)
- `--timeout` - ✅ Timeout in milliseconds
- `--verbose` - ✅ Verbose logging
- `--log-console` - ✅ Log console output to stderr
- `--browser` / `-b` - ✅ Browser selection (Chrome/Chromium only)
- `--browser-arg` - ✅ Additional browser arguments
- `--user-agent` - ✅ Custom user agent string
- `--skip` - ✅ Skip pages with HTTP errors
- `--fail` - ✅ Fail on HTTP errors
- `--bypass-csp` - ✅ Bypass Content Security Policy
- `--silent` - ✅ Suppress output messages
- `--auth-username` - ✅ HTTP Basic auth username
- `--auth-password` - ✅ HTTP Basic auth password

### `auth` command - ✅ **Fully Implemented**
**All options work:**
- `--browser` / `-b` - ✅ Browser selection (Chrome/Chromium only)
- `--browser-arg` - ✅ Additional browser arguments
- `--user-agent` - ✅ Custom user agent string
- `--devtools` - ✅ Open browser with DevTools
- `--log-console` - ✅ Log console output to stderr

### `accessibility` command - ⚠️ **Placeholder Only**
**Options exist but return placeholder data:**
- `--auth` / `-a` - ✅ Authentication context file (works)
- `--output` / `-o` - ✅ Output file (works)
- `--javascript` / `-j` - ✅ Execute JavaScript (works)
- `--timeout` - ✅ Timeout setting (works)
- `--log-console` - ✅ Console logging (works)
- `--skip` - ✅ Skip on HTTP errors (works)
- `--fail` - ✅ Fail on HTTP errors (works)
- `--bypass-csp` - ✅ Bypass CSP (works)
- `--auth-username` - ✅ HTTP Basic auth username (works)
- `--auth-password` - ✅ HTTP Basic auth password (works)

**Note**: All options are technically implemented but the command only returns `{"message": "Accessibility tree dumping not implemented"}`.

### `har` command - ❌ **Not Implemented**
**Command exists but immediately aborts with error message:**
- All options are defined but non-functional
- Command displays error: "HAR recording is not implemented with nodriver"

### `pdf` command - ❌ **Not Implemented**
**Command exists but immediately aborts with error message:**
- All options are defined but non-functional
- Command displays error: "PDF generation is not implemented with nodriver"

### `install` command - ℹ️ **Info Only**
**Command works but no actual installation:**
- `--browser` / `-b` - ✅ Browser selection (for info display only)
- Displays message: "nodriver... does not require any drivers"

### `set-default-user-agent` command - ✅ **Fully Implemented**
**All options work:**
- `--browser` / `-b` - ✅ Browser selection (Chrome/Chromium only)
- `--browser-arg` - ✅ Additional browser arguments

### `config` command - ✅ **Fully Implemented**
**All options work:**
- `--ad-block` - ✅ Set default ad blocking (true/false)
- `--popup-block` - ✅ Set default popup blocking (true/false)
- `--user-agent` - ✅ Set default user agent string
- `--clear` - ✅ Clear all configuration settings (delete config file)
- `--show` - ✅ Show current configuration

### ✅ **Commands That Work Fully**
- `shot-power-scraper` (screenshots) - Full functionality
- `shot-power-scraper javascript` - Full functionality
- `shot-power-scraper html` - Full functionality
- `shot-power-scraper multi` - Full functionality (except HAR options)
- `shot-power-scraper auth` - Full functionality
- `shot-power-scraper install` - Now just shows info message (no installation needed)

### 🆕 **New Commands**
- `shot-power-scraper set-default-user-agent` - Configure stealth user agent
- `shot-power-scraper config` - Configure default settings (ad/popup blocking, user agent)

### 🎯 **Why This Fork? Benefits of nodriver Migration**
- **No driver management** - Uses your installed Chrome/Chromium directly
- **Anti-detection capabilities** - Bypasses CAPTCHAs and Cloudflare automatically
- **Better performance** - Async architecture throughout
- **Stealth mode** - Undetected automation that doesn't reveal "HeadlessChrome"
- **Simplified setup** - No separate browser or driver downloads needed

**Trade-off**: Some original shot-scraper functionality is lost, but you gain powerful anti-detection capabilities for web scraping scenarios.

### 🤔 **Should You Use This Fork?**
- **Use this fork if**: You need to bypass Cloudflare, avoid CAPTCHA challenges, or require stealth browsing for web scraping
- **Use the original if**: You need PDF generation, HAR recording, accessibility features, or multi-browser support


## Configuration & Defaults

shot-power-scraper stores default settings in `~/.shot-power-scraper/config.json` that apply to all commands unless overridden with command-line options.

### How It Works
- Settings in the config file become the new defaults for all commands
- Command-line options always override config file settings
- Supports setting default user agent, ad blocking, and popup blocking

### Configuration Commands
```bash
# Set individual options
shot-power-scraper config --ad-block true
shot-power-scraper config --popup-block false
shot-power-scraper config --user-agent "Mozilla/5.0 (Custom) ..."

# View current settings
shot-power-scraper config --show

# Clear all settings
shot-power-scraper config --clear
```

### Example Config File
After configuring various settings, your config file will look like:
```json
{
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
  "ad_block": true,
  "popup_block": false
}
```

These settings will be used for all screenshots automatically:

    shot-power-scraper https://example.com  # Uses config defaults
    shot-power-scraper --user-agent "Custom" https://example.com  # Override when needed
    shot-power-scraper --no-ad-block https://example.com  # Override ad blocking

**Note**: Config file uses `user_agent` (underscore) while command line uses `--user-agent` (hyphen). This is the standard convention for Python CLI tools.

📖 **See [CONFIG.md](CONFIG.md) for a complete reference of all configuration options.**

## Code Structure

The codebase has been refactored for better maintainability and clarity:

- **`shot_power_scraper/cli.py`** - Main CLI interface with all command definitions and decorators
- **`shot_power_scraper/browser.py`** - Browser management and initialization
- **`shot_power_scraper/screenshot.py`** - Core screenshot functionality and element selection
- **`shot_power_scraper/page_utils.py`** - Page interaction utilities (JavaScript evaluation, Cloudflare bypass, DOM ready detection)
- **`shot_power_scraper/utils.py`** - General utility functions

## Examples

- The [shot-scraper-demo](https://github.com/simonw/shot-scraper-demo) repository uses this tool to capture recently spotted owls in El Granada, CA according to [this page](https://www.owlsnearme.com/?place=127871), and to  generate an annotated screenshot illustrating a Datasette feature as described [in my blog](https://simonwillison.net/2022/Mar/10/shot-scraper/#a-complex-example).
- The [Datasette Documentation](https://docs.datasette.io/en/latest/) uses screenshots taken by `shot-power-scraper` running in the [simonw/datasette-screenshots](https://github.com/simonw/datasette-screenshots) GitHub repository, described in detail in [Automating screenshots for the Datasette documentation using shot-power-scraper](https://simonwillison.net/2022/Oct/14/automating-screenshots/).
- Ben Welsh built [@newshomepages](https://twitter.com/newshomepages), a Twitter bot that uses `shot-power-scraper` and GitHub Actions to take screenshots of news website homepages and publish them to Twitter. The code for that lives in [palewire/news-homepages](https://github.com/palewire/news-homepages).
- [scrape-hacker-news-by-domain](https://github.com/simonw/scrape-hacker-news-by-domain) uses `shot-power-scraper javascript` to scrape a web page. See [Scraping web pages from the command-line with shot-power-scraper](https://simonwillison.net/2022/Mar/14/scraping-web-pages-shot-scraper/) for details of how this works.
- Reuters uses shot-power-scraper to generate regularly updating data dashboards [for email newsletters](https://twitter.com/palewire/status/1658069533763026944).
