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


async def wait_for_dom_ready(page, timeout_ms=10000):
    """Wait for DOM to be ready or timeout"""
    try:
        start_time = time.time()
        timeout_seconds = timeout_ms / 1000

        if Config.verbose:
            click.echo(f"Waiting for DOM ready state (timeout: {timeout_ms}ms)...", err=True)

        check_count = 0
        while time.time() - start_time < timeout_seconds:
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Get current state for verbose logging
            ready_state = await page.evaluate("document.readyState")

            if Config.verbose:
                check_count += 1
                if check_count % 10 == 0:  # Log every 10 checks (roughly every second)
                    click.echo(f"DOM ready check #{check_count}: readyState='{ready_state}', elapsed={elapsed_ms}ms", err=True)

            if ready_state == 'complete':
                if Config.verbose:
                    click.echo(f"DOM ready achieved in {elapsed_ms}ms (readyState: {ready_state})", err=True)
                return True

            await asyncio.sleep(0.1)

        # Timeout reached
        if Config.verbose:
            final_state = await page.evaluate("document.readyState")
            click.echo(f"DOM ready timeout after {timeout_ms}ms (final readyState: {final_state})", err=True)

        return False  # Timed out
    except Exception as e:
        if Config.verbose:
            click.echo(f"DOM ready check failed with exception: {e}", err=True)
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
    try:
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
        
    except Exception as e:
        if Config.verbose:
            click.echo(f"Error detection failed: {e}", err=True)
        return False, None


