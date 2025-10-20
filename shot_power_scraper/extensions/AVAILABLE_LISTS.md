# Available uBlock Filter Lists

Use with `--ublock-lists` to enable additional filter lists beyond the defaults.

## Usage

```bash
# Enable cookie consent blocking
shot-power-scraper 'https://example.com' --ad-block --ublock-lists annoyances-cookies -o test.png

# Enable multiple lists
shot-power-scraper 'https://example.com' --ad-block \
  --ublock-lists annoyances-cookies,annoyances-overlays,annoyances-social \
  -o test.png
```

## Core Lists

- **ublock-filters** - uBlock Origin filters
- **easylist** - Primary ad blocking list
- **easyprivacy** - Privacy protection list
- **pgl** - PGL (Peter Lowe's) list
- **ublock-badware** - Badware protection
- **urlhaus-full** - URLhaus malware list

## Annoyance Lists

- **annoyances-cookies** - Block cookie consent notices
- **annoyances-overlays** - Block overlay popups and modals
- **annoyances-social** - Block social media widgets (share buttons, etc.)
- **annoyances-widgets** - Block chat widgets and other annoyances
- **annoyances-others** - Block other miscellaneous annoyances
- **annoyances-notifications** - Block push notification prompts

## Additional Protection

- **adguard-mobile** - Mobile-specific blocking rules
- **adguard-spyware-url** - Additional spyware protection
- **stevenblack-hosts** - Steven Black's curated hosts file
- **dpollock-0** - Dan Pollock's hosts file
- **block-lan** - Block LAN/localhost requests
- **ublock-experimental** - Experimental filters (may cause breakage)
- **ubol-tests** - uBOL testing rules

## Regional Lists

### Europe
- **alb-0** - Albanian
- **bgr-0** - Bulgarian
- **hrv-0** - Croatian
- **cze-0** - Czech
- **deu-0** - German
- **est-0** - Estonian
- **fin-0** - Finnish
- **fra-0** - French
- **grc-0** - Greek
- **hun-0** - Hungarian
- **isl-0** - Icelandic
- **ita-0** - Italian
- **ltu-0** - Lithuanian
- **lva-0** - Latvian
- **mkd-0** - Macedonian
- **nld-0** - Dutch
- **nor-0** - Norwegian
- **pol-0** - Polish
- **rou-1** - Romanian
- **rus-0**, **rus-1** - Russian
- **spa-0**, **spa-1** - Spanish
- **svn-0** - Slovenian
- **swe-1** - Swedish
- **tur-0** - Turkish
- **ukr-0** - Ukrainian

### Asia
- **chn-0** - Chinese
- **ind-0** - Hindi
- **idn-0** - Indonesian
- **irn-0** - Persian/Farsi
- **isr-0** - Hebrew
- **jpn-1** - Japanese
- **kor-1** - Korean
- **tha-0** - Thai
- **vie-1** - Vietnamese

## How to Find List IDs

1. **Check manifest.json**:
   ```bash
   grep '"id"' shot_power_scraper/extensions/ublock-lite-custom/manifest.json | grep -v '"enabled": true'
   ```

2. **Look for disabled lists** - All lists marked `"enabled": false` can be enabled via `--ublock-lists`

## Permanently Enable Lists

Instead of using `--ublock-lists` every time, you can enable lists permanently:

```bash
# Edit the manifest
vim shot_power_scraper/extensions/ublock-lite-custom/manifest.json

# Change "enabled": false to "enabled": true for desired lists
```

Or rebuild with custom configuration (see CUSTOM_FILTERS.md).
