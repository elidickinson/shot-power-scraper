# Adding Custom Filter Rules to uBlock Lite

## Quick Method: Add Rules to ad-block-custom-rules.txt

1. **Edit the custom rules file:**
   ```bash
   vim shot_power_scraper/extensions/ad-block-custom-rules.txt
   ```

2. **Add your filter rules** using uBlock filter syntax:
   ```
   # Block a domain
   ||ads.example.com^

   # Hide an element
   example.com##.annoying-popup

   # Allow a site (whitelist)
   @@||goodsite.com^$document
   ```

3. **Rebuild the extension:**
   ```bash
   ./shot_power_scraper/extensions/update-ublock.sh
   ```

Your custom rules will be compiled into the extension automatically.

## Filter Syntax

See: https://github.com/gorhill/uBlock/wiki/Static-filter-syntax

**Common patterns:**
- `||domain.com^` - Block domain and all subdomains
- `||domain.com^$third-party` - Block only as third-party
- `domain.com##.selector` - Hide element with CSS selector
- `@@||domain.com^` - Whitelist (allow) a domain
- `domain.com#@#.selector` - Disable element hiding for domain

## Enable Existing Built-in Lists

To enable built-in filter lists without rebuilding, edit `manifest.json`:

```bash
vim shot_power_scraper/extensions/ublock-lite-custom/manifest.json
```

Change `"enabled": false` to `"enabled": true` for lists like:

- `annoyances-cookies` - Cookie consent notices
- `annoyances-overlays` - Overlays and modals
- `annoyances-social` - Social media widgets
- `annoyances-widgets` - Chat widgets
- `stevenblack-hosts` - Steven Black's hosts file
- Plus 40+ regional lists

## Update Workflow

1. **Update extension + filter lists:**
   ```bash
   ./shot_power_scraper/extensions/update-ublock.sh
   ```
   This rebuilds from uBlock source with latest filters + your custom rules.

2. **Just add custom rules:**
   - Edit `ad-block-custom-rules.txt`
   - Run update script
   - Your rules get compiled in

3. **Update uBlock source code itself:**
   ```bash
   cd /tmp/uBlock && git pull
   ./shot_power_scraper/extensions/update-ublock.sh
   ```

## How It Works

- Build script operates on `extensions/uBlock/` source
- Your `ad-block-custom-rules.txt` gets injected into the build
- Build compiles all filter lists (including yours) to DNR JSON
- Output copied to `ublock-lite-custom/`
