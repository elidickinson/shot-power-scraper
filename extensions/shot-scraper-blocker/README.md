# Shot Scraper Ad Blocker

A comprehensive Chrome extension that provides both network-level request blocking and content-level element hiding for shot-scraper and general web browsing.

## Features

### Network Blocking (DNR)
- Blocks requests using Chrome's Declarative Net Request API
- Supports up to 30,000 blocking rules
- Processes multiple filter lists from trusted sources
- Optimized for performance with minimal CPU overhead

### Element Hiding (Cosmetic Filtering)
- Hides annoying elements using CSS selectors
- Parses ABP (Adblock Plus) compatible filter lists
- Filters out unsupported rule types during build
- Real-time application with DOM mutation observer

### Filter Categories

**Ad Blocking Filters** (Core ad blocking):
- AdGuard Base (Optimized) - Primary ad blocking rules

**Popup Blocking Filters** (Popups and annoyances):
- AdGuard Popups - Popup and overlay blocking
- AdGuard Cookie Notices - Cookie notification blocking
- EasyList Newsletters - Newsletter subscription blocking
- Anti-Adblock Killer - Circumvents anti-adblocker detection

## Installation

### Development Installation
1. Clone the repository and navigate to the extension directory
2. Install dependencies and build the extension:
   ```bash
   cd extensions/shot-scraper-blocker
   ./build.sh
   ```
3. Load the extension in Chrome:
   - Open Chrome and go to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked" and select the `shot-scraper-blocker` directory

### Production Installation
Load the extension directory directly into Chrome without building (uses pre-built rules).

## Build System

### Building the Extension
```bash
# Normal build (preserves existing downloads)
./build.sh

# Force redownload all filter lists
./build.sh --force
```

### Build Process
1. **Download Phase**: Downloads filter lists from trusted sources
2. **Statistics Phase**: Analyzes each filter list and shows breakdown
3. **Network Rules**: Converts ABP rules to Chrome DNR format using abp2dnr
4. **Cosmetic Rules**: Extracts element hiding rules and filters invalid selectors
5. **Combination**: Combines all rules with proper ID assignment
6. **Cleanup**: Preserves source files in `downloads/` directory

### Build Output
- `ad-block-rules.json` - Network blocking rules for advertisements
- `popup-block-rules.json` - Network blocking rules for popups and annoyances
- `rules.json` - Combined rules for backward compatibility
- `cosmetic_rules.json` - Element hiding rules for content script
- `downloads/` - All downloaded filter lists and intermediate files

## Architecture

### Core Components
- **Background Script** (`background.js`): Tracks blocked requests and hidden elements
- **Content Script** (`content.js`): Applies element hiding rules to web pages
- **Popup** (`popup.html`): Shows blocking statistics and extension status
- **Manifest** (`manifest.json`): Extension configuration and permissions

### Data Flow
```
Filter Lists → Build Process → Extension Files
     ↓              ↓              ↓
  .txt files → Processing → rules.json + cosmetic_rules.json
     ↓              ↓              ↓
  Network Rules → DNR API → Request Blocking
  Cosmetic Rules → Content Script → Element Hiding
```

## Statistics

The build process shows detailed statistics for each filter list:
- **Total**: Total lines in filter list
- **Network**: Network blocking rules (for DNR)
- **Cosmetic**: Element hiding rules found
- **Valid**: Valid cosmetic rules (usable)
- **Unsupported**: Filtered out rules (invalid selectors, CSS injection, etc.)

Example output:
```
Name                      Total  Network Cosmetic    Valid Unsupported
----                      -----  ------- --------    ----- -----------
adguard-base-optimized     1234      800      400      350          50
fanboy-annoyances         53398     4076    47272    46036        1236
```

## Development

### File Structure
```
shot-scraper-blocker/
├── downloads/              # Downloaded filter lists and intermediate files
│   ├── *.txt              # Original filter lists
│   ├── *_rules.json       # Processed DNR rules
│   └── combined_filters.txt # Temporary combined file
├── manifest.json          # Extension manifest
├── background.js          # Background service worker
├── content.js            # Content script for element hiding
├── content.css           # CSS for cosmetic filtering
├── popup.html           # Extension popup interface
├── popup.js             # Popup logic
├── rules.json           # Final DNR rules
├── cosmetic_rules.json  # Final cosmetic rules
├── build.sh            # Build script
└── extract_cosmetic_rules.js # Cosmetic rule processor
```

### Adding New Filter Lists
1. Edit `build.sh` and add to the appropriate category:
   ```bash
   # For ad blocking filters
   AD_BLOCK_FILTERS="
   existing-list:https://example.com/filter.txt
   new-ad-filter:https://newsite.com/ads.txt
   "
   
   # For popup blocking filters
   POPUP_BLOCK_FILTERS="
   existing-popup-filter:https://example.com/popups.txt
   new-popup-filter:https://newsite.com/annoyances.txt
   "
   ```
2. Run `./build.sh --force` to download and process

### Testing
- Use the popup to monitor blocking effectiveness
- Check browser console for cosmetic filtering logs
- Test on various websites to verify rule effectiveness

## Usage with shot-scraper

The extension supports selective blocking based on content type:

```bash
# Enable ad blocking only
shot-scraper 'https://example.com' --ad-block -o screenshot.png

# Enable popup blocking only  
shot-scraper 'https://example.com' --popup-block -o screenshot.png

# Enable both ad and popup blocking
shot-scraper 'https://example.com' --ad-block --popup-block -o screenshot.png

# Enable automatic annoyance clearing (manual DOM manipulation)
shot-scraper 'https://example.com' --clear-annoyances -o screenshot.png
```

## Troubleshooting

### Common Issues
1. **"Failed to load cosmetic filters"** - Run `./build.sh` to generate `cosmetic_rules.json`
2. **Console errors about selectors** - These are filtered out during build; rebuild with latest script
3. **Extension not blocking** - Check if `rules.json` exists and has content
4. **Build fails** - Ensure all dependencies are installed (curl, jq, node, npm)

### Dependencies
- `curl` - Download filter lists
- `jq` - Process JSON files
- `node` - Run JavaScript processing scripts
- `npm` - Install abp2dnr dependencies

### Performance Notes
- The extension processes 80K+ cosmetic rules efficiently
- DOM mutation observer has minimal performance impact
- Network blocking via DNR is highly optimized
- Statistics show rule effectiveness per filter list

## License

This extension processes filter lists from various sources. Each filter list maintains its own license:
- AdGuard filters: [AdGuard License](https://github.com/AdguardTeam/AdguardFilters)
- EasyList: [Creative Commons Attribution 3.0](https://easylist.to/)
- Fanboy's Annoyance List: [Creative Commons Attribution 3.0](https://secure.fanboy.co.nz/)

## Contributing

1. Fork the repository
2. Make changes to the extension
3. Test thoroughly on various websites
4. Submit a pull request with detailed description

For filter list issues, report to the respective filter list maintainers.