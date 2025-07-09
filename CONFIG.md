# shot-scraper Configuration Reference

The configuration file is located at `~/.shot-scraper/config.json` and sets default values for command-line options.

## Currently Supported Options

```json
{
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
}
```

- **user_agent**: Default user agent string for all requests. Set automatically via `shot-scraper set-default-user-agent`.

## Planned Options (Not Yet Implemented)

These options currently only work as command-line arguments but may be added to the config system in the future:

```json
{
  "width": 1280,                        // Browser viewport width in pixels
  "height": 720,                        // Browser viewport height (omit for full page capture)
  "wait": 2000,                         // Wait time in ms before screenshot
  "quality": 80,                        // JPEG quality (1-100)
  "timeout": 30000,                     // Page load timeout in ms
  "skip_wait_for_dom_ready": false,    // Skip waiting for DOM ready
  "wait_for_dom_ready_timeout": 10000, // DOM ready timeout in ms
  "skip_cloudflare_check": false,      // Disable Cloudflare detection
  "scale_factor": 1,                    // Device scale factor (2 = retina)
  "omit_background": false,             // Transparent background
  "bypass_csp": false,                  // Bypass Content Security Policy
  "reduced_motion": false,              // Emulate prefers-reduced-motion
  "padding": 0,                         // Padding for selector screenshots
  "auth_username": "user",              // HTTP auth username
  "auth_password": "pass"               // HTTP auth password
}
```

## Command Line vs Config File Names

Note the naming convention differences:
- Config file: `user_agent` (underscore)
- Command line: `--user-agent` (hyphen)

This follows Python's standard convention where JSON uses underscores and CLI uses hyphens.

## Example: Setting Multiple Defaults

Once these options are implemented, you could set defaults like:

```json
{
  "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
  "width": 1920,
  "height": 1080,
  "wait": 1000,
  "quality": 90,
}
```

Then every screenshot would use these defaults unless overridden:
```bash
shot-scraper https://example.com              # Uses all defaults
shot-scraper https://example.com --width 800  # Overrides just width
```