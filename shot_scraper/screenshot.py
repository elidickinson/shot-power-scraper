"""Core screenshot functionality for shot-scraper"""
import os
import sys
import time
import json
import secrets
import textwrap
import tempfile
import pathlib
import asyncio
import click
from shot_scraper.browser import Config
from shot_scraper.page_utils import (
    evaluate_js,
    detect_cloudflare_challenge,
    wait_for_cloudflare_bypass,
    wait_for_dom_ready,
    wait_for_condition,
    detect_navigation_error
)
from shot_scraper.annoyance_manager import clear_annoyances
from shot_scraper.utils import filename_for_url, url_or_file_path
from shot_scraper.console_logger import ConsoleLogger


def _check_and_absolutize(filepath):
    """Check if a file exists and return its absolute path"""
    try:
        path = pathlib.Path(filepath)
        if path.exists():
            return path.absolute()
        return False
    except OSError:
        # On Windows, instantiating a Path object on `http://` or `https://` will raise an exception
        return False


def get_viewport(width, height):
    """Get viewport configuration"""
    if width or height:
        return {
            "width": width or 1280,
            "height": height or 720,
        }
    else:
        return {}


def js_selector_javascript(js_selectors, js_selectors_all):
    """Generate JavaScript to add classes for js selectors"""
    extra_selectors = []
    extra_selectors_all = []
    js_blocks = []
    for js_selector in js_selectors:
        klass = f"js-selector-{secrets.token_hex(16)}"
        extra_selectors.append(f".{klass}")
        js_blocks.append(
            textwrap.dedent(
                f"""
        Array.from(
          document.getElementsByTagName('*')
        ).find(el => {js_selector}).classList.add("{klass}");
        """
            )
        )
    for js_selector_all in js_selectors_all:
        klass = f"js-selector-all-{secrets.token_hex(16)}"
        extra_selectors_all.append(f".{klass}")
        js_blocks.append(
            textwrap.dedent(
                """
        Array.from(
          document.getElementsByTagName('*')
        ).filter(el => {}).forEach(el => el.classList.add("{}"));
        """.format(
                    js_selector_all, klass
                )
            )
        )
    js_selector_javascript = "() => {" + "\n".join(js_blocks) + "}"
    return js_selector_javascript, extra_selectors, extra_selectors_all


def selector_javascript(selectors, selectors_all, padding=0):
    """Generate JavaScript to create a box around selected elements"""
    selector_to_shoot = f"shot-scraper-{secrets.token_hex(8)}"
    selector_javascript = textwrap.dedent(
        """
    new Promise(takeShot => {
        let padding = %s;
        let minTop = 100000000;
        let minLeft = 100000000;
        let maxBottom = 0;
        let maxRight = 0;
        let els = %s.map(s => document.querySelector(s));
        // Add the --selector-all elements
        %s.map(s => els.push(...document.querySelectorAll(s)));
        els.forEach(el => {
            let rect = el.getBoundingClientRect();
            if (rect.top < minTop) {
                minTop = rect.top;
            }
            if (rect.left < minLeft) {
                minLeft = rect.left;
            }
            if (rect.bottom > maxBottom) {
                maxBottom = rect.bottom;
            }
            if (rect.right > maxRight) {
                maxRight = rect.right;
            }
        });
        // Adjust them based on scroll position
        let top = minTop + window.scrollY;
        let bottom = maxBottom + window.scrollY;
        let left = minLeft + window.scrollX;
        let right = maxRight + window.scrollX;
        // Apply padding
        top = top - padding;
        bottom = bottom + padding;
        left = left - padding;
        right = right + padding;
        let div = document.createElement('div');
        div.style.position = 'absolute';
        div.style.top = top + 'px';
        div.style.left = left + 'px';
        div.style.width = (right - left) + 'px';
        div.style.height = (bottom - top) + 'px';
        div.style.maxWidth = 'none';
        div.setAttribute('id', %s);
        document.body.appendChild(div);
        setTimeout(() => {
            takeShot();
        }, 300);
    });
    """
        % (
            padding,
            json.dumps(selectors),
            json.dumps(selectors_all),
            json.dumps(selector_to_shoot),
        )
    )
    return selector_javascript, "#" + selector_to_shoot


