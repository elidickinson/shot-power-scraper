# Adding Custom Filter Lists to uBlock Lite

## Quick Method: Add Filter List URL

1. **Edit the assets file:**
   ```bash
   vim /tmp/uBlock/assets/assets.json
   ```

2. **Add your filter list** to the appropriate section. For example, to add a custom ad blocking list:
   ```json
   "my-custom-list": {
     "content": "filters",
     "contentURL": "https://example.com/my-filters.txt",
     "title": "My Custom Filters"
   }
   ```

3. **Rebuild the extension:**
   ```bash
   ./shot_power_scraper/extensions/update-ublock.sh
   ```

4. **Enable the list** in `manifest.json`:
   ```json
   {
     "id": "my-custom-list",
     "enabled": true,
     "path": "/rulesets/main/my-custom-list.json"
   }
   ```

## Example: Adding EasyList Cookie List

Let's say you want to add the EasyList Cookie list (which is actually already included but disabled).

**To enable existing lists:**

Just edit `ublock-lite-custom/manifest.json` and change:
```json
{
  "id": "annoyances-cookies",
  "enabled": false,
  "path": "/rulesets/main/annoyances-cookies.json"
}
```

To:
```json
{
  "id": "annoyances-cookies",
  "enabled": true,
  "path": "/rulesets/main/annoyances-cookies.json"
}
```

## Available Built-in Lists (Currently Disabled)

These are already compiled and ready to enable in `manifest.json`:

- `annoyances-cookies` - Cookie consent notices
- `annoyances-overlays` - Overlays and modals
- `annoyances-social` - Social media widgets
- `annoyances-widgets` - Chat widgets
- `annoyances-others` - Other annoyances
- `annoyances-notifications` - Push notifications
- `stevenblack-hosts` - Steven Black's hosts file
- `dpollock-0` - Dan Pollock's hosts file
- Plus 40+ regional lists for specific countries

## Workflow for Adding External Filter Lists

1. Clone/update uBlock repo: `cd /tmp/uBlock && git pull`
2. Edit `/tmp/uBlock/assets/assets.json` to add your filter URL
3. Run `make cleanassets` to clear cache
4. Run `make mv3-chromium` to rebuild with new list
5. Copy to extensions: `cp -r /tmp/uBlock/dist/build/uBOLite.chromium /path/to/extensions/ublock-lite-custom`
6. Enable in `manifest.json`

Or just run: `./shot_power_scraper/extensions/update-ublock.sh` after editing assets.json
