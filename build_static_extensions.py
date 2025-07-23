#!/usr/bin/env python3
"""Build static extension versions - single command to create all blocking extensions"""
import json
import os
import shutil
from pathlib import Path


def check_required_files(base_path):
    """Check that required rule files exist, fail fast if not"""
    required_files = [
        "ad-block-rules.json",
        "popup-block-rules.json", 
        "background.js",
        "content.js",
        "content.css",
        "cosmetic_rules.json"
    ]
    
    missing_files = []
    for filename in required_files:
        if not (base_path / filename).exists():
            missing_files.append(filename)
    
    if missing_files:
        print(f"Error: Missing required files in {base_path}:")
        for filename in missing_files:
            print(f"  - {filename}")
        print(f"\nRun this first to generate rule files:")
        print(f"  cd {base_path} && ./build.sh")
        raise FileNotFoundError(f"Required rule files missing: {missing_files}")


def build_rules_json(base_path, output_path, ad_block=False, popup_block=False):
    """Build a rules.json file with the specified rule categories"""
    combined_rules = []
    rule_id = 1

    if ad_block:
        with open(base_path / "ad-block-rules.json", 'r') as f:
            rules = json.load(f)
        for rule in rules:
            rule["id"] = rule_id
            rule_id += 1
        combined_rules.extend(rules)
        print(f"Added {len(rules)} ad-block rules")

    if popup_block:
        with open(base_path / "popup-block-rules.json", 'r') as f:
            rules = json.load(f)
        for rule in rules:
            rule["id"] = rule_id
            rule_id += 1
        combined_rules.extend(rules)
        print(f"Added {len(rules)} popup-block rules")

    # Limit to Chrome's 30,000 rule limit
    if len(combined_rules) > 30000:
        combined_rules = combined_rules[:30000]
        print(f"Limited rules to 30,000 (Chrome's limit)")

    with open(output_path, 'w') as f:
        json.dump(combined_rules, f, indent=2)

    print(f"Created {len(combined_rules)} total rules in {output_path}")


def copy_shared_files(base_path, target_path):
    """Copy shared files from base extension to target extension"""
    shared_files = [
        'background.js',
        'content.js', 
        'content.css',
        'cosmetic_rules.json',
        'cosmetic-ad-block-rules.json',
        'cosmetic-popup-block-rules.json',
        'popup.html',
        'popup.js'
    ]
    
    for filename in shared_files:
        src = base_path / filename
        if src.exists():
            dst = target_path / filename
            shutil.copy2(src, dst)


def create_manifest(target_path, name, description):
    """Create a manifest.json file for the extension"""
    manifest = {
        "manifest_version": 3,
        "name": name,
        "version": "1.0",
        "description": description,
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
            "rule_resources": [{
                "id": "default_rules",
                "enabled": True,
                "path": "rules.json"
            }]
        },
        "web_accessible_resources": [
            {
                "resources": ["cosmetic_rules.json", "ad-block-rules.json", "popup-block-rules.json"],
                "matches": ["<all_urls>"]
            }
        ],
        "action": {
            "default_title": name,
            "default_popup": "popup.html"
        },
        "content_scripts": [
            {
                "matches": ["<all_urls>"],
                "js": ["content.js"],
                "css": ["content.css"],
                "run_at": "document_start"
            }
        ]
    }
    
    with open(target_path / 'manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2)


def build_extension(extensions_dir, base_path, name, folder_name, description, ad_block, popup_block):
    """Build a single extension"""
    print(f"\n=== Building {name} ===")
    extension_path = extensions_dir / folder_name
    extension_path.mkdir(exist_ok=True)
    
    build_rules_json(base_path, extension_path / "rules.json", ad_block, popup_block)
    copy_shared_files(base_path, extension_path)
    create_manifest(extension_path, name, description)


def main():
    script_dir = Path(__file__).parent
    base_extension_path = script_dir / "extensions" / "shot-scraper-blocker"
    extensions_dir = script_dir / "extensions"
    
    # Fail fast if required files don't exist
    check_required_files(base_extension_path)
    
    # Build all three extensions
    build_extension(extensions_dir, base_extension_path, 
                   "Shot Scraper Ad Blocker", "shot-scraper-ad-blocker",
                   "Ad blocker for shot-scraper", True, False)
    
    build_extension(extensions_dir, base_extension_path,
                   "Shot Scraper Popup Blocker", "shot-scraper-popup-blocker", 
                   "Popup and cookie notice blocker for shot-scraper", False, True)
    
    build_extension(extensions_dir, base_extension_path,
                   "Shot Scraper Complete Blocker", "shot-scraper-combo-blocker",
                   "Ad and popup blocker for shot-scraper", True, True)

    print("\n=== Extension building complete ===")
    print("✓ Three static extensions created")
    print("✓ No temporary directories needed") 
    print("✓ Ready to use with --ad-block and --popup-block flags")


if __name__ == "__main__":
    main()