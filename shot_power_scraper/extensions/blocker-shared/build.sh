#!/bin/bash
set -e

# Parse arguments
FORCE_DOWNLOAD=false
PATCH_PAYWALL_EXTENSION=true
[[ "$1" == "--force" ]] && FORCE_DOWNLOAD=true
[[ "$1" == "--no-patch-paywall" || "$2" == "--no-patch-paywall" ]] && PATCH_PAYWALL_EXTENSION=false

# Filter lists
AD_BLOCK_FILTERS="
adguard-base-optimized:https://filters.adtidy.org/extension/chromium/filters/2_optimized.txt
custom-ad-block-filters:local:custom-ad-block-filters.txt
"

POPUP_BLOCK_FILTERS="
adguard-popups-full:https://filters.adtidy.org/windows/filters/19.txt
i-dont-care-about-cookies:https://www.i-dont-care-about-cookies.eu/abp/
easylist-newsletters-ubo:https://ublockorigin.github.io/uAssets/thirdparties/easylist-newsletters.txt
anti-adblock-killer:https://raw.githubusercontent.com/reek/anti-adblock-killer/master/anti-adblock-killer-filters.txt
custom-popup-block-filters:local:custom-popup-block-filters.txt
"

FILTER_LISTS="$AD_BLOCK_FILTERS$POPUP_BLOCK_FILTERS"

# Setup abp2dnr
ensure_abp2dnr() {
    # [[ "$FORCE_DOWNLOAD" == true ]] && rm -rf abp2dnr
    if [[ ! -d "abp2dnr" ]]; then
        echo "Cloning and installing abp2dnr..."
        git clone https://github.com/kzar/abp2dnr.git
        cd abp2dnr && npm install --include=dev --verbose && cd ..
    fi
}

# Download and patch paywall extension
ensure_bypass_paywalls_extension() {
    local extension_dir="../bypass-paywalls-chrome-clean-master"
    local zip_url="https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-master.zip&inline=false"

    [[ "$FORCE_DOWNLOAD" == true ]] && rm -rf "$extension_dir"
    if [[ ! -d "$extension_dir" ]]; then
        echo "Downloading and patching Bypass Paywalls extension..."
        curl -s -L -o bypass-paywalls.zip "$zip_url"
        unzip -q bypass-paywalls.zip -d ../
        rm bypass-paywalls.zip
        patch_bypass_paywalls_extension
    fi
}

# Patch paywall extension
patch_bypass_paywalls_extension() {
    [[ "$PATCH_PAYWALL_EXTENSION" == false ]] && return

    local extension_dir="../bypass-paywalls-chrome-clean-master"
    echo "Patching Bypass Paywalls extension..."

    # Patch manifest.json - remove optional_host_permissions and add *://*/* to host_permissions
    cp "$extension_dir/manifest.json" "$extension_dir/manifest.json.backup"
    jq 'del(.optional_host_permissions) | .host_permissions = ["*://*/*"] + .host_permissions' \
        "$extension_dir/manifest.json.backup" > "$extension_dir/manifest.json"

    # Patch background.js - handle both with and without trailing comma
    sed -i.backup 's/optInUpdate: true,*/optInUpdate: true,\
  customOptIn: true/' "$extension_dir/background.js"

  # TODO: this doesn't work right
  # sed -i.backup 's/ext_api\.runtime\.openOptionsPage();/false && ext_api.runtime.openOptionsPage(); \/\/ Disabled by build script/' "$extension_dir/background.js"
}

# Download filter list
download_filter_list() {
    local name="$1" url="$2"
    local name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
    local filename="downloads/${name_lower}.txt"

    mkdir -p downloads

    if [[ "$url" == local:* ]]; then
        local source_file="${url#local:}"
        [[ ! -f "$source_file" ]] && touch "$source_file"
        cp "$source_file" "$filename"
    else
        [[ "$FORCE_DOWNLOAD" == true ]] && rm -f "$filename"
        if [[ ! -f "$filename" ]]; then
            curl -s -f -o "$filename" "$url" || echo "ERROR: Failed to download $url, continuing without it." >&2
        fi
    fi
}

