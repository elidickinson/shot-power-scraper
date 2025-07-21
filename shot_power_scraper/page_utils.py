"""Page interaction utilities for shot-scraper"""
import time
import asyncio
import click
from shot_power_scraper.browser import Config
import nodriver as uc


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
            await asyncio.sleep(0.3)  # Check more frequently
        except Exception as e:
            if Config.verbose:
                click.echo(f"Cloudflare bypass check failed: {e}", err=True)
            await asyncio.sleep(0.3)

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
        await asyncio.sleep(0.1)

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
        device_scale_factor=1,
        mobile=False
    ))
    await page  # give it a breather to actually do the emulation
    # await page.scroll_down(1000)
    # await page.sleep(0.5)
    # await page.scroll_up(1000)
    # await page.sleep(0.5)
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


async def navigate_to_page(
    browser_obj,
    shot_config,
):
    """
    Navigate to a page and handle common operations:
    - Page navigation
    - Console logging setup
    - Response handling
    - Cloudflare detection and bypass
    - Navigation error detection
    - Wait and JavaScript execution
    - Lazy load triggering

    Returns: (page, response_handler) tuple
    """
    from shot_power_scraper.console_logger import ConsoleLogger
    from shot_power_scraper.response_handler import ResponseHandler
    from shot_power_scraper.utils import url_or_file_path
    import pathlib

    def _check_and_absolutize(filepath):
        """Check if a file exists and return its absolute path"""
        try:
            path = pathlib.Path(filepath)
            if path.exists():
                return path.absolute()
            return False
        except OSError:
            return False

    # Convert URL to proper format
    url = url_or_file_path(shot_config.url, file_exists=_check_and_absolutize)

    if Config.verbose:
        click.echo(f"Creating new page for: {url}", err=True)

    # Get a blank page first
    page = await browser_obj.get("about:blank")

    # Set up console logging BEFORE navigating
    console_logger = None
    if shot_config.log_console:
        console_logger = ConsoleLogger(silent=Config.silent)
        await console_logger.setup(page)
        if Config.verbose:
            click.echo("Console logging enabled", err=True)

    # Set up response handler for HTTP status checking
    response_handler = ResponseHandler()
    page.add_handler(uc.cdp.network.ResponseReceived, response_handler.on_response_received)

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
                # FIXME: this is duplicated below

    # Automatic Cloudflare detection and waiting
    if not shot_config.skip_cloudflare_check and await detect_cloudflare_challenge(page):
        if not Config.silent:
            click.echo("Detected Cloudflare challenge, waiting for bypass...", err=True)
        success = await wait_for_cloudflare_bypass(page)
        if not success:
            if not Config.silent:
                click.echo("Warning: Cloudflare challenge may still be active", err=True)

    # Check if page failed to load
    # FIXME: not sure this is needed or useful
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
        return page, response_handler, js_result
    else:
        return page, response_handler
