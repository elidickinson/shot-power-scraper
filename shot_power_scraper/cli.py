import subprocess
import sys
import time
import json
import os
import pathlib
from click_default_group import DefaultGroup
import yaml
import click
import nodriver as uc
import asyncio

from shot_power_scraper.utils import filename_for_url, load_github_script, url_or_file_path, set_default_user_agent, get_default_ad_block, get_default_popup_block
from shot_power_scraper.browser import Config, create_browser_context, cleanup_browser, setup_blocking_extensions
from shot_power_scraper.screenshot import take_shot, take_pdf, get_viewport

BROWSERS = ("chromium", "chrome", "chrome-beta")


async def run_with_browser_cleanup(coro):
    """Run an async function and give nodriver time to cleanup afterwards."""
    import warnings

    # Suppress harmless cleanup warnings from nodriver
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",
                              message=".*Task was destroyed but it is pending.*",
                              category=RuntimeWarning)

        result = await coro
        await asyncio.sleep(0.1)  # Give nodriver time to cleanup background processes
        return result


def run_async(coro):
    """Run an async coroutine using uc.loop() as in nodriver examples."""
    # Use nodriver's event loop as recommended in their docs
    loop = uc.loop()
    return loop.run_until_complete(coro)


def resolve_blocking_config(ad_block, popup_block):
    """Resolve ad_block and popup_block values from config if not explicitly set."""
    if ad_block is None:
        ad_block = get_default_ad_block()
    if popup_block is None:
        popup_block = get_default_popup_block()
    return ad_block, popup_block






# Common command execution pattern
async def run_browser_command(command_func, browser_kwargs=None, extensions_needed=False, **kwargs):
    """Unified command execution pattern that handles browser setup/cleanup"""
    try:
        extensions = []
        if extensions_needed:
            ad_block = kwargs.get('ad_block', False)
            popup_block = kwargs.get('popup_block', False)
            verbose = kwargs.get('verbose', False)
            silent = kwargs.get('silent', False)
            await setup_blocking_extensions(extensions, ad_block, popup_block, verbose, silent)

        # Create browser with common parameters
        browser_kwargs = browser_kwargs or {}
        if extensions:
            browser_kwargs['extensions'] = extensions

        browser_obj = await create_browser_context(**browser_kwargs)
        if not browser_obj:
            raise click.ClickException("Browser initialization failed")

        # Execute the command
        result = await command_func(browser_obj, **kwargs)

        return result
    finally:
        if 'browser_obj' in locals():
            await cleanup_browser(browser_obj)


def setup_common_config(verbose, debug, silent):
    """Setup common configuration used by all commands"""
    Config.verbose = verbose
    Config.silent = silent
    Config.debug = debug

    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Small utility functions stay here
def console_log(msg):
    click.echo(msg, err=True)


def _check_and_absolutize(filepath):
    path = pathlib.Path(filepath)
    if path.exists():
        return path.absolute()
    return False




def skip_or_fail(status_code, url, skip, fail):
    if skip and fail:
        raise click.ClickException("--skip and --fail cannot be used together")
    if str(status_code)[0] in ("4", "5"):
        if skip:
            click.echo(
                f"{status_code} error for {url}, skipping",
                err=True,
            )
            # Exit with a 0 status code
            raise SystemExit
        elif fail:
            raise click.ClickException(f"{status_code} error for {url}")


def scale_factor_options(fn):
    """Scale factor options for backwards compatibility"""
    click.option("--retina", is_flag=True, help="Use device scale factor of 2. Cannot be used together with '--scale-factor'.")(fn)
    click.option("--scale-factor", type=float, help="Device scale factor. Cannot be used together with '--retina'.")(fn)
    return fn


def normalize_scale_factor(retina, scale_factor):
    """Normalize scale factor from retina flag or explicit value"""
    if retina and scale_factor:
        raise click.ClickException("--retina and --scale-factor cannot be used together")
    if scale_factor is not None and scale_factor <= 0.0:
        raise click.ClickException("--scale-factor must be positive")
    if retina:
        scale_factor = 2
    return scale_factor


