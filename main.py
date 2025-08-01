#!/usr/bin/env python3
"""
Simple runner script for shot-power-scraper without installation.

Usage:
    python3 main.py --help
    python3 main.py https://example.com -o screenshot.png
    python3 main.py multi config.yml
"""
import sys
import os
import faulthandler

faulthandler.enable()

# Add the current directory to Python path so we can import shot_power_scraper
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import and run the CLI
try:
    from shot_power_scraper.cli import cli
    
    if __name__ == '__main__':
        cli()
        
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("\nMissing dependencies. Please install:")
    print("pip install click PyYAML nodriver click-default-group")
    sys.exit(1)
except Exception as e:
    print(f"Error running shot-power-scraper: {e}")
    sys.exit(1)
