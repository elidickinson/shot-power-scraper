"""Core screenshot functionality for shot-scraper"""
import os
import json
import secrets
import textwrap
import tempfile
import pathlib
import base64
import click
import nodriver as uc
from shot_power_scraper.browser import Config
from shot_power_scraper.page_utils import evaluate_js
from shot_power_scraper.utils import filename_for_url, url_or_file_path
from shot_power_scraper.shot_config import ShotConfig


async def _save_screenshot_with_temp_file(page_or_element, format, quality=None, full_page=False):
    """Save screenshot to temporary file and return bytes"""
    suffix = '.jpg' if format == "jpeg" else '.png'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        await _save_screenshot(page_or_element, tmp.name, format, quality, full_page)
        with open(tmp.name, 'rb') as f:
            bytes_data = f.read()
        os.unlink(tmp.name)
        return bytes_data


async def _save_screenshot(page_or_element, output, format, quality=None, full_page=False):
    """Save screenshot to file"""
    # nodriver doesn't support `quality` param
    if format == "jpeg" and quality and not getattr(_save_screenshot, '_quality_warning_shown', False):
        click.echo("Warning: JPEG quality parameter is not supported by nodriver and will be ignored", err=True)
        _save_screenshot._quality_warning_shown = True

    # omit the full_page param when it's not true becaues on a page (tab) the default is false
    # and for an element it doesn't have full_page at all.
    if full_page:
        await page_or_element.save_screenshot(output, format=format, full_page=True)
    else:
        await page_or_element.save_screenshot(output, format=format)


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
        """.format(js_selector_all, klass)
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
    shot_config,
    return_bytes=False,
    use_existing_page=False,
):
    """Take a screenshot based on the provided configuration"""

    if not shot_config.url:
        raise click.ClickException("url is required")

    url = url_or_file_path(shot_config.url, file_exists=_check_and_absolutize)

    if not shot_config.output and not return_bytes:
        shot_config.output = filename_for_url(url, ext="png", file_exists=os.path.exists)

    if not use_existing_page:
        from shot_power_scraper.page_utils import navigate_to_page

        page, response_handler = await navigate_to_page(
            context_or_page,
            shot_config,
        )
    else:
        page = context_or_page

    # Set window size using shot_config dimensions
    await page.set_window_size(shot_config.width, shot_config.height)

    # Note: wait, javascript, wait_for, and trigger_lazy_load
    # are now handled by navigate_to_page() for new pages

    # Determine format based on quality parameter
    format = "jpeg" if shot_config.quality else "png"
    full_page = shot_config.full_page if not shot_config.has_selectors() else True

    if shot_config.js_selectors or shot_config.js_selectors_all:
        # Evaluate JavaScript adding classes we can select on
        (
            js_selector_js,
            extra_selectors,
            extra_selectors_all,
        ) = js_selector_javascript(shot_config.js_selectors, shot_config.js_selectors_all)
        shot_config.selectors.extend(extra_selectors)
        shot_config.selectors_all.extend(extra_selectors_all)
        print(js_selector_js)
        await evaluate_js(page, js_selector_js)

    if shot_config.has_selectors():
        # Use JavaScript to create a box around those elements
        selector_js, selector_to_shoot = selector_javascript(
            shot_config.selectors, shot_config.selectors_all, shot_config.padding
        )
        await evaluate_js(page, selector_js)
        # nodriver element screenshot with selector
        element = await page.select(selector_to_shoot)
        if element:
            if return_bytes:
                return await _save_screenshot_with_temp_file(element, format, shot_config.quality, full_page)
            else:
                if Config.verbose:
                    click.echo(f"Taking element screenshot: {selector_to_shoot}", err=True)
                await _save_screenshot(element, shot_config.output, format, shot_config.quality)
                message = "Screenshot of '{}' on '{}' written to '{}'".format(
                    ", ".join(list(shot_config.selectors) + list(shot_config.selectors_all)), url, shot_config.output
                )
        else:
            raise click.ClickException(f"Could not find element matching selector: {selector_to_shoot}")
    else:
        if shot_config.skip_shot:
            message = "Skipping screenshot of '{}'".format(url)
        else:
            # Whole page
            if return_bytes:
                return await _save_screenshot_with_temp_file(page, format, shot_config.quality, full_page)
            else:
                if Config.verbose:
                    click.echo(f"Taking screenshot (full_page={full_page})", err=True)
                await _save_screenshot(page, shot_config.output, format, shot_config.quality, full_page)
                message = f"Screenshot of '{url}' written to '{shot_config.output}'"

    # Save HTML if requested
    if shot_config.save_html and not return_bytes:
        try:
            # Get the HTML content
            html_content = await page.get_content()

            # Determine HTML filename from screenshot output
            if shot_config.output and shot_config.output != "-":
                # Get the base name without extension
                output_path = pathlib.Path(shot_config.output)
                html_filename = output_path.with_suffix('.html')

                # Write HTML content to file
                with open(html_filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                if not Config.silent:
                    click.echo(f"HTML content saved to '{html_filename}'", err=True)
            else:
                if not Config.silent:
                    click.echo("Cannot save HTML when output is stdout", err=True)

        except Exception as e:
            if not Config.silent:
                click.echo(f"Failed to save HTML: {e}", err=True)

    if not Config.silent:
        click.echo(message, err=True)

    # Always return something for consistency
    return None


async def generate_pdf(page, options):
    """Generate PDF from a page using Chrome DevTools Protocol with standard letter size."""

    # Build CDP print options - always use letter size (8.5x11 inches)
    print_options = {
        "display_header_footer": False,
        "print_background": options.get("print_background"),
        "scale": options.get("scale"),
        "margin_top": 0.4,
        "margin_bottom": 0.4,
        "margin_left": 0.25,
        "margin_right": 0.25,
        "paper_width": 8.5,  # Letter size width
        "paper_height": 11,   # Letter size height
    }



    # Handle media type
    if options.get("media_screen"):
        # Emulate screen media for CSS
        await page.send(uc.cdp.emulation.set_emulated_media(media="screen"))

        # Default CSS for better page break handling
        default_css = """
            /* Avoid breaking inside paragraphs and list items */
            p, li, blockquote, h1, h2, h3, h4, h5, h6 {
                break-inside: avoid;
            }

            /* Try to keep headings with their content */
            h1, h2, h3, h4, h5, h6 {
                break-after: avoid;
            }

            /* Avoid widows and orphans */
            p {
                widows: 3;
                orphans: 3;
            }

        """

        # Combine default CSS with custom CSS if provided
        css_to_inject = default_css
        if options.get("pdf_css"):
            css_to_inject = default_css + "\n" + options.get("pdf_css")

        # Inject the CSS
        await page.evaluate(f"""
            const style = document.createElement('style');
            style.textContent = `{css_to_inject}`;
            document.head.appendChild(style);
        """)

        # Additionally, use JavaScript to convert fixed/sticky elements to static
        await page.evaluate("""
            // Find all elements with computed position fixed or sticky
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => {
                const computed = window.getComputedStyle(el);
                // Skip hidden elements
                if (computed.visibility === 'hidden' || computed.display === 'none') {
                    return;
                }
                if (computed.position === 'fixed' || computed.position === 'sticky') {
                    // Store original position for reference
                    el.dataset.originalPosition = computed.position;
                    // Change to static to prevent repeating on every page
                    el.style.position = 'static';
                    // Remove any top/bottom/left/right values that might cause layout issues
                    el.style.top = 'auto';
                    el.style.bottom = 'auto';
                    el.style.left = 'auto';
                    el.style.right = 'auto';
                }
            });
        """)
    else:
        # Use print media (default)
        await page.send(uc.cdp.emulation.set_emulated_media(media="print"))

        # Inject custom CSS if provided (even for print media)
        if options.get("pdf_css"):
            await page.evaluate(f"""
                const style = document.createElement('style');
                style.textContent = `{options.get("pdf_css")}`;
                document.head.appendChild(style);
            """)

    # Generate PDF using CDP
    result = await page.send(uc.cdp.page.print_to_pdf(**print_options))

    # nodriver returns a tuple: (base64_string, stream_handle)
    # The first element is the base64-encoded PDF data as a string
    pdf_base64_string = result[0]

    # Decode base64 PDF data
    pdf_data = base64.b64decode(pdf_base64_string)

    return pdf_data


async def take_pdf(
    context_or_page,
    shot_config,
    return_bytes=False,
    use_existing_page=False,
):
    """Generate a PDF based on the provided configuration"""

    if not shot_config.url:
        raise click.ClickException("url is required")

    url = url_or_file_path(shot_config.url, file_exists=_check_and_absolutize)

    if not shot_config.output and not return_bytes:
        shot_config.output = filename_for_url(url, ext="pdf", file_exists=os.path.exists)

    if not use_existing_page:
        from shot_power_scraper.page_utils import navigate_to_page

        page, response_handler = await navigate_to_page(
            context_or_page,
            shot_config,
        )
    else:
        page = context_or_page

    # Set window size using shot_config dimensions
    await page.set_window_size(shot_config.width, shot_config.height)

    # Note: wait, javascript, wait_for, and trigger_lazy_load
    # are now handled by navigate_to_page() for new pages

    # Generate PDF
    pdf_options = {
        "landscape": shot_config.pdf_landscape,
        "scale": shot_config.pdf_scale,
        "print_background": shot_config.pdf_print_background,
        "media_screen": shot_config.pdf_media_screen,
        "pdf_css": shot_config.pdf_css,
    }

    if Config.verbose:
        click.echo(f"Generating PDF with options: {pdf_options}", err=True)

    pdf_data = await generate_pdf(page, pdf_options)

    if return_bytes:
        return pdf_data
    else:
        if shot_config.output == "-":
            import sys
            sys.stdout.buffer.write(pdf_data)
            message = f"PDF of '{url}' written to stdout"
        else:
            with open(shot_config.output, "wb") as f:
                f.write(pdf_data)
            message = f"PDF of '{url}' written to '{shot_config.output}'"

    if not Config.silent:
        click.echo(message, err=True)

    return None