# Consolidated option decorators
def common_shot_options(fn):
    """Complete set of options for screenshot commands"""
    # Output options
    click.option("--verbose", is_flag=True, help="Enable verbose logging to stdout")(fn)
    click.option("--debug", is_flag=True, hidden=True, help="Enable debug logging for nodriver")(fn)
    click.option("--silent", is_flag=True, help="Do not output any messages")(fn)
    click.option("--log-console", "--console-log", is_flag=True, help="Write console.log() to stderr")(fn)

    # Page interaction options
    click.option("--bypass-csp", is_flag=True, help="Bypass Content-Security-Policy")(fn)
    click.option("--trigger-lazy-load", is_flag=True,
                help="Automatically trigger lazy-loaded images by scrolling and converting data-src attributes")(fn)
    click.option("--skip-cloudflare-check", is_flag=True,
                help="Skip Cloudflare challenge detection and waiting")(fn)

    # Wait options
    click.option("--skip-wait-for-load", is_flag=True, help="Skip waiting for window load event")(fn)
    click.option("--timeout", type=int, help="Wait this many milliseconds before failing")(fn)
    click.option("--wait-for", help="Wait until this JS expression returns true")(fn)
    click.option("--wait", type=int, default=250,
                help="Wait this many milliseconds before taking the screenshot (default: 250)")(fn)

    # Browser options
    click.option("--reduced-motion", is_flag=True, help="Emulate 'prefers-reduced-motion' media feature")(fn)
    click.option("--user-agent", help="User-Agent header to use")(fn)
    click.option("browser_args", "--browser-arg", multiple=True,
                help="Additional arguments to pass to the browser")(fn)
    click.option("--browser", "-b", default="chromium", type=click.Choice(BROWSERS, case_sensitive=False),
                help="Which browser to use")(fn)

    # Authentication options
    click.option("--auth-password", help="Password for HTTP Basic authentication")(fn)
    click.option("--auth-username", help="Username for HTTP Basic authentication")(fn)
    click.option("-a", "--auth", type=click.File("r"),
                help="Path to JSON authentication context file")(fn)

    # Error handling options
    click.option("--skip", is_flag=True, help="Skip pages that return HTTP errors")(fn)
    click.option("--fail", is_flag=True,
                help="Fail with an error code if a page returns an HTTP error")(fn)

    # Blocking options
    click.option("--popup-block/--no-popup-block", "--block-popups/--no-block-popups", default=None,
                help="Enable/disable popup blocking (overrides config file setting)")(fn)
    click.option("--ad-block/--no-ad-block", default=None,
                help="Enable ad blocking using built-in filter lists")(fn)

    return fn


def simple_browser_options(fn):
    """Simplified browser options for auth and config commands"""
    click.option("--reduced-motion", is_flag=True, help="Emulate 'prefers-reduced-motion' media feature")(fn)
    click.option("--user-agent", help="User-Agent header to use")(fn)
    click.option("browser_args", "--browser-arg", multiple=True,
                help="Additional arguments to pass to the browser")(fn)
    click.option("--browser", "-b", default="chromium", type=click.Choice(BROWSERS, case_sensitive=False),
                help="Which browser to use")(fn)
    return fn


@click.group(
    cls=DefaultGroup,
    default="shot",
    default_if_no_args=True,
    context_settings=dict(help_option_names=["--help"]),
)
@click.version_option()
def cli():
    "Tools for taking automated screenshots"
    pass