# Process all rules for a given category
process_rules_by_category() {
    local category="$1" filter_list="$2" network_rules_output="$3" cosmetic_rules_output="$4"
    local combined_filters="downloads/combined_${category}_filters.txt"

    echo "Combining and processing $category rules..."
    > "$combined_filters" # Create or truncate the file

    # Combine all filter lists for the category into one file
    echo "$filter_list" | while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        name=$(echo "$line" | cut -d: -f1)
        name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
        local filter_file="downloads/${name_lower}.txt"
        if [[ -f "$filter_file" ]]; then
            cat "$filter_file" >> "$combined_filters"
            echo "" >> "$combined_filters" # Add a newline between files
        fi
    done

    # Generate network rules from the combined list
    node abp2dnr/abp2dnr.js < "$combined_filters" > "$network_rules_output"
    local total_network_rules=$(jq length "$network_rules_output")
    if [[ "$total_network_rules" -gt 30000 ]]; then
        echo "WARNING: Generated $total_network_rules $category network rules, limiting to 30,000."
        jq '.[0:30000]' "$network_rules_output" > "downloads/temp.json" && mv "downloads/temp.json" "$network_rules_output"
        echo "$category network rules: 30000"
    else
        echo "$category network rules: $total_network_rules"
    fi

    # Generate cosmetic rules from the combined list
    if [[ -s "$combined_filters" ]]; then
        local stats=$(node extract_cosmetic_rules.js --stats "$combined_filters")
        local valid=$(echo "$stats" | jq -r '.validCosmeticRules')
        local unsupported=$(echo "$stats" | jq -r '.unsupportedRules')
        node extract_cosmetic_rules.js "$combined_filters" "$cosmetic_rules_output"
        echo "$category cosmetic rules: $valid (${unsupported} unsupported)"
    else
        echo "[]" > "$cosmetic_rules_output"
        echo "$category cosmetic rules: 0 (0 unsupported)"
    fi
}

# Build extension
build_extension() {
    local type="$1" name="$2" description="$3" dir_name="$4" rules_file="$5" cosmetic_file="$6"

    mkdir -p "../$dir_name"
    echo "DO NOT EDIT - Files in this directory are auto-generated by blocker-shared/build.sh" > "../$dir_name/DO_NOT_EDIT__AUTOGENERATED.txt"

    # Copy shared files
    for file in background.js content.js content.css popup.html popup.js; do
        [[ -f "$file" ]] && cp "$file" "../$dir_name/"
    done

    # Copy rules files with standardized names
    [[ -f "$rules_file" ]] && cp "$rules_file" "../$dir_name/network-rules.json"
    [[ -f "$cosmetic_file" ]] && cp "$cosmetic_file" "../$dir_name/cosmetic-rules.json"

    # Create manifest
    cat > "../$dir_name/manifest.json" << EOF
{
  "manifest_version": 3,
  "name": "$name",
  "version": "1.0",
  "description": "$description",
  "permissions": ["declarativeNetRequest", "declarativeNetRequestFeedback", "activeTab", "webNavigation"],
  "host_permissions": ["<all_urls>"],
  "background": {"service_worker": "background.js"},
  "declarative_net_request": {
    "rule_resources": [{"id": "default_rules", "enabled": true, "path": "network-rules.json"}]
  },
  "web_accessible_resources": [{
    "resources": ["cosmetic-rules.json"],
    "matches": ["<all_urls>"]
  }],
  "action": {"default_title": "$name", "default_popup": "popup.html"},
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"],
    "css": ["content.css"],
    "run_at": "document_start"
  }]
}
EOF
}

# Check dependencies
check_dependencies() {
    for cmd in git curl unzip node npm jq; do
        if ! command -v "$cmd" &>/dev/null; then
            echo "ERROR: '$cmd' is not installed. Please install it and try again." >&2
            exit 1
        fi
    done
}

# Main script logic
main() {
    # Check dependencies
    check_dependencies

    # Parse arguments
    FORCE_DOWNLOAD=false
    PATCH_PAYWALL_EXTENSION=true
    [[ "$1" == "--force" ]] && FORCE_DOWNLOAD=true
    [[ "$1" == "--no-patch-paywall" || "$2" == "--no-patch-paywall" ]] && PATCH_PAYWALL_EXTENSION=false

    echo "Starting build process..."

    # Main
    ensure_abp2dnr
    ensure_bypass_paywalls_extension
    # Always rebuild filter files (custom files may have changed)
    echo "Cleaning up old rules..."
    rm -f downloads/*_rules.json cosmetic-*.json *-block-rules.json

    # Download all filter lists
    echo "Downloading all filter lists..."
    echo "$FILTER_LISTS" | while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        name=$(echo "$line" | cut -d: -f1)
        url=$(echo "$line" | cut -d: -f2-)
        download_filter_list "$name" "$url"
    done

    # Process rules by category
    process_rules_by_category "ad-block" "$AD_BLOCK_FILTERS" "ad-block-rules.json" "cosmetic-ad-block-rules.json"
    process_rules_by_category "popup-block" "$POPUP_BLOCK_FILTERS" "popup-block-rules.json" "cosmetic-popup-block-rules.json"

    # Build extensions
    echo "Building extensions..."
    build_extension "ad" "Shot Scraper Ad Blocker" "Ad blocker for shot-scraper" "shot-scraper-ad-blocker" "ad-block-rules.json" "cosmetic-ad-block-rules.json"
    build_extension "popup" "Shot Scraper Popup Blocker" "Popup and cookie notice blocker for shot-scraper" "shot-scraper-popup-blocker" "popup-block-rules.json" "cosmetic-popup-block-rules.json"

    # Cleanup
    echo "Cleaning up temporary files..."
    rm -f downloads/temp_*.json downloads/combined_*.txt

    echo "Build complete."
}

# Execute main
main "$@"
