#!/bin/bash
set -e

# Color output functions
info() { echo -e "\033[1;34m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
success() { echo -e "\033[1;32m[SUCCESS]\033[0m $1"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

# Parse command line arguments
FORCE_DOWNLOAD=false
if [[ "$1" == "--force" ]]; then
    FORCE_DOWNLOAD=true
    info "Force download enabled - will redownload all filter lists"
fi

# Ad blocking filter lists (core ad blocking)
AD_BLOCK_FILTERS="
adguard-base-optimized:https://filters.adtidy.org/extension/chromium/filters/2_optimized.txt
custom-ad-block-filters:local:custom-ad-block-filters.txt
"

# Popup blocking filter lists (popups, cookie notices, newsletters, etc.)
POPUP_BLOCK_FILTERS="
adguard-popups-full:https://filters.adtidy.org/windows/filters/19.txt
i-dont-care-about-cookies:https://www.i-dont-care-about-cookies.eu/abp/
easylist-newsletters-ubo:https://ublockorigin.github.io/uAssets/thirdparties/easylist-newsletters.txt
anti-adblock-killer:https://raw.githubusercontent.com/reek/anti-adblock-killer/master/anti-adblock-killer-filters.txt
custom-popup-block-filters:local:custom-popup-block-filters.txt
"

# Combined list for backward compatibility
FILTER_LISTS="$AD_BLOCK_FILTERS$POPUP_BLOCK_FILTERS"
# adguard-cookie-notices-full:https://filters.adtidy.org/windows/filters/18.txt
# fanboy-annoyances:https://secure.fanboy.co.nz/fanboy-annoyance.txt
# adguard-annoyances-full:https://filters.adtidy.org/extension/chromium/filters/14.txt
#  Title: AdGuard Annoyances filter - Blocks irritating elements on web pages including cookie notices, third-party widgets and in-page pop-ups. Contains the following AdGuard filters: Cookie Notices, Popups, Mobile App Banners, Other Annoyances and Widgets.
# other annoyances https://filters.adtidy.org/windows/filters/21.txt
# easylist-newsletters-ubo:https://ublockorigin.github.io/uAssets/thirdparties/easylist-newsletters.txt
# ^ explicit site filters
# fanboy-annoyance-abp:https://easylist-downloads.adblockplus.org/fanboy-annoyance.txt
# AdGuard-popups:https://filters.adtidy.org/windows/filters/19.txt
# Adguard-annoyances-optimized:https://filters.adtidy.org/extension/chromium/filters/14_optimized.txt
# Fanboy-Annoyances-optimized:https://filters.adtidy.org/extension/ublock/filters/122_optimized.txt
# Fanboy-Annoyances:https://secure.fanboy.co.nz/fanboy-annoyance.txt
# Anti-Adblock-Killer:https://raw.githubusercontent.com/reek/anti-adblock-killer/master/anti-adblock-killer-filters.txt
# https://easylist-downloads.adblockplus.org/fanboy-annoyance.txt
# see readme on https://github.com/yokoffing/filterlists?tab=readme-ov-file#optimized-lists
# cookie notices https://filters.adtidy.org/extension/chromium/filters/18_optimized.txt
# dns filter https://filters.adtidy.org/extension/chromium/filters/15_optimized.txt
# remove tracking params https://filters.adtidy.org/extension/chromium/filters/17_optimized.txt
# easylist cookies https://secure.fanboy.co.nz/fanboy-cookiemonster.txt


# Ensure abp2dnr is available
ensure_abp2dnr() {
    if [ ! -d "abp2dnr" ] || [ ! -f "abp2dnr/abp2dnr.js" ] || [ ! -d "abp2dnr/node_modules" ]; then
        if [ -d "abp2dnr" ]; then
            warn "abp2dnr directory exists but appears incomplete, removing..."
            rm -rf abp2dnr
        fi
        
        info "Cloning abp2dnr from GitHub..."
        git clone https://github.com/kzar/abp2dnr.git

        info "Installing abp2dnr dependencies..."
        cd abp2dnr
        npm install --include=dev
        cd ..
        success "abp2dnr setup complete"
    else
        info "abp2dnr already exists and is properly set up"
    fi
}

# Download filter list
download_filter_list() {
    local name="$1"
    local url="$2"
    local name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
    local filename="downloads/${name_lower}.txt"

    # Create downloads directory if it doesn't exist
    mkdir -p downloads

    # Handle local files (prefixed with "local:")
    if [[ "$url" == local:* ]]; then
        local source_file="${url#local:}"
        
        # Check if source file exists
        if [ ! -f "$source_file" ]; then
            warn "$name source file $source_file not found, creating empty file"
            touch "$source_file"
        fi
        
        # Always copy local files (they may have been edited)
        info "Processing local filter list $name from $source_file..."
        cp "$source_file" "$filename"
        success "Processed local filter list $name to $filename"
        return 0
    fi

    # Check if file exists and --force not used
    if [ -f "$filename" ] && [ "$FORCE_DOWNLOAD" = false ]; then
        info "$name already exists (use --force to redownload)"
        return 0
    fi

    info "Downloading $name from $url..."
    if curl -s -o "$filename" "$url"; then
        success "Downloaded $name to $filename"
    else
        error "Failed to download $name"
        return 1
    fi
}

# Convert filter list using abp2dnr
convert_filter_list() {
    local input_file="$1"
    local output_file="$2"

    info "Converting $input_file to $output_file..."

    if node abp2dnr/abp2dnr.js < "$input_file" > "downloads/$output_file" 2>/dev/null; then
        local rule_count=$(jq length "downloads/$output_file" 2>/dev/null || echo "unknown")
        success "Generated $rule_count rules in downloads/$output_file"
    else
        error "Failed to convert $input_file"
        return 1
    fi
}

# Extract cosmetic rules from filter lists by category
extract_cosmetic_rules_by_category() {
    local category="$1"
    local filter_list="$2"
    local output_file="$3"
    
    info "Extracting $category cosmetic rules..."

    local combined_filters="downloads/combined_${category}_filters.txt"

    # Create downloads directory if it doesn't exist
    mkdir -p downloads

    # Clear previous combined file
    > "$combined_filters"

    # Print statistics header for this category
    echo ""
    info "$category Filter List Statistics:"
    printf "%-25s %8s %8s %8s %8s %8s %8s\n" "Name" "Total" "Network" "Cosmetic" "Script" "Valid" "Unsupported"
    printf "%-25s %8s %8s %8s %8s %8s %8s\n" "----" "-----" "-------" "--------" "------" "-----" "-----------"

    # Combine filter files for this category
    echo "$filter_list" | while IFS= read -r line; do
        # Skip empty lines
        [ -z "$line" ] && continue

        # Parse name from line
        name=$(echo "$line" | cut -d: -f1)
        name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
        local filter_file="downloads/${name_lower}.txt"

        if [ -f "$filter_file" ]; then
            # Get statistics for this filter file
            local stats=$(node extract_cosmetic_rules.js --stats "$filter_file")
            local total=$(echo "$stats" | jq -r '.totalLines')
            local network=$(echo "$stats" | jq -r '.networkRules')
            local cosmetic=$(echo "$stats" | jq -r '.cosmeticRules')
            local script=$(echo "$stats" | jq -r '.scriptRules')
            local valid=$(echo "$stats" | jq -r '.validCosmeticRules')
            local unsupported=$(echo "$stats" | jq -r '.unsupportedRules')

            printf "%-25s %8s %8s %8s %8s %8s %8s\n" "$name" "$total" "$network" "$cosmetic" "$script" "$valid" "$unsupported"

            echo "" >> "$combined_filters"
            echo "! === $name ===" >> "$combined_filters"
            cat "$filter_file" >> "$combined_filters"
        fi
    done

    # Extract cosmetic rules using our JavaScript processor
    if [ -f "$combined_filters" ]; then
        node extract_cosmetic_rules.js "$combined_filters" "$output_file"
        if [ -f "$output_file" ]; then
            local rule_count=$(jq length "$output_file" 2>/dev/null || echo "unknown")
            success "Extracted $rule_count $category cosmetic rules to $output_file"
        else
            warn "Failed to extract $category cosmetic rules"
        fi
    else
        warn "No filter files found for $category cosmetic rule extraction"
    fi
}

# Extract cosmetic rules for all categories
extract_cosmetic_rules() {
    extract_cosmetic_rules_by_category "ad-block" "$AD_BLOCK_FILTERS" "cosmetic-ad-block-rules.json"
    extract_cosmetic_rules_by_category "popup-block" "$POPUP_BLOCK_FILTERS" "cosmetic-popup-block-rules.json"
}

combine_rules_by_category() {
    local category="$1"
    local filter_list="$2"
    local output_file="$3"

    info "Combining $category rules..."

    local rule_id=1
    local temp_combined="downloads/temp_${category}_combined.json"

    # Create downloads directory if it doesn't exist
    mkdir -p downloads

    # Start with empty array
    echo "[]" > "$temp_combined"

    echo "$filter_list" | while IFS= read -r line; do
        # Skip empty lines
        [ -z "$line" ] && continue

        # Parse name from line
        name=$(echo "$line" | cut -d: -f1)
        name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
        local rules_file="downloads/${name_lower}_rules.json"

        if [ -f "$rules_file" ]; then
            info "Processing $rules_file for $category..."

            # Add IDs and merge with existing rules
            local temp_rules_file="downloads/temp_${category}_${name_lower}_rules.json"
            jq --argjson start_id "$rule_id" '
                [to_entries[] | .value.id = ($start_id + .key) | .value]
            ' "$rules_file" > "$temp_rules_file"

            # Update rule_id counter
            local count=$(jq length "$rules_file")
            rule_id=$((rule_id + count))

            # Merge with combined rules
            jq -s '.[0] + .[1]' "$temp_combined" "$temp_rules_file" > "downloads/temp_${category}_new_combined.json"
            mv "downloads/temp_${category}_new_combined.json" "$temp_combined"

            rm "$temp_rules_file"
        fi
    done

    # Limit to 30,000 rules (Chrome's limit)
    local total_rules=$(jq length "$temp_combined")
    if [ "$total_rules" -gt 30000 ]; then
        warn "Generated $total_rules $category rules, limiting to 30,000"
        jq '.[0:30000]' "$temp_combined" > "$output_file"
    else
        mv "$temp_combined" "$output_file"
    fi

    local final_count=$(jq length "$output_file")
    success "Generated $final_count $category rules in $output_file"
}

combine_rules() {
    # Generate category-specific rule files
    combine_rules_by_category "ad-block" "$AD_BLOCK_FILTERS" "ad-block-rules.json"
    combine_rules_by_category "popup-block" "$POPUP_BLOCK_FILTERS" "popup-block-rules.json"
}

# Check for required dependencies
check_dependencies() {
    local missing=()

    info "Checking dependencies..."

    # Check for required commands
    local required_commands=("curl" "jq" "git" "node" "npm")

    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Missing required dependencies: ${missing[*]}"
        echo ""
        echo "Installation instructions:"

        for cmd in "${missing[@]}"; do
            case $cmd in
                "curl")
                    echo "  Ubuntu/Debian: sudo apt update && sudo apt install curl"
                    echo "  macOS: curl is pre-installed"
                    ;;
                "jq")
                    echo "  Ubuntu/Debian: sudo apt update && sudo apt install jq"
                    echo "  macOS: brew install jq"
                    ;;
                "git")
                    echo "  Ubuntu/Debian: sudo apt update && sudo apt install git"
                    echo "  macOS: xcode-select --install"
                    ;;
                "node")
                    echo "  Ubuntu/Debian: sudo apt update && sudo apt install nodejs"
                    echo "  macOS: brew install node"
                    echo "  Or use Node Version Manager: https://github.com/nvm-sh/nvm"
                    ;;
                "npm")
                    echo "  Usually comes with Node.js"
                    echo "  Ubuntu/Debian: sudo apt install npm"
                    echo "  macOS: included with brew node"
                    ;;
            esac
        done
        exit 1
    fi

    success "All dependencies found"
}