@cli.command()
@click.argument("url")
@click.option("--width", type=int, help="Width of browser window, defaults to 1280", default=1280)
@click.option("--height", type=int, help="Height of browser window and shot - defaults to the full height of the page")
@click.option("-o", "--output", type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True))
@click.option("selectors", "-s", "--selector", help="Take shot of first element matching this CSS selector", multiple=True)
@click.option("selectors_all", "--selector-all", help="Take shot of all elements matching this CSS selector", multiple=True)
@click.option("js_selectors", "--js-selector", help="Take shot of first element matching this JS (el) expression", multiple=True)
@click.option("js_selectors_all", "--js-selector-all", help="Take shot of all elements matching this JS (el) expression", multiple=True)
@click.option("-p", "--padding", type=int, help="When using selectors, add this much padding in pixels", default=0)
@click.option("-j", "--javascript", help="Execute this JS prior to taking the shot")
@scale_factor_options
@click.option("--omit-background", is_flag=True, help="Omit the default browser background from the shot, making it possible take advantage of transparency. Does not work with JPEGs or when using --quality.")
@click.option("--quality", type=int, help="Save as JPEG with this quality, e.g. 80")
@click.option("-i", "--interactive", is_flag=True, help="Interact with the page in a browser before taking the shot")
@click.option("--devtools", is_flag=True, help="Interact mode with developer tools")
@click.option("--log-requests", type=click.File("w"), help="Log details of all requests to this file")
@click.option("--save-html", is_flag=True, help="Save HTML content alongside the screenshot with the same base name")
@common_shot_options
def shot(url, width, height, output, selectors, selectors_all, js_selectors, js_selectors_all,
         padding, javascript, retina, scale_factor, omit_background, quality,
         interactive, devtools, log_requests, save_html,
         verbose, debug, silent, log_console, skip, fail, ad_block, popup_block,
         wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load,
         auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
         auth_username, auth_password):
    """
    Take a single screenshot of a page or portion of a page.

    Usage:

        shot-scraper www.example.com

    This will write the screenshot to www-example-com.png

    Use "-o" to write to a specific file:

        shot-scraper https://www.example.com/ -o example.png

    You can also pass a path to a local file on disk:

        shot-scraper index.html -o index.png

    Using "-o -" will output to standard out:

        shot-scraper https://www.example.com/ -o - > example.png

    Use -s to take a screenshot of one area of the page, identified using
    one or more CSS selectors:

        shot-scraper https://simonwillison.net -s '#bighead'

    Full page screenshots are taken by default. Use --height to limit the screenshot height:

        shot-scraper https://www.example.com/ --height 600 -o partial.png
    """
    setup_common_config(verbose, debug, silent)

    if output is None:
        ext = "jpg" if quality else None
        output = filename_for_url(url, ext=ext, file_exists=os.path.exists)

    scale_factor = normalize_scale_factor(retina, scale_factor)
    ad_block, popup_block = resolve_blocking_config(ad_block, popup_block)
    interactive = interactive or devtools

    shot_config = {
        "url": url, "selectors": selectors, "selectors_all": selectors_all,
        "js_selectors": js_selectors, "js_selectors_all": js_selectors_all,
        "javascript": javascript, "width": width, "height": height, "quality": quality,
        "padding": padding, "omit_background": omit_background, "scale_factor": scale_factor,
        "save_html": save_html,
        "ad_block": ad_block, "popup_block": popup_block,
        "wait": wait, "wait_for": wait_for, "timeout": timeout,
        "skip_cloudflare_check": skip_cloudflare_check,
        "skip_wait_for_load": skip_wait_for_load,
        "trigger_lazy_load": trigger_lazy_load, "verbose": verbose
    }

    async def execute_shot(browser_obj, **kwargs):
        if interactive:
            page = await browser_obj.get(url)
            if width or height:
                viewport = get_viewport(width, height)
                await page.set_window_size(viewport["width"], viewport["height"])
            click.echo("Hit <enter> to take the shot and close the browser window:", err=True)
            input()
            context = page
            use_existing_page = True
        else:
            context = browser_obj
            use_existing_page = False

        if output == "-":
            shot_bytes = await take_shot(
                context, shot_config, return_bytes=True, use_existing_page=use_existing_page,
                log_requests=log_requests, log_console=log_console, silent=silent,
            )
            sys.stdout.buffer.write(shot_bytes)
        else:
            shot_config["output"] = str(output)
            await take_shot(
                context, shot_config, use_existing_page=use_existing_page,
                log_requests=log_requests, log_console=log_console,
                skip=skip, fail=fail, silent=silent,
            )

    browser_kwargs = {
        'auth': auth, 'interactive': interactive, 'devtools': devtools,
        'scale_factor': scale_factor, 'browser': browser,
        'browser_args': browser_args, 'user_agent': user_agent,
        'timeout': timeout, 'reduced_motion': reduced_motion,
        'bypass_csp': bypass_csp, 'auth_username': auth_username,
        'auth_password': auth_password
    }

    run_async(run_with_browser_cleanup(
        run_browser_command(execute_shot, browser_kwargs, extensions_needed=ad_block or popup_block,
                          verbose=verbose, silent=silent, ad_block=ad_block, popup_block=popup_block)
    ))




