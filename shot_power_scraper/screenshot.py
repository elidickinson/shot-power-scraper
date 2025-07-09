"""Core screenshot functionality for shot-scraper"""
import os
import time
import json
import secrets
import textwrap
import tempfile
import pathlib
import click
from shot_power_scraper.browser import Config
from shot_power_scraper.page_utils import (
    evaluate_js,
    detect_cloudflare_challenge,
    wait_for_cloudflare_bypass,
    wait_for_condition,
    detect_navigation_error
)
from shot_power_scraper.utils import filename_for_url, url_or_file_path
from shot_power_scraper.console_logger import ConsoleLogger
from shot_power_scraper.response_handler import ResponseHandler


class ShotConfig:
    """Configuration for screenshot operations"""
    def __init__(self, shot):
        self.url = shot.get("url") or ""
        self.output = (shot.get("output") or "").strip()
        self.quality = shot.get("quality")
        self.omit_background = shot.get("omit_background")
        self.wait = shot.get("wait")
        self.wait_for = shot.get("wait_for")
        self.padding = shot.get("padding") or 0
        self.skip_cloudflare_check = shot.get("skip_cloudflare_check", False)
        self.timeout = shot.get("timeout") or 30
        self.skip_wait_for_load = shot.get("skip_wait_for_load", False)
        self.javascript = shot.get("javascript")
        self.full_page = shot.get("full_page", not shot.get("height"))
        self.configure_extension = shot.get("configure_extension")
        self.ad_block = shot.get("ad_block", False)
        self.popup_block = shot.get("popup_block", False)
        self.skip_shot = shot.get("skip_shot")
        self.save_html = shot.get("save_html")
        self.width = shot.get("width")
        self.height = shot.get("height")
        
        # Process selectors
        self.selectors = list(shot.get("selectors") or [])
        self.selectors_all = list(shot.get("selectors_all") or [])
        self.js_selectors = list(shot.get("js_selectors") or [])
        self.js_selectors_all = list(shot.get("js_selectors_all") or [])
        
        # Add single selectors to their respective lists
        if shot.get("selector"):
            self.selectors.append(shot["selector"])
        if shot.get("selector_all"):
            self.selectors_all.append(shot["selector_all"])
        if shot.get("js_selector"):
            self.js_selectors.append(shot["js_selector"])
        if shot.get("js_selector_all"):
            self.js_selectors_all.append(shot["js_selector_all"])
    
    def has_selectors(self):
        """Check if any selectors are defined"""
        return bool(self.selectors or self.js_selectors or self.selectors_all or self.js_selectors_all)


async def _save_screenshot_with_temp_file(page, format, quality, full_page):
    """Save screenshot to temporary file and return bytes"""
    suffix = '.jpg' if format == "jpeg" else '.png'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        await _save_screenshot(page, tmp.name, format, quality, full_page)
        with open(tmp.name, 'rb') as f:
            bytes_data = f.read()
        os.unlink(tmp.name)
        return bytes_data


