#!/bin/bash
set -e

# Color output functions
info() { echo -e "\033[1;34m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
success() { echo -e "\033[1;32m[SUCCESS]\033[0m $1"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

# Filter lists to download (name:url pairs)
FILTER_LISTS="
EasyPrivacy:https://easylist.to/easylist/easyprivacy.txt
Anti-Adblock-Killer:https://raw.githubusercontent.com/reek/anti-adblock-killer/master/anti-adblock-killer-filters.txt
Fanboy-Annoyances:https://secure.fanboy.co.nz/fanboy-annoyance.txt
"

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
    local filename="${name_lower}.txt"

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

    if node abp2dnr/abp2dnr.js < "$input_file" > "$output_file" 2>/dev/null; then
        local rule_count=$(jq length "$output_file" 2>/dev/null || echo "unknown")
        success "Generated $rule_count rules in $output_file"
    else
        error "Failed to convert $input_file"
        return 1
    fi
}

# Add IDs to rules and combine
combine_rules() {
    info "Combining all rules..."

    local rule_id=1
    local temp_combined="temp_combined.json"

    # Start with empty array
    echo "[]" > "$temp_combined"

    echo "$FILTER_LISTS" | while IFS= read -r line; do
        # Skip empty lines
        [ -z "$line" ] && continue

        # Parse name from line
        name=$(echo "$line" | cut -d: -f1)
        name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
        local rules_file="${name_lower}_rules.json"

        if [ -f "$rules_file" ]; then
            info "Processing $rules_file..."

            # Add IDs and merge with existing rules
            jq --argjson start_id "$rule_id" '
                [to_entries[] | .value.id = ($start_id + .key) | .value]
            ' "$rules_file" > "temp_$rules_file"

            # Update rule_id counter
            local count=$(jq length "$rules_file")
            rule_id=$((rule_id + count))

            # Merge with combined rules
            jq -s '.[0] + .[1]' "$temp_combined" "temp_$rules_file" > "temp_new_combined.json"
            mv "temp_new_combined.json" "$temp_combined"

            rm "temp_$rules_file"
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
            convert_filter_list "${name_lower}.txt" "${name_lower}_rules.json"
        fi
    done

    # Combine all rules
    combine_rules

    # Cleanup temp files
    rm -f *_rules.json *.txt temp_*.json

    success "Build complete! Extension ready to use."
}

# Run main function
main "$@"
