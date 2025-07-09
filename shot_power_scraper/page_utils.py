"""Page interaction utilities for shot-scraper"""
import time
import asyncio
import click
from shot_power_scraper.browser import Config


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
            // Handle images with data-src
            const images = document.querySelectorAll('img[data-src]');
            images.forEach(img => {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    delete img.dataset.src;
                    count++;
                }
                // Remove lazy loading attribute
                if (img.loading === 'lazy') {
                    img.removeAttribute('loading');
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
        click.echo(f"Converted {converted_count} data-src attributes to src", err=True)

    # Now scroll through the page to trigger any remaining lazy loading
    start_time = time.time()
    max_wait_seconds = timeout_ms / 1000
    scroll_count = 0

    while time.time() - start_time < max_wait_seconds:
        # Scroll down progressively
        await page.scroll_down(amount=110)  # Scroll by X% of viewport
        scroll_count += 1

        # Give time for content to load
        await asyncio.sleep(0.15)

        # Check if we've reached the bottom
        at_bottom = await page.scroll_bottom_reached()

        if Config.verbose and scroll_count % 5 == 0:
            click.echo(f"Scrolled {scroll_count} times", err=True)

        # If we're at the bottom and height hasn't changed, we're done
        if at_bottom:
            if Config.verbose:
                click.echo(f"Reached bottom of page after {scroll_count} scrolls", err=True)
            break

    # Scroll back to top for consistent screenshot
    await page.scroll_up(amount=10000)  # Scroll to top using nodriver method
    await asyncio.sleep(0.15)

    if Config.verbose:
        elapsed = time.time() - start_time
        click.echo(f"Lazy load triggering completed in {elapsed:.1f}s", err=True)
