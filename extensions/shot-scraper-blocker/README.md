# Shot Scraper Ad Blocker Extension

This Chrome extension provides ad blocking functionality for shot-scraper using Chrome's declarativeNetRequest API.

## Features

- Blocks common ad networks and trackers
- Uses standard filter list format (compatible with EasyList)
- Lightweight and efficient using Chrome's native blocking API
- No CPU/memory overhead during browsing

## Building from Filter Lists

To rebuild the blocking rules from filter lists:

```bash
cd extensions/shot-scraper-blocker
./build.sh
# or
npm run build
```

The build script will:
- Check for required dependencies (curl, jq, git, node, npm)
- Automatically clone abp2dnr from GitHub if not present
- Download filter lists (EasyList, EasyPrivacy, Anti-Adblock Killer, Fanboy Annoyances)
- Convert them to Chrome's declarativeNetRequest format using abp2dnr
- Generate a `rules.json` file with up to 30,000 blocking rules

### Requirements

The build script checks for and requires:
- `curl` - for downloading filter lists
- `jq` - for JSON processing
- `git` - for cloning abp2dnr
- `node` - for running abp2dnr
- `npm` - for installing abp2dnr dependencies

If any are missing, the script will show installation instructions.

## Customizing Filter Lists

To add your own filter lists:

1. Edit `build.js` and add your filter list to the `FILTER_LISTS` array:
   ```javascript
   const FILTER_LISTS = [
     {
       name: 'EasyList',
       url: 'https://easylist.to/easylist/easylist.txt'
     },
     {
       name: 'YourCustomList',
       url: 'https://example.com/your-filter-list.txt'
     }
   ];
   ```

2. Rebuild the rules:
   ```bash
   npm run build
   ```

## Manual Rule Addition

To add custom blocking rules without rebuilding:

1. Edit `rules.json` directly
2. Add your rule following the declarativeNetRequest format:
   ```json
   {
     "id": 99999,
     "priority": 1,
     "action": { "type": "block" },
     "condition": {
       "urlFilter": "*example-ad-server.com*",
       "resourceTypes": ["script", "image", "xmlhttprequest", "sub_frame"]
     }
   }
   ```

## Usage with shot-scraper

The extension is automatically loaded when you use the `--ad-block` flag:

```bash
shot-scraper 'https://example.com' --ad-block -o screenshot.png
```

## Limitations

- Chrome limits extensions to 30,000 static rules
- Some complex filter patterns may not be supported
- Dynamic rule updates require rebuilding the extension

## Debugging

To see blocked requests in the browser console:
1. Use shot-scraper with `--interactive` and `--ad-block` flags
2. Open DevTools (F12)
3. Check the Console tab for blocked request logs