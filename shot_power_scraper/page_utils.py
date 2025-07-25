"""Page interaction utilities for shot-scraper"""
import time
import asyncio
import platform
import re
import click
from shot_power_scraper.browser import Config
import nodriver as uc


def generate_user_agent_metadata(user_agent_string):
    """Generate realistic UserAgentMetadata for Client Hints based on user agent string"""

    # Parse Chrome version from user agent
    chrome_match = re.search(r'Chrome/(\d+)\.(\d+)\.(\d+)\.(\d+)', user_agent_string)
    if not chrome_match:
        return None

    major_version = chrome_match.group(1)
    minor_version = chrome_match.group(2)
    build_version = chrome_match.group(3)
    patch_version = chrome_match.group(4)
    full_version = f"{major_version}.{minor_version}.{build_version}.{patch_version}"

    # Detect platform from user agent
    is_mobile = 'Mobile' in user_agent_string or 'Android' in user_agent_string

    if 'Windows NT' in user_agent_string:
        # Windows platform
        platform_name = "Windows"

        # Extract Windows version
        windows_match = re.search(r'Windows NT (\d+)\.(\d+)', user_agent_string)
        if windows_match:
            nt_major = windows_match.group(1)
            nt_minor = windows_match.group(2)
            platform_version = f"{nt_major}.{nt_minor}.0"
        else:
            platform_version = "10.0.0"

        # Detect architecture
        architecture = "x86" if "WOW64" in user_agent_string or "Win64" in user_agent_string else "x86"
        if "x64" in user_agent_string or "Win64" in user_agent_string:
            architecture = "x86"

        bitness = "64"
        wow64 = "WOW64" in user_agent_string
        model = ""

    elif 'Mac OS X' in user_agent_string or 'macOS' in user_agent_string:
        # macOS platform
        platform_name = "macOS"

        # Extract macOS version
        mac_match = re.search(r'Mac OS X (\d+)[_.](\d+)[_.]?(\d+)?', user_agent_string)
        if mac_match:
            mac_major = mac_match.group(1)
            mac_minor = mac_match.group(2)
            mac_patch = mac_match.group(3) or "0"
            platform_version = f"{mac_major}.{mac_minor}.{mac_patch}"
        else:
            platform_version = "13.0.0"

        # Mac architecture detection
        architecture = "arm" if "arm64" in user_agent_string else "x86"
        bitness = "64"
        wow64 = False
        model = ""

    elif 'Android' in user_agent_string:
        # Android platform
        platform_name = "Android"

        # Extract Android version
        android_match = re.search(r'Android (\d+)(?:\.(\d+))?(?:\.(\d+))?', user_agent_string)
        if android_match:
            android_major = android_match.group(1)
            android_minor = android_match.group(2) or "0"
            android_patch = android_match.group(3) or "0"
            platform_version = f"{android_major}.{android_minor}.{android_patch}"
        else:
            platform_version = "10.0.0"

        architecture = "arm"
        bitness = "64"
        wow64 = False

        # Extract device model if available
        model_match = re.search(r';\s*([^)]+)\s*\)', user_agent_string)
        model = model_match.group(1).strip() if model_match else ""

    else:
        # Default to Linux
        platform_name = "Linux"
        platform_version = "0.0.0"
        architecture = "x86"
        bitness = "64"
        wow64 = False
        model = ""

    # Generate brands list (matches what real Chrome reports)
    brands = [
        uc.cdp.emulation.UserAgentBrandVersion(brand="Not)A;Brand", version="8"),
        uc.cdp.emulation.UserAgentBrandVersion(brand="Chromium", version=major_version),
        uc.cdp.emulation.UserAgentBrandVersion(brand="Google Chrome", version=major_version)
    ]

    # Full version list for Sec-CH-UA-Full-Version-List
    full_version_list = [
        uc.cdp.emulation.UserAgentBrandVersion(brand="Not)A;Brand", version="8.0.0.0"),
        uc.cdp.emulation.UserAgentBrandVersion(brand="Chromium", version=full_version),
        uc.cdp.emulation.UserAgentBrandVersion(brand="Google Chrome", version=full_version)
    ]

    # Create UserAgentMetadata
    metadata = uc.cdp.emulation.UserAgentMetadata(
        platform=platform_name,
        platform_version=platform_version,
        architecture=architecture,
        model=model,
        mobile=is_mobile,
        brands=brands,
        full_version_list=full_version_list,
        full_version=full_version,
        bitness=bitness,
        wow64=wow64 if platform_name == "Windows" else None
    )

    return metadata


