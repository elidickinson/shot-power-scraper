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

# Filter lists to download (name:url pairs)
FILTER_LISTS="
adguard-base-optimized:https://filters.adtidy.org/extension/chromium/filters/2_optimized.txt
adguard-popups-full:https://filters.adtidy.org/windows/filters/19.txt
adguard-cookie-notices-full:https://filters.adtidy.org/windows/filters/18.txt
easylist-newsletters-ubo:https://ublockorigin.github.io/uAssets/thirdparties/easylist-newsletters.txt
Anti-Adblock-Killer:https://raw.githubusercontent.com/reek/anti-adblock-killer/master/anti-adblock-killer-filters.txt
"
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


# Ensure abp2dnr is available
ensure_abp2dnr() {
    if [ ! -d "abp2dnr" ]; then
        info "Cloning abp2dnr from GitHub..."
        git clone https://github.com/kzar/abp2dnr.git

        info "Installing abp2dnr dependencies..."
        cd abp2dnr
        npm install --include=dev
        cd ..
        success "abp2dnr setup complete"
    else
        info "abp2dnr already exists"
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

# Add IDs to rules and combine
# Extract cosmetic rules from filter lists
extract_cosmetic_rules() {
    info "Extracting cosmetic rules from filter lists..."

    # Combine all .txt files into one for cosmetic rules
    local combined_filters="downloads/combined_filters.txt"
    local cosmetic_rules="cosmetic_rules.json"

    # Create downloads directory if it doesn't exist
    mkdir -p downloads

    # Clear previous combined file
    > "$combined_filters"

    # Print statistics header
    echo ""
    info "Filter List Statistics:"
    printf "%-25s %8s %8s %8s %8s %8s\n" "Name" "Total" "Network" "Cosmetic" "Valid" "Unsupported"
    printf "%-25s %8s %8s %8s %8s %8s\n" "----" "-----" "-------" "--------" "-----" "-----------"

    # Combine all downloaded .txt files and show statistics
    echo "$FILTER_LISTS" | while IFS= read -r line; do
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
            local valid=$(echo "$stats" | jq -r '.validCosmeticRules')
            local unsupported=$(echo "$stats" | jq -r '.unsupportedRules')
            
            printf "%-25s %8s %8s %8s %8s %8s\n" "$name" "$total" "$network" "$cosmetic" "$valid" "$unsupported"
            
            info "Adding cosmetic rules from $filter_file..."
            echo "" >> "$combined_filters"
            echo "! === $name ===" >> "$combined_filters"
            cat "$filter_file" >> "$combined_filters"
        fi
    done

    # Extract cosmetic rules using our JavaScript processor
    if [ -f "$combined_filters" ]; then
        node extract_cosmetic_rules.js "$combined_filters" "$cosmetic_rules"
        if [ -f "$cosmetic_rules" ]; then
            success "Cosmetic rules extracted to $cosmetic_rules"
        else
            warn "Failed to extract cosmetic rules"
        fi
    else
        warn "No filter files found for cosmetic rule extraction"
    fi
}

combine_rules() {
    info "Combining all rules..."

    local rule_id=1
    local temp_combined="downloads/temp_combined.json"

    # Create downloads directory if it doesn't exist
    mkdir -p downloads

    # Start with empty array
    echo "[]" > "$temp_combined"

    echo "$FILTER_LISTS" | while IFS= read -r line; do
        # Skip empty lines
        [ -z "$line" ] && continue

        # Parse name from line
        name=$(echo "$line" | cut -d: -f1)
        name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
        local rules_file="downloads/${name_lower}_rules.json"

        if [ -f "$rules_file" ]; then
            info "Processing $rules_file..."

            # Add IDs and merge with existing rules
            jq --argjson start_id "$rule_id" '
                [to_entries[] | .value.id = ($start_id + .key) | .value]
            ' "$rules_file" > "downloads/temp_$rules_file"

            # Update rule_id counter
            local count=$(jq length "$rules_file")
            rule_id=$((rule_id + count))

            # Merge with combined rules
            jq -s '.[0] + .[1]' "$temp_combined" "downloads/temp_$rules_file" > "downloads/temp_new_combined.json"
            mv "downloads/temp_new_combined.json" "$temp_combined"

            rm "downloads/temp_$rules_file"
        fi
    done

    # Limit to 30,000 rules (Chrome's limit)
    local total_rules=$(jq length "$temp_combined")
    if [ "$total_rules" -gt 30000 ]; then
        warn "Generated $total_rules rules, limiting to 30,000"
        jq '.[0:30000]' "$temp_combined" > rules.json
    else
        mv "$temp_combined" rules.json
    fi

    local final_count=$(jq length rules.json)
    success "Generated $final_count blocking rules in rules.json"
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

    success "Build complete! Extension ready to use."
    success "Downloaded files preserved in: downloads/"
    success "Cosmetic rules extracted: cosmetic_rules.json"
    success "Network blocking rules: rules.json"
}

# Run main function
main "$@"
