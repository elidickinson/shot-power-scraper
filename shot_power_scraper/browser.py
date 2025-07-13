"""Browser management for shot-scraper"""
import asyncio
import json
import os
import click
import nodriver as uc
import pathlib
import tempfile
import shutil
from shot_power_scraper.utils import get_default_user_agent


import logging

# Enable debug logging for nodriver
logging.basicConfig(level=logging.DEBUG)

class Config:
    """Global configuration state"""
    verbose = False
    silent = False


async def create_browser_context(
    auth=None,
    interactive=False,
    devtools=False,
    scale_factor=None,
    browser="chromium",
    browser_args=None,
    user_agent=None,
    timeout=None,
    reduced_motion=False,
    bypass_csp=False,
    auth_username=None,
    auth_password=None,
    record_har_path=None,
    extensions=None,
):
    """Create and configure a browser instance with nodriver"""
    # Convert browser_args tuple to list and add user agent if needed
    browser_args_list = list(browser_args) if browser_args else []
    
    # Use stored default user agent if no explicit user agent is provided
    if not user_agent:
        user_agent = get_default_user_agent()

    # Add user agent to browser args if specified or found in config
    if user_agent:
        browser_args_list.append(f"--user-agent={user_agent}")
    
    # Add extensions if provided
    if extensions:
        if isinstance(extensions, str):
            extensions = [extensions]
        
        extension_paths = []
        for ext_path in extensions:
            ext_path = pathlib.Path(ext_path).absolute()
            if Config.verbose:
                click.echo(f"Loading extension: {ext_path}", err=True)
            # Check if extension path exists and has manifest
            manifest_path = ext_path / "manifest.json"
            if not ext_path.exists():
                click.echo(f"Warning: Extension path does not exist: {ext_path}", err=True)
                continue
            if not manifest_path.exists():
                click.echo(f"Warning: Extension manifest not found: {manifest_path}", err=True)
                continue
            if Config.verbose:
                click.echo(f"Extension manifest found: {manifest_path}", err=True)
            extension_paths.append(str(ext_path))
        
        # Use Chrome's --load-extension argument with proper flags
        if extension_paths:
            # Add the load extension argument
            extension_arg = f"--load-extension={','.join(extension_paths)}"
            browser_args_list.append(extension_arg)
            
            # Only allow our extensions (disable built-in ones)
            for ext_path in extension_paths:
                browser_args_list.append(f"--disable-extensions-except-{ext_path}")
            
            # Enable extension loading from command line
            browser_args_list.append("--disable-features=DisableLoadExtensionCommandLineSwitch")
            
            if Config.verbose:
                click.echo(f"Added extension arguments: {extension_arg}", err=True)
    
    # Create temporary user data directory to avoid nodriver cleanup messages
    temp_user_data_dir = tempfile.mkdtemp(prefix="shot_scraper_")
    
    # Create browser config
    config = uc.Config(
        user_data_dir=temp_user_data_dir, 
        no_sandbox=True
    )
    config.headless = not interactive
    
    # Add container-friendly flags
    browser_args_list.append("--disable-setuid-sandbox")
    browser_args_list.append("--disable-dev-shm-usage")
    
    # Add --hide-scrollbars when in headless mode
    if not interactive:
        browser_args_list.append("--hide-scrollbars")
    
    # Add browser args (including extension args)
    for arg in browser_args_list:
        config.add_argument(arg)

    # Show browser args in verbose mode
    if Config.verbose and browser_args_list:
        click.echo(f"Browser args: {browser_args_list}", err=True)

    browser_obj = await uc.start(config=config)

    if browser_obj is None:
        raise click.ClickException("Failed to initialize browser")
    
    # Give extensions time to load if any were specified
    if extensions:
        if Config.verbose:
            click.echo("Waiting for extensions to load...", err=True)
        await asyncio.sleep(2.5)

    # Handle auth state if provided
    if auth:
        storage_state = json.load(auth)
        # nodriver doesn't have direct storage_state support,
        # but we can set cookies manually
        if "cookies" in storage_state:
            page = await browser_obj.get("about:blank")
            for cookie in storage_state["cookies"]:
                try:
                    await page.add_handler("Network.enable", lambda event: None)
                    await page.send(uc.cdp.network.set_cookie(**cookie))
                except Exception:
                    # Ignore cookie setting errors for now
                    pass

    # Store the temp directory on the browser object for later cleanup
    browser_obj._temp_user_data_dir = temp_user_data_dir
    
    return browser_obj


async def cleanup_browser(browser_obj):
    """Clean up browser and its temporary user data directory"""
    if browser_obj is None:
        return
        
    # Stop the browser first (stop() is a regular sync method, not async)
    browser_obj.stop()
    
    # Clean up our temporary user data directory
    if hasattr(browser_obj, '_temp_user_data_dir'):
        shutil.rmtree(browser_obj._temp_user_data_dir, ignore_errors=True)
        if Config.verbose:
            click.echo(f"Cleaned up temp profile: {browser_obj._temp_user_data_dir}", err=True)