# Main build process
main() {
    info "Starting ad blocker filter list build..."

    # Check for required dependencies
    check_dependencies

    # Setup abp2dnr
    ensure_abp2dnr

    # Download and convert each filter list
    echo "$FILTER_LISTS" | while IFS= read -r line; do
        # Skip empty lines
        [ -z "$line" ] && continue

        # Parse name:url
        name=$(echo "$line" | cut -d: -f1)
        url=$(echo "$line" | cut -d: -f2-)

        # Download filter list
        if download_filter_list "$name" "$url"; then
            # Convert to DNR rules (make lowercase)
            name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
            convert_filter_list "downloads/${name_lower}.txt" "${name_lower}_rules.json"
        fi
    done

    # Extract cosmetic rules from filter lists
    extract_cosmetic_rules

    # Combine all rules
    combine_rules

    # Cleanup temp files in downloads directory
    rm -f downloads/temp_*.json downloads/combined_filters.txt

# Build a single extension
build_extension() {
    local type="$1"           # "ad" or "popup"
    local name="$2"           # "Shot Scraper Ad Blocker"
    local description="$3"    # "Ad blocker for shot-scraper"
    local dir_name="$4"       # "shot-scraper-ad-blocker"
    local rules_file="$5"     # "ad-block-rules.json"
    local cosmetic_file="$6"  # "cosmetic-ad-block-rules.json"
    
    info "Building $dir_name..."
    mkdir -p "../$dir_name"
    echo "DO NOT EDIT - Files in this directory are auto-generated by blocker-shared/build.sh" > "../$dir_name/DO_NOT_EDIT__AUTOGENERATED.txt"
    
    # Copy shared files
    local shared_files=("background.js" "content.js" "content.css" "popup.html" "popup.js")
    for file in "${shared_files[@]}"; do
        if [ -f "$file" ]; then
            cp "$file" "../$dir_name/"
        fi
    done
    
    # Copy specific rules files
    if [ -f "$rules_file" ]; then
        cp "$rules_file" "../$dir_name/rules.json"
    fi
    if [ -f "$cosmetic_file" ]; then
        cp "$cosmetic_file" "../$dir_name/"
    fi
    
    # Create manifest
    cat > "../$dir_name/manifest.json" << EOF
{
  "manifest_version": 3,
  "name": "$name",
  "version": "1.0",
  "description": "$description",
  "permissions": [
    "declarativeNetRequest",
    "declarativeNetRequestFeedback",
    "activeTab"
  ],
  "host_permissions": [
    "<all_urls>"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "declarative_net_request": {
    "rule_resources": [
      {
        "id": "default_rules",
        "enabled": true,
        "path": "rules.json"
      }
    ]
  },
  "web_accessible_resources": [
    {
      "resources": [
        "cosmetic-ad-block-rules.json",
        "cosmetic-popup-block-rules.json"
      ],
      "matches": [
        "<all_urls>"
      ]
    }
  ],
  "action": {
    "default_title": "$name",
    "default_popup": "popup.html"
  },
  "content_scripts": [
    {
      "matches": [
        "<all_urls>"
      ],
      "js": [
        "content.js"
      ],
      "css": [
        "content.css"
      ],
      "run_at": "document_start"
    }
  ]
}
EOF
    
    success "$name built at ../$dir_name/"
}

# Build extension directories
info "Building extension directories..."
build_extension "ad" "Shot Scraper Ad Blocker" "Ad blocker for shot-scraper" "shot-scraper-ad-blocker" "ad-block-rules.json" "cosmetic-ad-block-rules.json"
build_extension "popup" "Shot Scraper Popup Blocker" "Popup and cookie notice blocker for shot-scraper" "shot-scraper-popup-blocker" "popup-block-rules.json" "cosmetic-popup-block-rules.json"

    success "Build complete! Extensions ready to use."
    success "Downloaded files preserved in: downloads/"
}

# Run main function
main "$@"
