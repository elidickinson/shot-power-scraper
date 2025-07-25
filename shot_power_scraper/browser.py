"""Browser management for shot-scraper"""
import asyncio
import json
import os
import click
import nodriver as uc
import pathlib
import tempfile
import shutil


class Config:
    """Global configuration state"""
    verbose = False
    silent = False
    debug = False
    skip = False
    fail = False
    enable_gpu = False






async def create_browser_context(shot_config, extensions=None):
    """Create and configure a browser instance with nodriver"""
    # Convert browser_args tuple to list
    browser_args_list = list(shot_config.browser_args) if shot_config.browser_args else []

    # Note: User agent is now set via CDP with Client Hints metadata, not browser args

    # Add --disable-gpu by default unless --enable-gpu is specified
    if not Config.enable_gpu:
        browser_args_list.append("--disable-gpu")

    # Add extensions via Chrome flags if provided
    if extensions:
        if isinstance(extensions, str):
            extensions = [extensions]

        extension_paths = []

        for ext_path in extensions:
            ext_path = pathlib.Path(ext_path).absolute()
            if Config.verbose:
                click.echo(f"Loading extension: {ext_path}", err=True)


            extension_paths.append(str(ext_path))

        # Use Chrome's --load-extension argument for all extensions
        if extension_paths:
            extension_arg = f"--load-extension={','.join(extension_paths)}"
            browser_args_list.append(extension_arg)

        # Enable extension loading
        if extension_paths:
            browser_args_list.append("--disable-features=DisableLoadExtensionCommandLineSwitch")

    # Create temporary user data directory to avoid nodriver cleanup messages
    temp_user_data_dir = tempfile.mkdtemp(prefix="shot_scraper_")

    # Create browser config
    config = uc.Config(user_data_dir=temp_user_data_dir)
    config.headless = not shot_config.interactive
    # config.lang = "en-US"  # Set single language to match legitimate browsers

    # Add --hide-scrollbars when in headless mode
    if not shot_config.interactive:
        browser_args_list.append("--hide-scrollbars")

    # Add browser args (including extension args)
    for arg in browser_args_list:
        config.add_argument(arg)

    # Show browser args in verbose mode
    if Config.verbose and browser_args_list:
        # click.echo(f"Browser args: {browser_args_list}", err=True)
        click.echo(f"Browser config: {config}", err=True)

    browser_obj = await uc.start(config=config)

    if browser_obj is None:
        raise click.ClickException("Failed to initialize browser; browser_obj is empty")

    # Store user agent config on browser object for later use
    if shot_config.user_agent:
        browser_obj._user_agent = shot_config.user_agent
        if Config.verbose:
            click.echo(f"Will set user agent with Client Hints metadata: {shot_config.user_agent}", err=True)

    # Handle auth state if provided
    if shot_config.auth:
        storage_state = json.load(shot_config.auth)
        # nodriver doesn't have direct storage_state support,
        # but we can set cookies manually
        if "cookies" in storage_state:
            page = await browser_obj.get("about:blank")
            for cookie in storage_state["cookies"]:
                await page.add_handler("Network.enable", lambda event: None)
                await page.send(uc.cdp.network.set_cookie(**cookie))

    # Store the temp directory on the browser object for later cleanup
    browser_obj._temp_user_data_dir = temp_user_data_dir

    return browser_obj


async def setup_blocking_extensions(extensions, ad_block, popup_block, paywall_block):
    """Setup blocking extensions based on requested flags"""
    base_extensions_path = pathlib.Path(__file__).parent.parent / 'extensions'

    # Load appropriate extensions
    loaded_extensions = []

    if ad_block:
        ad_extension_path = (base_extensions_path / 'shot-scraper-ad-blocker').resolve()
        extensions.append(str(ad_extension_path))
        loaded_extensions.append("ad blocking")

    if popup_block:
        popup_extension_path = (base_extensions_path / 'shot-scraper-popup-blocker').resolve()
        extensions.append(str(popup_extension_path))
        loaded_extensions.append("popup blocking")

    if paywall_block:
        paywall_extension_path = (base_extensions_path / 'bypass-paywalls-chrome-clean-master').resolve()
        extensions.append(str(paywall_extension_path))
        loaded_extensions.append("paywall bypass")

    if Config.verbose:
        click.echo(f"Blocking extensions enabled: {' + '.join(loaded_extensions)}", err=True)


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