@cli.command()
@click.argument("config", type=click.File(mode="r"))
@scale_factor_options
@click.option(
    "--timeout", type=int, help="Wait this many milliseconds before failing",
)
@click.option(
    "--fail-on-error", is_flag=True, help="Fail noisily on error", hidden=True
)
@click.option(
    "noclobber", "-n", "--no-clobber", is_flag=True, help="Skip images that already exist",
)
@click.option(
    "outputs", "-o", "--output", help="Just take shots matching these output files", multiple=True,
)
@click.option(
    "leave_server", "--leave-server", is_flag=True, help="Leave servers running when script finishes",
)
@click.option(
    "--har", is_flag=True, help="Save all requests to trace.har file",
)
@click.option(
    "--har-zip", is_flag=True, help="Save all requests to trace.har.zip file",
)
@click.option(
    "--har-file", type=click.Path(file_okay=True, writable=True, dir_okay=False),
    help="Path to HAR file to save all requests",
)
@common_shot_options
def multi(config, retina, scale_factor, timeout, fail_on_error, noclobber, outputs,
         leave_server, har, har_zip, har_file,
         verbose, debug, silent, log_console, skip, fail, ad_block, popup_block,
         wait, wait_for, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load,
         auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
         auth_username, auth_password):
    """
    Take multiple screenshots or PDFs, defined by a YAML file

    Usage:

        shot-power-scraper multi config.yml

    Where config.yml contains configuration like this:

    \b
        - output: example.png
          url: http://www.example.com/
        - output: example.pdf
          url: http://www.example.com/
          pdf_format: A4
          pdf_landscape: false

    \b
    PDF files are automatically detected by .pdf extension.
    All PDF options from the pdf command are supported in YAML format.
    """
    setup_common_config(verbose, debug, silent)

    if (har or har_zip) and not har_file:
        har_file = filename_for_url(
            "trace", ext="har.zip" if har_zip else "har", file_exists=os.path.exists
        )

    scale_factor = normalize_scale_factor(retina, scale_factor)
    ad_block, popup_block = resolve_blocking_config(ad_block, popup_block)
    shots = yaml.safe_load(config)

    if har_file:
        for shot in shots:
            if not shot.get("output"):
                shot["skip_shot"] = True

    server_processes = []
    if shots is None:
        shots = []
    if not isinstance(shots, list):
        raise click.ClickException("YAML file must contain a list")

    async def run_multi():
        extensions = []
        if ad_block or popup_block:
            await setup_blocking_extensions(extensions, ad_block, popup_block, verbose, silent)

        browser_obj = await create_browser_context(
            auth=auth, scale_factor=scale_factor, browser=browser,
            browser_args=browser_args, user_agent=user_agent,
            timeout=timeout, reduced_motion=reduced_motion,
            auth_username=auth_username, auth_password=auth_password,
            record_har_path=har_file or None, extensions=extensions if extensions else None,
        )

        try:
            for shot in shots:
                if (noclobber and shot.get("output") and pathlib.Path(shot["output"]).exists()):
                    continue
                if outputs and shot.get("output") and shot.get("output") not in outputs:
                    continue
                if shot.get("sh"):
                    sh = shot["sh"]
                    if isinstance(sh, str):
                        subprocess.run(shot["sh"], shell=True)
                    elif isinstance(sh, list):
                        subprocess.run(sh)
                    else:
                        raise click.ClickException("- sh: must be a string or list")
                if shot.get("python"):
                    subprocess.run([sys.executable, "-c", shot["python"]])
                if "server" in shot:
                    server = shot["server"]
                    proc = None
                    if isinstance(server, str):
                        proc = subprocess.Popen(server, shell=True)
                    elif isinstance(server, list):
                        proc = subprocess.Popen(map(str, server))
                    else:
                        raise click.ClickException("server: must be a string or list")
                    server_processes.append((proc, server))
                    time.sleep(1)
                if "url" in shot:
                    if ad_block or popup_block:
                        shot["ad_block"] = ad_block
                        shot["popup_block"] = popup_block

                    if timeout and "timeout" not in shot:
                        shot["timeout"] = timeout

                    try:
                        output_file = shot.get("output", "")
                        if output_file.lower().endswith('.pdf'):
                            await take_pdf(
                                browser_obj, shot, log_console=log_console,
                                skip=skip, fail=fail, silent=silent,
                            )
                        else:
                            await take_shot(
                                browser_obj, shot, log_console=log_console,
                                skip=skip, fail=fail, silent=silent,
                            )
                    except Exception as e:
                        if fail or fail_on_error:
                            raise e
                        else:
                            click.echo(str(e), err=True)
                            continue
        finally:
            if browser_obj:
                await cleanup_browser(browser_obj)
            if leave_server:
                for process, details in server_processes:
                    click.echo(f"Leaving server PID: {process.pid} details: {details}", err=True)
            else:
                if server_processes:
                    for process, _ in server_processes:
                        process.kill()
            if har_file and not silent:
                click.echo(f"Wrote to HAR file: {har_file}", err=True)

    run_async(run_with_browser_cleanup(run_multi()))


