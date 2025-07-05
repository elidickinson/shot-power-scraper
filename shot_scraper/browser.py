"""Browser management for shot-scraper"""
import json
import click
import nodriver as uc
from shot_scraper.utils import get_default_user_agent


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

    browser_kwargs = dict(
        headless=not interactive,
        browser_args=browser_args_list
    )

    # Show browser args in verbose mode
    if Config.verbose and browser_args_list:
        click.echo(f"Browser args: {browser_args_list}", err=True)

    browser_obj = await uc.start(**browser_kwargs)

    if browser_obj is None:
        raise click.ClickException("Failed to initialize browser")

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

    return browser_obj