async def take_shot(
    context_or_page,
    shot,
    return_bytes=False,
    use_existing_page=False,
    log_requests=None,
    log_console=False,
    skip=False,
    fail=False,
    silent=False,
):
    """Take a screenshot based on the provided configuration"""
    url = shot.get("url") or ""
    if not url:
        raise click.ClickException("url is required")

    if skip and fail:
        raise click.ClickException("--skip and --fail cannot be used together")

    url = url_or_file_path(url, file_exists=_check_and_absolutize)

    output = (shot.get("output") or "").strip()
    if not output and not return_bytes:
        output = filename_for_url(url, ext="png", file_exists=os.path.exists)
    quality = shot.get("quality")
    omit_background = shot.get("omit_background")
    wait = shot.get("wait")
    wait_for = shot.get("wait_for")
    padding = shot.get("padding") or 0
    skip_cloudflare_check = shot.get("skip_cloudflare_check", False)
    wait_for_dom_ready_timeout = shot.get("wait_for_dom_ready_timeout", 10000)
    skip_wait_for_dom_ready = shot.get("skip_wait_for_dom_ready", False)

    selectors = list(shot.get("selectors") or [])
    selectors_all = list(shot.get("selectors_all") or [])
    js_selectors = list(shot.get("js_selectors") or [])
    js_selectors_all = list(shot.get("js_selectors_all") or [])
    # If a single 'selector' append to 'selectors' array (and 'js_selectors' etc)
    if shot.get("selector"):
        selectors.append(shot["selector"])
    if shot.get("selector_all"):
        selectors_all.append(shot["selector_all"])
    if shot.get("js_selector"):
        js_selectors.append(shot["js_selector"])
    if shot.get("js_selector_all"):
        js_selectors_all.append(shot["js_selector_all"])

    if not use_existing_page:
        # Create a new tab first to set up console logging before navigation
        if Config.verbose:
            click.echo(f"Creating new page for: {url}", err=True)
        
        # Get a blank page first
        page = await context_or_page.get("about:blank")
        
        # Set up console logging BEFORE navigating to the actual URL
        console_logger = None
        if log_console:
            console_logger = ConsoleLogger(silent=silent)
            await console_logger.setup(page)
            if Config.verbose:
                click.echo("Console logging enabled", err=True)
        
        # Now navigate to the actual URL
        if Config.verbose:
            click.echo(f"Loading page: {url}", err=True)
        await page.get(url)
        if Config.verbose:
            click.echo(f"Page loaded: {url}", err=True)
            
        if log_requests:
            # nodriver doesn't have direct response events like Playwright
            # We can implement this later using CDP if needed
            pass

        # Automatic Cloudflare detection and waiting
        if not skip_cloudflare_check and await detect_cloudflare_challenge(page):
            if not silent:
                click.echo("Detected Cloudflare challenge, waiting for bypass...", err=True)
            success = await wait_for_cloudflare_bypass(page)
            if not success:
                if not silent:
                    click.echo("Warning: Cloudflare challenge may still be active", err=True)

        # Check if page failed to load
        has_error, error_msg = await detect_navigation_error(page, url)
        if has_error:
            full_msg = f"Page failed to load: {error_msg}"
            if skip:
                click.echo(f"{full_msg}, skipping", err=True)
                raise SystemExit
            elif fail:
                raise click.ClickException(full_msg)
            elif not silent:
                click.echo(f"Warning: {full_msg}", err=True)

        # Wait for DOM ready unless explicitly skipped or wait_for is specified
        if not skip_wait_for_dom_ready and not wait_for:
            dom_ready = await wait_for_dom_ready(page, wait_for_dom_ready_timeout)
            if not dom_ready and not silent:
                click.echo(f"DOM ready timeout after {wait_for_dom_ready_timeout}ms", err=True)
    else:
        page = context_or_page
        # Set up console logging for existing page
        console_logger = None
        if log_console:
            console_logger = ConsoleLogger(silent=silent)
            await console_logger.setup(page)

    viewport = get_viewport(shot.get("width"), shot.get("height"))
    if viewport:
        # nodriver doesn't have set_viewport_size, we'll use window size instead
        await page.set_window_size(viewport["width"], viewport["height"])

    # Use explicit full_page if provided, otherwise default to True if no height is specified
    full_page = shot.get("full_page", not shot.get("height"))

    if not use_existing_page:
        # nodriver automatically handles page loading and doesn't return response status
        # We'll assume the page loaded successfully unless we get an exception
        pass

    if wait:
        if Config.verbose:
            click.echo(f"Waiting {wait}ms before processing...", err=True)
        time.sleep(wait / 1000)

    # Clear annoyances after any wait period if enabled
    if shot.get("clear_annoyances", True):
        try:
            await clear_annoyances(page, timeout_seconds=5)
        except Exception as e:
            if Config.verbose:
                click.echo(f"Annoyance clearing failed: {e}", err=True)

    javascript = shot.get("javascript")
    if javascript:
        if Config.verbose:
            click.echo(f"Executing JavaScript: {javascript[:50]}{'...' if len(javascript) > 50 else ''}", err=True)
        await evaluate_js(page, javascript)

    if wait_for:
        await wait_for_condition(page, wait_for)

    screenshot_args = {}
    # Determine format based on quality parameter
    format = "jpeg" if quality else "png"
    if quality:
        screenshot_args.update({"quality": quality, "type": "jpeg"})
    if omit_background:
        screenshot_args.update({"omit_background": True})
    if not return_bytes:
        screenshot_args["path"] = output

    if (
        not selectors
        and not js_selectors
        and not selectors_all
        and not js_selectors_all
    ):
        screenshot_args["full_page"] = full_page

    if js_selectors or js_selectors_all:
        # Evaluate JavaScript adding classes we can select on
        (
            js_selector_js,
            extra_selectors,
            extra_selectors_all,
        ) = js_selector_javascript(js_selectors, js_selectors_all)
        selectors.extend(extra_selectors)
        selectors_all.extend(extra_selectors_all)
        await evaluate_js(page, js_selector_js)

    if selectors or selectors_all:
        # Use JavaScript to create a box around those elements
        selector_js, selector_to_shoot = selector_javascript(
            selectors, selectors_all, padding
        )
        await evaluate_js(page, selector_js)
        try:
            # nodriver element screenshot with selector
            element = await page.select(selector_to_shoot)
            if element:
                if return_bytes:
                    # For bytes output, save to temp file then read
                    # Use appropriate suffix based on format
                    suffix = '.jpg' if format == "jpeg" else '.png'
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                        # Add quality parameter for JPEG format
                        if format == "jpeg" and quality:
                            await page.save_screenshot(tmp.name, format=format, quality=quality, full_page=screenshot_args.get("full_page", True))
                        else:
                            await page.save_screenshot(tmp.name, format=format, full_page=screenshot_args.get("full_page", True))
                        with open(tmp.name, 'rb') as f:
                            bytes_data = f.read()
                        os.unlink(tmp.name)
                        return bytes_data
                else:
                    if Config.verbose:
                        click.echo(f"Taking element screenshot: {selector_to_shoot}", err=True)
                    # Add quality parameter for JPEG format
                    if format == "jpeg" and quality:
                        result = await page.save_screenshot(output, format=format, quality=quality, full_page=screenshot_args.get("full_page", True))
                    else:
                        result = await page.save_screenshot(output, format=format, full_page=screenshot_args.get("full_page", True))
                    # save_screenshot might return None, that's OK
                    message = "Screenshot of '{}' on '{}' written to '{}'".format(
                        ", ".join(list(selectors) + list(selectors_all)), url, output
                    )
            else:
                raise click.ClickException(f"Could not find element matching selector: {selector_to_shoot}")
        except Exception as e:
            raise click.ClickException(
                f"Timed out while waiting for element to become available.\n\n{e}"
            )
    else:
        if shot.get("skip_shot"):
            message = "Skipping screenshot of '{}'".format(url)
        else:
            # Whole page
            if return_bytes:
                # For bytes output, save to temp file then read
                # Use appropriate suffix based on format
                suffix = '.jpg' if format == "jpeg" else '.png'
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    # Add quality parameter for JPEG format
                    if format == "jpeg" and quality:
                        await page.save_screenshot(tmp.name, format=format, quality=quality, full_page=screenshot_args.get("full_page", True))
                    else:
                        await page.save_screenshot(tmp.name, format=format, full_page=screenshot_args.get("full_page", True))
                    with open(tmp.name, 'rb') as f:
                        bytes_data = f.read()
                    os.unlink(tmp.name)
                    return bytes_data
            else:
                if Config.verbose:
                    click.echo(f"Taking screenshot (full_page={screenshot_args.get('full_page', True)})", err=True)
                # Add quality parameter for JPEG format
                if format == "jpeg" and quality:
                    result = await page.save_screenshot(output, format=format, quality=quality, full_page=screenshot_args.get("full_page", True))
                else:
                    result = await page.save_screenshot(output, format=format, full_page=screenshot_args.get("full_page", True))
                # save_screenshot might return None, that's OK
                message = f"Screenshot of '{url}' written to '{output}'"

    # Save HTML if requested
    if shot.get("save_html") and not return_bytes:
        try:
            # Get the HTML content
            html_content = await page.get_content()
            
            # Determine HTML filename from screenshot output
            if output and output != "-":
                # Get the base name without extension
                output_path = pathlib.Path(output)
                html_filename = output_path.with_suffix('.html')
                
                # Write HTML content to file
                with open(html_filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                if not silent:
                    click.echo(f"HTML content saved to '{html_filename}'", err=True)
            else:
                if not silent:
                    click.echo("Cannot save HTML when output is stdout", err=True)
                    
        except Exception as e:
            if not silent:
                click.echo(f"Failed to save HTML: {e}", err=True)

    if not silent:
        click.echo(message, err=True)

    # Always return something for consistency
    return None