@cli.command()
@click.argument("url")
@click.option(
    "-o", "--output", type=click.File("w"), default="-",
)
@click.option("-j", "--javascript", help="Execute this JS prior to taking the snapshot")
@common_shot_options
def accessibility(url, output, javascript,
                 verbose, debug, silent, log_console, skip, fail, ad_block, popup_block,
                 wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load,
                 auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
                 auth_username, auth_password):
    """
    Dump the Chromium accessibility tree for the specifed page

    Usage:

        shot-scraper accessibility https://datasette.io/
    """
    setup_common_config(verbose, debug, silent)

    async def run_accessibility():
        browser_obj = await create_browser_context(
            auth=auth, timeout=timeout, bypass_csp=bypass_csp,
            auth_username=auth_username, auth_password=auth_password,
        )

        config = {
            "javascript": javascript, "skip_cloudflare_check": skip_cloudflare_check,
            "skip_wait_for_load": skip_wait_for_load, "timeout": timeout or 30,
            "wait": wait, "wait_for": wait_for, "trigger_lazy_load": trigger_lazy_load
        }

        from shot_power_scraper.page_utils import setup_page
        page, response_handler = await setup_page(
            browser_obj, url, config, log_console=log_console,
            skip=skip, fail=fail, silent=silent,
        )

        snapshot = {"message": "Accessibility tree dumping not implemented"}
        await cleanup_browser(browser_obj)
        return snapshot

    snapshot = run_async(run_with_browser_cleanup(run_accessibility()))
    output.write(json.dumps(snapshot, indent=4))
    output.write("\n")


@cli.command()
@click.argument("url")
@click.option("zip_", "-z", "--zip", is_flag=True, help="Save as a .har.zip file")
@click.option(
    "-o", "--output", type=click.Path(file_okay=True, dir_okay=False, writable=True, allow_dash=False),
    help="HAR filename",
)
@click.option("-j", "--javascript", help="Execute this JavaScript on the page")
@common_shot_options
def har(url, zip_, output, javascript,
       verbose, debug, silent, log_console, skip, fail, ad_block, popup_block,
       wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load,
       auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
       auth_username, auth_password):
    """
    NOT IMPLEMENTED - Record a HAR file for the specified page

    This command is not yet implemented with nodriver.
    """
    click.echo("Error: HAR recording is not implemented with nodriver", err=True)
    click.echo("Use the screenshot commands instead for capturing page content.", err=True)
    raise click.Abort()