async def create_tab_context(browser_obj, shot_config):
    """
    Create and configure a new tab context with one-time setup.
    
    Handles tab creation, window sizing, user agent configuration,
    script injection, console logging, and network response handling.
    
    Returns: configured tab at about:blank ready for navigation
    """
    from shot_power_scraper.console_logger import ConsoleLogger
    from shot_power_scraper.response_handler import ResponseHandler
    
    if Config.verbose:
        click.echo(f"Setting up tab context", err=True)

    # Create blank page and set window size
    page = await browser_obj.get("about:blank")
    await page.set_window_size(shot_config.width, shot_config.height)

    # Configure user agent with Client Hints metadata
    if hasattr(browser_obj, '_user_agent') and browser_obj._user_agent:
        metadata = generate_user_agent_metadata(browser_obj._user_agent)
        await page.send(uc.cdp.emulation.set_user_agent_override(
            user_agent=browser_obj._user_agent,
            user_agent_metadata=metadata
        ))
        if Config.verbose:
            click.echo(f"Applied user agent with Client Hints: {browser_obj._user_agent}", err=True)

    # Enable page domain and inject navigator.languages override
    await page.send(uc.cdp.page.enable())
    await page.send(uc.cdp.page.add_script_to_evaluate_on_new_document("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US']
        });
    """))

    # Set up console logging if requested
    if shot_config.log_console:
        console_logger = ConsoleLogger(silent=Config.silent)
        await console_logger.setup(page)
        if Config.verbose:
            click.echo("Console logging enabled", err=True)

    # Set up HTTP response monitoring
    response_handler = ResponseHandler()
    await page.send(uc.cdp.network.enable())
    page.add_handler(uc.cdp.network.ResponseReceived, response_handler.on_response_received)
    page._response_handler = response_handler
    
    if Config.verbose:
        click.echo(f"Tab context setup complete", err=True)
    
    return page


async def navigate_to_url(page, shot_config):
    """
    Navigate a configured tab to a target URL and handle post-navigation logic.
    
    Expects a tab that has already been configured with create_tab_context().
    Handles navigation, load waiting, error checking, Cloudflare bypass,
    JavaScript execution, and post-navigation processing.
    
    Returns: response_handler (page._response_handler should already be set)
    """
    from shot_power_scraper.utils import url_or_file_path
    
    # Convert URL to proper format
    url = url_or_file_path(shot_config.url)
    
    # Get the response handler that was set up during tab context creation
    response_handler = page._response_handler

    # Navigate to the actual URL
    if Config.verbose:
        click.echo(f"Loading page: {url}", err=True)
    await page.get(url)
    await page
    
    # Wait for window load event unless skipped
    if not shot_config.skip_wait_for_load:
        if Config.verbose:
            click.echo(f"Waiting for window load event...", err=True)

        timeout = shot_config.timeout
        await page.evaluate(f"""
            new Promise((resolve) => {{
                if (document.readyState === 'complete') {{
                    resolve();
                }} else {{
                    window.addEventListener('load', resolve);
                    setTimeout(resolve, {timeout * 1000});
                }}
            }});
        """)
        if Config.verbose:
            click.echo(f"Done waiting for window load", err=True)

    # Check HTTP response status
    response_status, response_url = await response_handler.wait_for_response(timeout=5)
    if response_status is not None:
        if str(response_status)[0] in ("4", "5"):
            if Config.skip:
                click.echo(
                    f"{response_status} error for {url}, skipping",
                    err=True,
                )
                # Exit with a 0 status code
                raise SystemExit  # TODO: this probably breaks `multi`
            elif Config.fail:
                raise click.ClickException(f"{response_status} error for {url}")

    # Automatic Cloudflare detection and waiting
    if not shot_config.skip_cloudflare_check and await detect_cloudflare_challenge(page):
        if not Config.silent:
            click.echo("Detected Cloudflare challenge, waiting for bypass...", err=True)
        success = await wait_for_cloudflare_bypass(page)
        if not success:
            if not Config.silent:
                click.echo("Warning: Cloudflare challenge may still be active", err=True)

    # Check if page failed to load
    has_error, error_msg = await detect_navigation_error(page, url)
    if has_error:
        full_msg = f"Page failed to load: {error_msg}"
        if Config.skip:
            click.echo(f"{full_msg}, skipping", err=True)
            raise SystemExit
        elif Config.fail:
            raise click.ClickException(full_msg)
        elif not Config.silent:
            click.echo(f"Warning: {full_msg}", err=True)

    # Wait if specified
    wait_ms = shot_config.wait
    if wait_ms:
        if Config.verbose:
            click.echo(f"Waiting {wait_ms}ms before processing...", err=True)
        await asyncio.sleep(wait_ms / 1000)

    # Execute JavaScript if provided
    js_result = None
    javascript = shot_config.javascript
    if javascript:
        if Config.verbose:
            click.echo(f"Executing JavaScript: {javascript[:50]}{'...' if len(javascript) > 50 else ''}", err=True)
        js_result = await evaluate_js(page, javascript)

    # Wait for condition if specified
    wait_for = shot_config.wait_for
    if wait_for:
        timeout_seconds = shot_config.timeout
        await wait_for_condition(page, wait_for, timeout_seconds)

    # Trigger lazy load if requested
    if shot_config.trigger_lazy_load:
        await trigger_lazy_load(page)

    # Apply viewport expansion to fix intersection observers when blocking is enabled
    elif shot_config.popup_block or shot_config.ad_block:
        if Config.verbose:
            click.echo("Applying viewport expansion to fix intersection observers...", err=True)

        # Get viewport width and document height
        viewport_width = await page.evaluate("window.innerWidth")
        document_height = await page.evaluate("document.documentElement.scrollHeight")

        # Use document height, minimum 10000px
        viewport_height = max(document_height, 10000)

        await page.send(uc.cdp.emulation.set_device_metrics_override(
            width=viewport_width,
            height=viewport_height,
            device_scale_factor=1,
            mobile=False
        ))

        # Wait a moment for lazy loading to trigger
        await page.sleep(0.5)

        # Clear the override to restore normal viewport
        await page.send(uc.cdp.emulation.clear_device_metrics_override())
        await page.sleep()

    if shot_config.return_js_result:
        return response_handler, js_result
    else:
        return response_handler


async def evaluate_js(page, javascript):
    """Safely evaluate JavaScript on a page"""
    try:
        return await page.evaluate(javascript)
    except Exception as error:
        raise click.ClickException(str(error))


async def detect_cloudflare_challenge(page):
    """Detect if the current page is showing a Cloudflare challenge"""
    try:
        return await page.evaluate("""
        (() => {
            return document.title === 'Just a moment...' ||
                   !!window._cf_chl_opt ||
                   !!document.querySelector('script[src*="/cdn-cgi/challenge-platform/"]') ||
                   (!!document.querySelector('meta[http-equiv="refresh"]') && document.title.includes('Just a moment'));
        })()
        """)
    except Exception:
        return False


async def wait_for_cloudflare_bypass(page, max_wait_seconds=8):
    """Wait for Cloudflare challenge to complete"""
    start_time = time.time()

    if Config.verbose:
        click.echo(f"Waiting for Cloudflare challenge bypass (max {max_wait_seconds}s)...", err=True)

    check_count = 0
    while time.time() - start_time < max_wait_seconds:
        try:
            elapsed_seconds = time.time() - start_time
            check_count += 1

            cf_detected = await detect_cloudflare_challenge(page)

            if Config.verbose and not Config.silent and check_count % 10 == 0:  # Log every 10 checks
                click.echo(f"Cloudflare check #{check_count}: challenge_detected={cf_detected}, elapsed={elapsed_seconds:.1f}s", err=True)

            if not cf_detected:
                # Wait minimum 1 second for page stability after challenge clears
                if elapsed_seconds >= 1:
                    if Config.verbose:
                        click.echo(f"Cloudflare challenge bypassed in {elapsed_seconds:.1f}s", err=True)
                    return True
            await page.sleep(0.3)  # Check more frequently
        except Exception as e:
            if Config.verbose:
                click.echo(f"Cloudflare bypass check failed: {e}", err=True)
            await page.sleep(0.3)

    if Config.verbose:
        click.echo(f"Cloudflare bypass timeout after {max_wait_seconds}s", err=True)
    return False




async def wait_for_condition(page, wait_for_expression, timeout_seconds=30):
    """Wait for a JavaScript condition to become true"""
    if Config.verbose:
        click.echo(f"Waiting for condition: {wait_for_expression}", err=True)

    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        result = await page.evaluate(wait_for_expression)
        if result:
            if Config.verbose:
                elapsed = int((time.time() - start_time) * 1000)
                click.echo(f"Wait condition met after {elapsed}ms", err=True)
            return True
        await page.sleep(0.1)

    raise click.ClickException(f"Timeout waiting for condition: {wait_for_expression}")





async def detect_navigation_error(page, expected_url):
    """Detect if page navigation failed (DNS errors, network failures, etc.)"""
    current_url = page.url
    page_title = await page.evaluate("document.title")
    body_text = await page.evaluate("document.body ? document.body.innerText.trim() : ''")

    # Check for Chrome error pages
    if current_url.startswith('chrome-error://'):
        return True, f"Chrome error page: {current_url}"

    # Check for Chrome error page pattern
    if (len(body_text) < 200 and
        page_title == current_url.replace('https://', '').replace('http://', '').split('/')[0] and
        "This site can't be reached" in body_text):
        return True, "DNS or network error"

    return False, None


async def trigger_lazy_load(page, timeout_ms=5000):
    """Trigger lazy-loaded content by scrolling and converting data-src attributes"""
    if Config.verbose:
        click.echo("Triggering lazy-loaded content...", err=True)

    # First, convert all data-src to src and remove loading="lazy"
    converted_count = await page.evaluate("""
        (() => {
            let count = 0;
            // Handle lazy loaded images (some have loading as a JS property not an attribute)
            const images = document.querySelectorAll('img');
            images.forEach(img => {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    delete img.dataset.src;
                    count++;
                }
                // Remove lazy loading attribute
                if (img.loading === 'lazy') {
                    img.loading = 'eager';
                    img.decode(); // try to force loading right now
                    count++;
                }
            });

            // Handle other elements that might have data-src (like iframes)
            const otherElements = document.querySelectorAll('[data-src]:not(img)');
            otherElements.forEach(el => {
                if (el.dataset.src) {
                    el.src = el.dataset.src;
                    delete el.dataset.src;
                    count++;
                }
            });

            return count;
        })()
    """)

    if Config.verbose and converted_count > 0:
        click.echo(f"Converted {converted_count} lazy load attributes", err=True)

    await page.scroll_down(1000)
    await page.sleep(0.1)
    await page.scroll_up(1000)
    await page.sleep(0.1)

    # Try CDP-based viewport scaling to trigger image loading in headless mode. I had strange problems
    # triggering loading=lazy images when in headless. Both scrolling and rewriting img attributes
    # didn't seem to work. Something peculiar to --headless (or --headless=new perhaps)
    if Config.verbose:
        click.echo(f"Attempting viewport scaling trick for headless image loading...", err=True)
    viewport_width = await page.evaluate("window.innerWidth")
    # This makes Chrome think the viewport is very tall
    await page.send(uc.cdp.emulation.set_device_metrics_override(
        width=viewport_width,
        height=10000,  # Very tall viewport
        device_scale_factor=0.5,  # scaled down
        mobile=False
    ))
    await page  # give it a breather to actually do the emulation
    # Wait for all images to load with timeout
    max_wait = 5  # seconds (TODO: don't hardcode this)
    start_wait = time.time()
    while time.time() - start_wait < max_wait:
        all_loaded = await page.evaluate("""
            Array.from(document.querySelectorAll('img[src]')).every(img => img.complete)
        """)
        if all_loaded:
            if Config.verbose:
                click.echo(f"All images loaded after {time.time() - start_wait:.2f}s", err=True)
            break

        await page.sleep(0.1)

    # Clear the override to restore normal viewport
    await page.send(uc.cdp.emulation.clear_device_metrics_override())
    await page
    if Config.verbose:
        click.echo(f"Lazy load complete", err=True)


