#!/usr/bin/env python3
"""
Example client for the Shot Scraper API Server

This script demonstrates how to use the API endpoints.

Usage:
    python api_client_example.py
"""

import requests
import json
from pathlib import Path

API_BASE_URL = "http://localhost:8000"

def save_screenshot(response, filename):
    """Save screenshot response to file"""
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✓ Screenshot saved to {filename}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def example_simple_screenshot():
    """Example: Simple screenshot of a website"""
    print("\n1. Simple screenshot example:")
    response = requests.post(
        f"{API_BASE_URL}/shot",
        json={"url": "https://example.com"}
    )
    save_screenshot(response, "example_simple.png")

def example_sized_screenshot():
    """Example: Screenshot with custom viewport size"""
    print("\n2. Sized screenshot example:")
    response = requests.post(
        f"{API_BASE_URL}/shot",
        json={
            "url": "https://example.com",
            "width": 800,
            "height": 600,
            "wait": 1000
        }
    )
    save_screenshot(response, "example_sized.png")

def example_full_page_screenshot():
    """Example: Full page screenshot (default behavior)"""
    print("\n3. Full page screenshot example (default behavior):")
    response = requests.post(
        f"{API_BASE_URL}/shot",
        json={
            "url": "https://example.com",
            "width": 1280
        }
    )
    save_screenshot(response, "example_fullpage.png")

def example_selector_screenshot():
    """Example: Screenshot of specific element"""
    print("\n4. Selector screenshot example:")
    response = requests.post(
        f"{API_BASE_URL}/shot",
        json={
            "url": "https://example.com",
            "selector": "body > div",
            "padding": 20
        }
    )
    save_screenshot(response, "example_selector.png")

def example_javascript_screenshot():
    """Example: Screenshot after running JavaScript"""
    print("\n5. JavaScript screenshot example:")
    response = requests.post(
        f"{API_BASE_URL}/shot",
        json={
            "url": "https://example.com",
            "javascript": "document.body.style.backgroundColor = 'lightblue';",
            "wait": 500
        }
    )
    save_screenshot(response, "example_javascript.png")

def example_quality_screenshot():
    """Example: JPEG screenshot with quality setting"""
    print("\n6. JPEG quality screenshot example:")
    response = requests.post(
        f"{API_BASE_URL}/shot",
        json={
            "url": "https://example.com",
            "quality": 80,
            "width": 1024,
            "height": 768
        }
    )
    save_screenshot(response, "example_quality.jpg")

def check_health():
    """Check if the API server is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✓ API server is healthy")
            return True
        else:
            print(f"✗ API server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API server at", API_BASE_URL)
        print("  Make sure the server is running: python api_server.py")
        return False

def main():
    """Run all examples"""
    print("Shot Scraper API Client Examples")
    print("================================")
    
    # Check if server is running
    if not check_health():
        return
    
    # Create output directory
    output_dir = Path("api_examples")
    output_dir.mkdir(exist_ok=True)
    print(f"\nSaving screenshots to: {output_dir}/")
    
    # Change to output directory
    import os
    os.chdir(output_dir)
    
    # Run examples
    try:
        example_simple_screenshot()
        example_sized_screenshot()
        example_full_page_screenshot()
        example_selector_screenshot()
        example_javascript_screenshot()
        example_quality_screenshot()
        
        print("\n✓ All examples completed successfully!")
        print(f"  Check the {output_dir}/ directory for screenshots")
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")

if __name__ == "__main__":
    main()