@cli.command()
@click.argument("url")
@click.argument("javascript", required=False)
@click.option(
    "-i", "--input", default="-",
    help=("Read input JavaScript from this file or use gh:username/script "
          "to load from github.com/username/shot-scraper-scripts/script.js"),
)
@click.option(
    "-o", "--output", type=click.File("w"), default="-", help="Save output JSON to this file",
)
@click.option(
    "-r", "--raw", is_flag=True, help="Output JSON strings as raw text",
)
@common_shot_options
def javascript(url, javascript, input, output, raw,
              verbose, debug, silent, log_console, skip, fail, ad_block, popup_block,
              wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load,
              auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
              auth_username, auth_password):
    """
    Execute JavaScript against the page and return the result as JSON

    Usage:

        shot-scraper javascript https://datasette.io/ "document.title"

    To return a JSON object, use this:

        "({title: document.title, location: document.location})"

    To use setInterval() or similar, pass a promise:

    \b
        "new Promise(done => setInterval(
          () => {
            done({
              title: document.title,
              h2: document.querySelector('h2').innerHTML
            });
          }, 1000
        ));"

    If a JavaScript error occurs an exit code of 1 will be returned.
    """
    setup_common_config(verbose, debug, silent)

    if not javascript:
        if input.startswith("gh:"):
            javascript = load_github_script(input[3:])
        elif input == "-":
            javascript = sys.stdin.read()
        else:
            with open(input, "r") as f:
                javascript = f.read()

    async def run_javascript():
        browser_obj = await create_browser_context(
            auth=auth, browser=browser, browser_args=browser_args,
            user_agent=user_agent, reduced_motion=reduced_motion,
            bypass_csp=bypass_csp, auth_username=auth_username,
            auth_password=auth_password,
        )

        config = {
            "javascript": javascript, "skip_cloudflare_check": skip_cloudflare_check,
            "skip_wait_for_load": skip_wait_for_load, "timeout": timeout or 30,
            "wait": wait, "wait_for": wait_for, "trigger_lazy_load": trigger_lazy_load
        }

        from shot_power_scraper.page_utils import setup_page
        page, response_handler, result = await setup_page(
            browser_obj, url, config, log_console=log_console,
            skip=skip, fail=fail, silent=silent,
            return_js_result=True,
        )
        await cleanup_browser(browser_obj)
        return result

    result = run_async(run_with_browser_cleanup(run_javascript()))
    if raw:
        output.write(str(result))
        return
    output.write(json.dumps(result, indent=4, default=str))
    output.write("\n")


@cli.command()
@click.argument("url")
@click.option(
    "-o", "--output", type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True),
)
@click.option("-j", "--javascript", help="Execute this JS prior to creating the PDF")
@click.option(
    "--media-screen", is_flag=True, help="Use screen rather than print styles"
)
@click.option("--landscape", is_flag=True, help="Use landscape orientation")
@click.option(
    "--scale", type=click.FloatRange(min=0.1, max=2.0), help="Scale of the webpage rendering",
)
@click.option("--print-background", is_flag=True, help="Print background graphics")
@click.option("--pdf-css", help="Inject custom CSS for PDF generation")
@common_shot_options
def pdf(url, output, javascript, media_screen, landscape, scale, print_background, pdf_css,
       verbose, debug, silent, log_console, skip, fail, ad_block, popup_block,
       wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load,
       auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
       auth_username, auth_password):
    """
    Create a PDF of the specified page

    Usage:

        shot-power-scraper pdf https://www.example.com/

    This will write the PDF to www-example-com.pdf using standard letter size (8.5x11 inches).

    Use "-o" to write to a specific file:

        shot-power-scraper pdf https://www.example.com/ -o example.pdf

    You can also pass a path to a local file on disk:

        shot-power-scraper pdf index.html -o index.pdf

    Using "-o -" will output to standard out:

        shot-power-scraper pdf https://www.example.com/ -o - > example.pdf
    """
    setup_common_config(verbose, debug, silent)

    url = url_or_file_path(url, _check_and_absolutize)

    if output is None:
        output = filename_for_url(url, ext="pdf", file_exists=os.path.exists)

    async def run_pdf():
        browser_obj = await create_browser_context(
            auth=auth, browser=browser, browser_args=browser_args,
            user_agent=user_agent, timeout=timeout,
            reduced_motion=reduced_motion, bypass_csp=bypass_csp,
            auth_username=auth_username, auth_password=auth_password,
        )

        shot = {
            "url": url, "output": output, "javascript": javascript,
            "pdf_landscape": landscape, "pdf_scale": scale or 1.0,
            "pdf_print_background": print_background, "pdf_media_screen": media_screen,
            "pdf_css": pdf_css, "wait": wait, "wait_for": wait_for, "timeout": timeout,
            "trigger_lazy_load": trigger_lazy_load
        }

        pdf_data = await take_pdf(
            browser_obj, shot, return_bytes=True, log_console=log_console,
            skip=skip, fail=fail, silent=silent
        )

        await cleanup_browser(browser_obj)
        return pdf_data

    pdf_data = run_async(run_with_browser_cleanup(run_pdf()))

    if output == "-":
        sys.stdout.buffer.write(pdf_data)
    else:
        with open(output, "wb") as f:
            f.write(pdf_data)
        if not silent:
            click.echo(f"PDF created: {output}", err=True)


