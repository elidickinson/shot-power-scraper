"""Browser management for shot-power-scraper"""
import json
import click
import nodriver as uc
import pathlib
import tempfile
import shutil
import os


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

    # Add default window position unless user specified one
    if not any(arg.startswith("--window-position") for arg in browser_args_list):
        browser_args_list.append("--window-position=50,50")

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
    config.headless = not (shot_config.interactive or shot_config.headful)
    # config.lang = "en-US"  # Set single language to match legitimate browsers

    # Add --hide-scrollbars when in headless mode
    if config.headless:
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
    browser_obj._temp_extensions = []

    return browser_obj


def customize_ublock_extension(base_path, enable_lists):
    """Copy uBlock extension and enable specific filter lists"""
    temp_ext = tempfile.mkdtemp(prefix="ublock_custom_")

    # Copy entire extension to temp directory
    for item in os.listdir(base_path):
        src = os.path.join(base_path, item)
        dst = os.path.join(temp_ext, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Modify manifest.json to enable requested filter lists
    manifest_path = os.path.join(temp_ext, 'manifest.json')
    with open(manifest_path) as f:
        manifest = json.load(f)

    enabled_count = 0
    for rule in manifest['declarative_net_request']['rule_resources']:
        if rule['id'] in enable_lists:
            rule['enabled'] = True
            enabled_count += 1

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    if Config.verbose:
        click.echo(f"Enabled {enabled_count} additional filter lists: {', '.join(enable_lists)}", err=True)

    return temp_ext


async def setup_blocking_extensions(extensions, ad_block, paywall_block, ublock_lists=None):
    """Setup blocking extensions based on requested flags"""
    base_extensions_path = pathlib.Path(__file__).parent / 'extensions'

    # Load appropriate extensions
    loaded_extensions = []
    temp_extensions = []

    if ad_block:
        # Use uBlock Lite (Manifest V3) for ad blocking
        ad_extension_base = (base_extensions_path / 'ublock-lite-custom').resolve()

        if ublock_lists:
            # Customize extension with specific filter lists
            ad_extension_path = customize_ublock_extension(str(ad_extension_base), ublock_lists)
            temp_extensions.append(ad_extension_path)
            extensions.append(ad_extension_path)
            loaded_extensions.append(f"ad blocking (uBlock Lite + {len(ublock_lists)} custom lists)")
        else:
            extensions.append(str(ad_extension_base))
            loaded_extensions.append("ad blocking (uBlock Lite)")

    if paywall_block:
        paywall_extension_path = (base_extensions_path / 'bypass-paywalls-chrome-clean-master').resolve()
        extensions.append(str(paywall_extension_path))
        loaded_extensions.append("paywall bypass")

    if Config.verbose:
        click.echo(f"Blocking extensions enabled: {' + '.join(loaded_extensions)}", err=True)

    return temp_extensions


async def cleanup_browser(browser_obj):
    """Clean up browser and its temporary user data directory"""
    if browser_obj is None:
        return

    # Stop the browser first (stop() is a regular sync method, not async)
    browser_obj.stop()

    # Clean up temporary extensions
    if hasattr(browser_obj, '_temp_extensions'):
        for temp_ext in browser_obj._temp_extensions:
            shutil.rmtree(temp_ext, ignore_errors=True)
            if Config.verbose:
                click.echo(f"Cleaned up temp extension: {temp_ext}", err=True)

    # Clean up our temporary user data directory
    if hasattr(browser_obj, '_temp_user_data_dir'):
        shutil.rmtree(browser_obj._temp_user_data_dir, ignore_errors=True)
        if Config.verbose:
            click.echo(f"Cleaned up temp profile: {browser_obj._temp_user_data_dir}", err=True)
