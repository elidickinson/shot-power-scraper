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


class Config:
    """Global configuration state"""
    verbose = False
    silent = False
    debug = False


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
                click.warn(f"Warning: Extension path does not exist: {ext_path}", err=True)
                continue
            if not manifest_path.exists():
                click.warn(f"Warning: Extension manifest not found: {manifest_path}", err=True)
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

    # Create temporary user data directory to avoid nodriver cleanup messages
    temp_user_data_dir = tempfile.mkdtemp(prefix="shot_scraper_")

    # Create browser config
    config = uc.Config(user_data_dir=temp_user_data_dir)
    config.headless = not interactive

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
                await page.add_handler("Network.enable", lambda event: None)
                await page.send(uc.cdp.network.set_cookie(**cookie))

    # Store the temp directory on the browser object for later cleanup
    browser_obj._temp_user_data_dir = temp_user_data_dir

    return browser_obj


async def setup_blocking_extensions(extensions, ad_block, popup_block, verbose, silent):
    """Setup blocking extensions based on requested flags"""
    import tempfile
    import shutil

    base_extension_path = os.path.join(os.path.dirname(__file__), '..', 'extensions', 'shot-scraper-blocker')

    if not os.path.exists(base_extension_path):
        if not silent:
            click.echo(f"Warning: Base extension not found at {base_extension_path}", err=True)
        return

    # Create a temporary extension directory
    temp_ext_dir = tempfile.mkdtemp(prefix="shot_scraper_ext_")

    # Copy base extension files
    shutil.copytree(base_extension_path, temp_ext_dir, dirs_exist_ok=True)

    # Create custom rules.json based on selected filters
    rules_path = os.path.join(temp_ext_dir, "rules.json")
    create_filtered_rules(rules_path, ad_block, popup_block, base_extension_path, verbose)

    extensions.append(temp_ext_dir)

    if verbose:
        enabled_filters = []
        if ad_block:
            enabled_filters.append("ad blocking")
        if popup_block:
            enabled_filters.append("popup blocking")
        click.echo(f"Blocking enabled: {', '.join(enabled_filters)}", err=True)


def create_filtered_rules(rules_path, ad_block, popup_block, base_extension_path, verbose):
    """Create a rules.json file with only the selected filter categories"""
    import os

    # Load rules from category files
    combined_rules = []
    rule_id = 1

    # Ad blocking rules
    if ad_block:
        ad_rules_file = os.path.join(base_extension_path, "ad-block-rules.json")
        if os.path.exists(ad_rules_file):
            with open(ad_rules_file, 'r') as f:
                rules = json.load(f)
            for rule in rules:
                rule["id"] = rule_id
                rule_id += 1
            combined_rules.extend(rules)
            if verbose:
                click.echo(f"Added {len(rules)} ad-block rules", err=True)

    # Popup blocking rules
    if popup_block:
        popup_rules_file = os.path.join(base_extension_path, "popup-block-rules.json")
        if os.path.exists(popup_rules_file):
            with open(popup_rules_file, 'r') as f:
                rules = json.load(f)
            for rule in rules:
                rule["id"] = rule_id
                rule_id += 1
            combined_rules.extend(rules)
            if verbose:
                click.echo(f"Added {len(rules)} popup-block rules", err=True)

    # Limit to Chrome's 30,000 rule limit
    if len(combined_rules) > 30000:
        combined_rules = combined_rules[:30000]
        if verbose:
            click.echo(f"Limited rules to 30,000 (Chrome's limit)", err=True)

    # Write combined rules
    with open(rules_path, 'w') as f:
        json.dump(combined_rules, f, indent=2)

    if verbose:
        click.echo(f"Created {len(combined_rules)} total blocking rules", err=True)




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