@cli.command()
@click.argument("url")
@click.option(
    "-o", "--output", type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True), default="-",
)
@click.option("-j", "--javascript", help="Execute this JS prior to saving the HTML")
@click.option(
    "-s", "--selector", help="Return outerHTML of first element matching this CSS selector",
)
@common_shot_options
def html(url, output, javascript, selector,
        verbose, debug, silent, log_console, skip, fail, ad_block, popup_block,
        wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load,
        auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
        auth_username, auth_password):
    """
    Output the final HTML of the specified page

    Usage:

        shot-scraper html https://datasette.io/

    Use -o to specify a filename:

        shot-scraper html https://datasette.io/ -o index.html
    """
    setup_common_config(verbose, debug, silent)

    if output is None:
        output = filename_for_url(url, ext="html", file_exists=os.path.exists)

    async def run_html():
        browser_obj = await create_browser_context(
            auth=auth, browser=browser, browser_args=browser_args,
            user_agent=user_agent, timeout=timeout,
            bypass_csp=bypass_csp, auth_username=auth_username,
            auth_password=auth_password,
        )

        config = {
            "javascript": javascript, "skip_cloudflare_check": skip_cloudflare_check,
            "skip_wait_for_load": skip_wait_for_load, "timeout": timeout or 30,
            "wait": wait, "wait_for": wait_for, "trigger_lazy_load": trigger_lazy_load
        }

        from shot_power_scraper.page_utils import setup_page
        page, response_handler = await setup_page(
            browser_obj, url, config, log_console=log_console,
            skip=skip, fail=fail, silent=silent,
        )

        if selector:
            element = await page.select(selector)
            if element:
                html = await element.get_html()
            else:
                raise click.ClickException(f"Selector '{selector}' not found")
        else:
            html = await page.get_content()

        await cleanup_browser(browser_obj)
        return html

    html = run_async(run_with_browser_cleanup(run_html()))

    if output == "-":
        sys.stdout.write(html)
    else:
        open(output, "w").write(html)
        if not silent:
            click.echo(f"HTML snapshot of '{url}' written to '{output}'", err=True)


@cli.command()
@click.option(
    "--browser",
    "-b",
    default="chromium",
    type=click.Choice(BROWSERS, case_sensitive=False),
    help="Which browser to use (nodriver automatically manages browsers)",
)
def install(browser):
    """
    Install note: nodriver automatically manages Chrome/Chromium installation.

    Usage:

        shot-scraper install

    No manual browser installation is required with nodriver.
    """
    click.echo("nodriver... does not require any drivers.")
    click.echo("Just needs Chrome or Chromium to be installed")


@cli.command(name="set-default-user-agent")
@click.option(
    "--browser", "-b", default="chromium", type=click.Choice(BROWSERS, case_sensitive=False),
    help="Which browser to use",
)
@click.option(
    "browser_args", "--browser-arg", multiple=True, help="Additional arguments to pass to the browser",
)
def set_default_user_agent_cmd(browser, browser_args):
    """
    Detect the browser's user agent, remove 'HeadlessChrome', and store as default.

    Usage:

        shot-scraper set-default-user-agent

    This will launch a browser instance, detect its user agent, modify it to
    remove 'HeadlessChrome' (replacing with 'Chrome'), and store it in the
    config file for future use.
    """
    async def detect_and_set_user_agent():
        browser_kwargs = dict(headless=True, browser_args=browser_args or [])
        browser_obj = await uc.start(**browser_kwargs)

        if browser_obj is None:
            raise click.ClickException("Failed to initialize browser")

        try:
            page = await browser_obj.get("about:blank")
            user_agent = await page.evaluate("navigator.userAgent")

            if not user_agent:
                raise click.ClickException("Could not detect user agent")

            modified_user_agent = user_agent.replace("HeadlessChrome", "Chrome")
            set_default_user_agent(modified_user_agent)

            from shot_power_scraper.utils import get_config_file
            click.echo(f"Original user agent: {user_agent}")
            click.echo(f"Modified user agent: {modified_user_agent}")
            click.echo(f"Saved default user agent to: {get_config_file()}")

        finally:
            await cleanup_browser(browser_obj)

    run_async(run_with_browser_cleanup(detect_and_set_user_agent()))


