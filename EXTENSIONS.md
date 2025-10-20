# Browser Extensions

shot-power-scraper uses browser extensions for content blocking during screenshot capture.

## Extensions

- **uBlock Lite**: Manifest V3 ad blocker based on uBlock Origin for blocking ads and unwanted content
- **Bypass Paywalls Clean**: Third-party extension for bypassing paywalls on news sites

## uBlock Lite

uBlock Lite is the primary content blocking extension, providing comprehensive ad and annoyance blocking.

### Basic Usage

```bash
# Enable ad blocking
shot-power-scraper --ad-block https://example.com

# Enable ad blocking with additional filter lists (e.g., for popups/cookies)
shot-power-scraper --ad-block --ublock-lists annoyances-cookies,annoyances-overlays https://example.com
```

### Available Filter Lists

Use `--ublock-lists` to enable additional filter lists beyond the default ad blocking. Common options:

- `annoyances-cookies` - Block cookie consent notices
- `annoyances-overlays` - Block overlay popups and modals
- `annoyances-notifications` - Block push notification prompts
- `annoyances-social` - Block social media widgets
- `annoyances-widgets` - Block various annoyance widgets

Multiple lists can be combined with commas:
```bash
shot-power-scraper --ad-block --ublock-lists annoyances-cookies,annoyances-overlays,annoyances-social https://example.com
```

See `shot_power_scraper/extensions/AVAILABLE_LISTS.md` for a complete list of available filter lists.

### Custom Filter Rules

You can add custom blocking rules by editing:
```
shot_power_scraper/extensions/ad-block-custom-rules.txt
```

This file supports standard [Adblock Plus filter syntax](https://adblockplus.org/filter-cheatsheet):
- **Network rules**: `||domain.com^` blocks network requests
- **Cosmetic rules**: `example.com##.selector` hides page elements
- **Comments**: Lines starting with `!` are ignored

After editing custom rules, restart your shot-power-scraper command to apply changes.

### How It Works

uBlock Lite uses Chrome's Declarative Net Request API to:
- Block network requests before they load (ads, trackers, popups)
- Hide page elements via CSS injection (cosmetic blocking)
- Apply procedural filters for complex blocking scenarios

The extension is located at `shot_power_scraper/extensions/ublock-lite-custom/` and is automatically loaded when `--ad-block` is specified.

### Filter List Customization

When you specify `--ublock-lists`, shot-power-scraper dynamically modifies the extension's manifest to enable those specific filter lists. This is done by:

1. Copying the base uBlock Lite extension to a temporary directory
2. Modifying the manifest.json to enable the requested filter lists
3. Loading the customized extension into Chrome

## Bypass Paywalls Clean

The Bypass Paywalls Clean extension enables access to paywalled content on news sites.

### Usage

```bash
# Enable paywall bypass
shot-power-scraper --paywall-block https://www.nytimes.com

# Combine with ad blocking
shot-power-scraper --ad-block --paywall-block https://www.nytimes.com
```

### Coverage

The extension supports 2,400+ news sites across multiple categories:
- Major newspapers (NYT, WSJ, Washington Post, etc.)
- Tech publications (Wired, MIT Technology Review, etc.)
- Regional newspapers worldwide
- Custom sites (1,500+ additional publications)

The extension is located at `shot_power_scraper/extensions/bypass-paywalls-chrome-clean-master/`.

## Configuration Defaults

You can set blocking options as defaults:

```bash
# Set default ad blocking
shot-power-scraper config --ad-block true

# Set default paywall blocking
shot-power-scraper config --paywall-block true

# View current settings
shot-power-scraper config --show
```

Configuration is stored in `~/.config/shot-power-scraper/config.json`.

## Extension Loading

Extensions are loaded automatically when using blocking flags:
- `--ad-block` loads uBlock Lite
- `--ublock-lists` customizes uBlock Lite with additional filter lists
- `--paywall-block` loads Bypass Paywalls Clean

Chrome loads extensions via the `--load-extension` flag with required permission bypass via nodriver.

## Updating uBlock Lite

To update uBlock Lite to the latest version:

```bash
cd shot_power_scraper/extensions
./update-ublock.sh
```

This script downloads the latest version of uBlock Lite from the official repository and replaces the current version.

## Technical Details

### uBlock Lite Architecture

uBlock Lite consists of:
- Static rulesets (main, regex, strictblock) for network blocking
- Scripting rulesets (generic, procedural, specific, scriptlet) for cosmetic filtering
- Declarative Net Request rules for efficient blocking
- Manifest V3 compliance for Chrome extension compatibility

### Extension Manifest

Each filter list in uBlock Lite has an entry in the manifest.json `declarative_net_request.rule_resources` array. When you use `--ublock-lists`, shot-power-scraper finds the matching rule resources by ID and sets `enabled: true`.

### Performance

- uBlock Lite uses Chrome's native DNR API for optimal performance
- Filter lists are pre-compiled into efficient rule formats
- Minimal memory footprint compared to dynamic filtering
- No runtime rule compilation or processing