async def _save_screenshot(page, output, format, quality, full_page):
    """Save screenshot to file"""
    if format == "jpeg" and quality:
        await page.save_screenshot(output, format=format, quality=quality, full_page=full_page)
    else:
        await page.save_screenshot(output, format=format, full_page=full_page)


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
    config = ShotConfig(shot)
    
    if not config.url:
        raise click.ClickException("url is required")

    if skip and fail:
        raise click.ClickException("--skip and --fail cannot be used together")

    url = url_or_file_path(config.url, file_exists=_check_and_absolutize)
    
    if not config.output and not return_bytes:
        config.output = filename_for_url(url, ext="png", file_exists=os.path.exists)

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

        # Set up response handler for HTTP status checking
        response_handler = ResponseHandler()
        import nodriver as uc
        page.add_handler(uc.cdp.network.ResponseReceived, response_handler.on_response_received)

        # Now navigate to the actual URL
        if Config.verbose:
            click.echo(f"Loading page: {url}", err=True)
        await page.get(url)

        # Wait for the window load event (all resources including images) unless skipped
        if not config.skip_wait_for_load:
            if Config.verbose:
                click.echo(f"Waiting for window load event...", err=True)

            await page.evaluate(f"""
                new Promise((resolve) => {{
                    if (document.readyState === 'complete') {{
                        resolve();
                    }} else {{
                        window.addEventListener('load', resolve);
                        setTimeout(resolve, {config.timeout * 1000});
                    }}
                }});
            """)

        if log_requests:
            # nodriver doesn't have direct response events like Playwright
            # We can implement this later using CDP if needed
            pass

        # Check HTTP response status
        response_status, response_url = await response_handler.wait_for_response(timeout=5)
        if response_status is not None:
            # Create a response-like object for skip_or_fail function
            class ResponseObj:
                def __init__(self, status, url):
                    self.status = status
                    self.url = url

            from shot_power_scraper.cli import skip_or_fail
            skip_or_fail(ResponseObj(response_status, response_url), skip, fail)

        # Automatic Cloudflare detection and waiting
        if not config.skip_cloudflare_check and await detect_cloudflare_challenge(page):
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

    else:
        page = context_or_page
        # Set up console logging for existing page
        console_logger = None
        if log_console:
            console_logger = ConsoleLogger(silent=silent)
            await console_logger.setup(page)

    viewport = get_viewport(config.width, config.height)
    if viewport:
        # nodriver doesn't have set_viewport_size, we'll use window size instead
        await page.set_window_size(viewport["width"], viewport["height"])

    # Configure blocking extensions if enabled
    if config.configure_extension:
        from shot_power_scraper.cli import configure_blocking_extension
        await configure_blocking_extension(
            page,
            config.ad_block,
            config.popup_block,
            Config.verbose
        )

    if config.wait:
        if Config.verbose:
            click.echo(f"Waiting {config.wait}ms before processing...", err=True)
        time.sleep(config.wait / 1000)

    if config.javascript:
        if Config.verbose:
            click.echo(f"Executing JavaScript: {config.javascript[:50]}{'...' if len(config.javascript) > 50 else ''}", err=True)
        await evaluate_js(page, config.javascript)

    if config.wait_for:
        await wait_for_condition(page, config.wait_for)

    # Determine format based on quality parameter
    format = "jpeg" if config.quality else "png"
    full_page = config.full_page if not config.has_selectors() else True

    if config.js_selectors or config.js_selectors_all:
        # Evaluate JavaScript adding classes we can select on
        (
            js_selector_js,
            extra_selectors,
            extra_selectors_all,
        ) = js_selector_javascript(config.js_selectors, config.js_selectors_all)
        config.selectors.extend(extra_selectors)
        config.selectors_all.extend(extra_selectors_all)
        await evaluate_js(page, js_selector_js)

    if config.has_selectors():
        # Use JavaScript to create a box around those elements
        selector_js, selector_to_shoot = selector_javascript(
            config.selectors, config.selectors_all, config.padding
        )
        await evaluate_js(page, selector_js)
        try:
            # nodriver element screenshot with selector
            element = await page.select(selector_to_shoot)
            if element:
                if return_bytes:
                    return await _save_screenshot_with_temp_file(page, format, config.quality, full_page)
                else:
                    if Config.verbose:
                        click.echo(f"Taking element screenshot: {selector_to_shoot}", err=True)
                    await _save_screenshot(page, config.output, format, config.quality, full_page)
                    message = "Screenshot of '{}' on '{}' written to '{}'".format(
                        ", ".join(list(config.selectors) + list(config.selectors_all)), url, config.output
                    )
            else:
                raise click.ClickException(f"Could not find element matching selector: {selector_to_shoot}")
        except Exception as e:
            raise click.ClickException(
                f"Timed out while waiting for element to become available.\n\n{e}"
            )
    else:
        if config.skip_shot:
            message = "Skipping screenshot of '{}'".format(url)
        else:
            # Whole page
            if return_bytes:
                return await _save_screenshot_with_temp_file(page, format, config.quality, full_page)
            else:
                if Config.verbose:
                    click.echo(f"Taking screenshot (full_page={full_page})", err=True)
                await _save_screenshot(page, config.output, format, config.quality, full_page)
                message = f"Screenshot of '{url}' written to '{config.output}'"

    # Save HTML if requested
    if config.save_html and not return_bytes:
        try:
            # Get the HTML content
            html_content = await page.get_content()

            # Determine HTML filename from screenshot output
            if config.output and config.output != "-":
                # Get the base name without extension
                output_path = pathlib.Path(config.output)
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