@cli.command(name="config")
@click.option(
    "--ad-block",
    type=bool,
    help="Set default ad blocking (true/false)"
)
@click.option(
    "--popup-block",
    type=bool,
    help="Set default popup blocking (true/false)"
)
@click.option(
    "--user-agent",
    help="Set default user agent string"
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear all configuration settings (delete config file)"
)
@click.option(
    "--show",
    is_flag=True,
    help="Show current configuration"
)
def config_cmd(ad_block, popup_block, user_agent, clear, show):
    """
    Configure default settings for shot-power-scraper

    Usage:

        shot-power-scraper config --ad-block true --popup-block false
        shot-power-scraper config --user-agent "Mozilla/5.0 ..."
        shot-power-scraper config --clear
        shot-power-scraper config --show
    """
    from shot_power_scraper.utils import load_config, set_default_ad_block, set_default_popup_block, set_default_user_agent, get_config_file
    import os

    if clear:
        config_file = get_config_file()
        if config_file.exists():
            os.remove(config_file)
            click.echo("Configuration file cleared.")
        else:
            click.echo("No configuration file found to clear.")
        return

    if show:
        config = load_config()
        click.echo(f"Configuration file: {get_config_file()}")
        click.echo(f"ad_block: {config.get('ad_block', False)}")
        click.echo(f"popup_block: {config.get('popup_block', False)}")
        click.echo(f"user_agent: {config.get('user_agent', 'None')}")
        return

    if ad_block is not None:
        set_default_ad_block(ad_block)
        click.echo(f"Set default ad_block to: {ad_block}")

    if popup_block is not None:
        set_default_popup_block(popup_block)
        click.echo(f"Set default popup_block to: {popup_block}")

    if user_agent is not None:
        set_default_user_agent(user_agent)
        click.echo(f"Set default user_agent to: {user_agent}")

    if ad_block is None and popup_block is None and user_agent is None and not show and not clear:
        click.echo("No configuration changes specified. Use --show to view current settings.")
        click.echo("Use --ad-block true/false, --popup-block true/false, --user-agent 'string', or --clear to modify settings.")


@cli.command()
@click.argument("url")
@click.argument(
    "context_file", type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True),
)
@click.option("--devtools", is_flag=True, help="Open browser DevTools")
@simple_browser_options
@click.option("--log-console", "--console-log", is_flag=True, help="Write console.log() to stderr")
def auth(url, context_file, devtools, browser, browser_args, user_agent, reduced_motion, log_console):
    """
    Open a browser so user can manually authenticate with the specified site,
    then save the resulting authentication context to a file.

    Usage:

        shot-scraper auth https://github.com/ auth.json
    """
    async def run_auth():
        browser_obj = await create_browser_context(
            auth=None, interactive=True, devtools=devtools,
            browser=browser, browser_args=browser_args,
            user_agent=user_agent,
        )
        page = await browser_obj.get(url)
        click.echo("Hit <enter> after you have signed in:", err=True)
        input()

        cookies = await page.send(uc.cdp.network.get_cookies())
        context_state = {
            "cookies": cookies.cookies if hasattr(cookies, 'cookies') else [],
            "origins": []
        }
        await cleanup_browser(browser_obj)
        return context_state

    context_state = run_async(run_with_browser_cleanup(run_auth()))
    context_json = json.dumps(context_state, indent=2) + "\n"
    if context_file == "-":
        click.echo(context_json)
    else:
        with open(context_file, "w") as fp:
            fp.write(context_json)
        if os.name != "nt":
            pathlib.Path(context_file).chmod(0o600)
