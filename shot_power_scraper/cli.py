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

from shot_power_scraper.utils import filename_for_url, load_github_script, url_or_file_path
from shot_power_scraper.browser import Config, create_browser_context, cleanup_browser, setup_blocking_extensions
from shot_power_scraper.screenshot import take_shot, take_pdf
from shot_power_scraper.shot_config import ShotConfig, set_config_value

BROWSERS = ("chromium", "chrome", "chrome-beta")


def run_nodriver_async(coro):
    """Run an async coroutine with nodriver event loop, cleanup warnings, and delay"""
    import warnings
    # Suppress harmless cleanup warnings from nodriver
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",
                              message=".*Task was destroyed but it is pending.*",
                              category=RuntimeWarning)

        async def coro_with_cleanup():
            result = await coro
            await asyncio.sleep(0.1)  # Give nodriver time to cleanup background processes
            return result

        # Use nodriver's event loop as recommended in their docs
        loop = uc.loop()
        return loop.run_until_complete(coro_with_cleanup())


def run_browser_command(command_func, shot_config, **kwargs):
    """ Create a browser, set up a tab, execute command async, and tear it down """
    async def browser_execution():
        browser_obj = None
        try:
            extensions = []
            if shot_config.ad_block or shot_config.popup_block or shot_config.paywall_block:
                await setup_blocking_extensions(extensions, shot_config.ad_block, shot_config.popup_block, shot_config.paywall_block)

            # Create browser with shot_config parameters
            browser_obj = await create_browser_context(shot_config, extensions)

            # Set up tab context with one-time configuration
            from shot_power_scraper.page_utils import create_tab_context
            page = await create_tab_context(browser_obj, shot_config)

            # Execute the command with configured page
            result = await command_func(page, **kwargs)
            return result
        finally:
            await cleanup_browser(browser_obj)

    return run_nodriver_async(browser_execution())


def setup_common_config(verbose, debug, silent, skip, fail, enable_gpu=False):
    """Setup common configuration used by all commands"""
    Config.verbose = verbose
    Config.silent = silent
    Config.debug = debug
    Config.skip = skip
    Config.fail = fail

    # Use command line flag if provided, otherwise check config file
    if enable_gpu:
        Config.enable_gpu = True
    else:
        from shot_power_scraper.shot_config import load_config
        config_file_settings = load_config()
        Config.enable_gpu = config_file_settings.get("enable_gpu", False)

    if skip and fail:
        raise click.ClickException("--skip and --fail cannot be used together")

    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Small utility functions stay here
def console_log(msg):
    click.echo(msg, err=True)




def scale_factor_options(fn):
    """Scale factor options for backwards compatibility"""
    click.option("--retina", is_flag=True, help="Use device scale factor of 2. Cannot be used together with '--scale-factor'.")(fn)
    click.option("--scale-factor", type=float, help="Device scale factor. Cannot be used together with '--retina'.")(fn)
    return fn




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
    click.option("--no-resize-viewport", is_flag=True,
                help="Don't resize viewport to full page height when taking full page screenshot")(fn)

    # Wait options
    click.option("--skip-wait-for-load", is_flag=True, help="Skip waiting for window load event")(fn)
    click.option("--timeout", type=int, help="Wait this many milliseconds before failing")(fn)
    click.option("--wait-for", help="Wait until this JS expression returns true")(fn)
    click.option("--wait", type=int, help="Wait this many milliseconds before taking the screenshot (default: 250)")(fn)

    # Browser options
    click.option("--reduced-motion", is_flag=True, help="Emulate 'prefers-reduced-motion' media feature")(fn)
    click.option("--user-agent", help="User-Agent header to use")(fn)
    click.option("--enable-gpu", is_flag=True, help="Enable GPU acceleration (GPU is disabled by default)")(fn)
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
    click.option("--paywall-block/--no-paywall-block", default=None,
                help="Enable paywall bypass using Bypass Paywalls Clean extension")(fn)

    return fn


def simple_browser_options(fn):
    """Simplified browser options for auth and config commands"""
    click.option("--reduced-motion", is_flag=True, help="Emulate 'prefers-reduced-motion' media feature")(fn)
    click.option("--user-agent", help="User-Agent header to use")(fn)
    click.option("--enable-gpu", is_flag=True, help="Enable GPU acceleration (GPU is disabled by default)")(fn)
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
@click.option("--width", "-w", type=int, help="Width of browser window, defaults to 1280", default=1280)
@click.option("--height", "-h", type=int, help="Height of browser window and shot - defaults to the full height of the page")
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
         verbose, debug, silent, log_console, skip, fail, ad_block, popup_block, paywall_block,
         wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load, no_resize_viewport,
         auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
         auth_username, auth_password, enable_gpu):
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
    setup_common_config(verbose, debug, silent, skip, fail, enable_gpu)

    url = url_or_file_path(url)

    if output is None:
        ext = "jpg" if quality else None
        output = filename_for_url(url, ext=ext)

    interactive = interactive or devtools
    resize_viewport = not no_resize_viewport

    try:
        shot_config = ShotConfig(locals())
    except ValueError as e:
        raise click.ClickException(str(e))

    async def shot_execution(page):
        skip_navigation = False
        if interactive:
            from shot_power_scraper.page_utils import navigate_to_url
            response_handler = await navigate_to_url(page, shot_config)
            click.echo("Hit <enter> to take the shot and close the browser window:", err=True)
            input()
            skip_navigation = True

        if output == "-":
            shot_bytes = await take_shot(
                page, shot_config, return_bytes=True, skip_navigation=skip_navigation,
            )
            sys.stdout.buffer.write(shot_bytes)
        else:
            shot_config.output = str(output)
            await take_shot(
                page, shot_config, skip_navigation=skip_navigation,
            )

    run_browser_command(shot_execution, shot_config)




@cli.command()
@click.argument("config", type=click.File(mode="r"))
@scale_factor_options
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
         verbose, debug, silent, log_console, skip, fail, ad_block, popup_block, paywall_block,
         wait, wait_for, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load, no_resize_viewport,
         auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
         auth_username, auth_password, enable_gpu):
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
    setup_common_config(verbose, debug, silent, skip, fail, enable_gpu)

    if (har or har_zip) and not har_file:
        har_file = filename_for_url(
            "trace", ext="har.zip" if har_zip else "har"
        )

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
        if ad_block or popup_block or paywall_block:
            await setup_blocking_extensions(extensions, ad_block, popup_block, paywall_block)

        # Create browser config for multi command
        record_har_path = har_file
        try:
            browser_shot_config = ShotConfig(locals())
        except ValueError as e:
            raise click.ClickException(str(e))

        browser_obj = await create_browser_context(browser_shot_config, extensions)

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
                    if timeout and "timeout" not in shot:
                        shot["timeout"] = timeout

                    try:
                        # Add execution parameters to shot dict before creating ShotConfig
                        shot.update({
                            "log_console": log_console,
                        })
                        shot_config = ShotConfig(shot)

                        # Create a new tab context for each shot
                        from shot_power_scraper.page_utils import create_tab_context
                        page = await create_tab_context(browser_obj, shot_config)

                        if shot_config.output and shot_config.output.lower().endswith('.pdf'):
                            await take_pdf(
                                page, shot_config,
                            )
                        else:
                            await take_shot(
                                page, shot_config,
                            )
                    except Exception as e:
                        if Config.fail or fail_on_error:
                            raise e
                        else:
                            click.echo(str(e), err=True)
                            continue
        finally:
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

    run_nodriver_async(run_multi())


@cli.command()
@click.argument("url")
@click.option(
    "-o", "--output", type=click.File("w"), default="-",
)
@click.option("-j", "--javascript", help="Execute this JS prior to taking the snapshot")
@common_shot_options
def accessibility(url, output, javascript,
                 verbose, debug, silent, log_console, skip, fail, ad_block, popup_block, paywall_block,
                 wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load, no_resize_viewport,
                 auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
                 auth_username, auth_password, enable_gpu):
    """
    (NOT IMPLEMENTED) Dump the Chromium accessibility tree for the specifed page

    Usage:

        shot-scraper accessibility https://datasette.io/
    """
    raise NotImplementedError("Accessibility tree dumping is not implemented in shot-power-scraper")


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
       verbose, debug, silent, log_console, skip, fail, ad_block, popup_block, paywall_block,
       wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load, no_resize_viewport,
       auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
       auth_username, auth_password, enable_gpu):
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
@click.option("-o", "--output", type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True), default="-", help="Save output JSON to this file")
@click.option(
    "-r", "--raw", is_flag=True, help="Output JSON strings as raw text",
)
@common_shot_options
def javascript(url, javascript, input, output, raw,
              verbose, debug, silent, log_console, skip, fail, ad_block, popup_block, paywall_block,
              wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load, no_resize_viewport,
              auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
              auth_username, auth_password, enable_gpu):
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
    setup_common_config(verbose, debug, silent, skip, fail, enable_gpu)

    if not javascript:
        if input.startswith("gh:"):
            javascript = load_github_script(input[3:])
        elif input == "-":
            javascript = sys.stdin.read()
        else:
            with open(input, "r") as f:
                javascript = f.read()

    return_js_result = True
    shot_config = ShotConfig(locals())

    async def execute_js(page, **kwargs):
        from shot_power_scraper.page_utils import navigate_to_url
        response_handler, result = await navigate_to_url(
            page, shot_config,
        )
        return result

    result = run_browser_command(execute_js, shot_config)

    if output == "-":
        if raw:
            sys.stdout.write(str(result))
        else:
            sys.stdout.write(json.dumps(result, default=str))
            sys.stdout.write("\n")
    else:
        with open(output, "w") as f:
            if raw:
                f.write(str(result))
            else:
                f.write(json.dumps(result, indent=4, default=str))
                f.write("\n")


@cli.command()
@click.argument("url")
@click.option("-o", "--output", type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True),)
@click.option("-j", "--javascript", help="Execute this JS prior to creating the PDF")
@click.option("--media-screen", is_flag=True, help="Use screen rather than print styles")
@click.option("--landscape", is_flag=True, help="Use landscape orientation")
@click.option("--scale", type=click.FloatRange(min=0.1, max=2.0), help="Scale of the webpage rendering",)
@click.option("--print-background", is_flag=True, help="Print background graphics")
@click.option("--pdf-css", help="Inject custom CSS for PDF generation")
@common_shot_options
def pdf(url, output, javascript, media_screen, landscape, scale, print_background, pdf_css,
       verbose, debug, silent, log_console, skip, fail, ad_block, popup_block, paywall_block,
       wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load, no_resize_viewport,
       auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
       auth_username, auth_password, enable_gpu):
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
    setup_common_config(verbose, debug, silent, skip, fail, enable_gpu)

    url = url_or_file_path(url)

    if output is None:
        output = filename_for_url(url, ext="pdf")

    pdf_landscape = landscape
    pdf_scale = scale or 1.0
    pdf_print_background = print_background
    pdf_media_screen = media_screen
    try:
        shot_config = ShotConfig(locals())
    except ValueError as e:
        raise click.ClickException(str(e))

    async def execute_pdf(page, **kwargs):
        pdf_data = await take_pdf(
            page, shot_config, return_bytes=True
        )
        return pdf_data

    pdf_data = run_browser_command(execute_pdf, shot_config)

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
        verbose, debug, silent, log_console, skip, fail, ad_block, popup_block, paywall_block,
        wait, wait_for, timeout, skip_cloudflare_check, skip_wait_for_load, trigger_lazy_load, no_resize_viewport,
        auth, browser, browser_args, user_agent, reduced_motion, bypass_csp,
        auth_username, auth_password, enable_gpu):
    """
    Output the final HTML of the specified page

    Usage:

        shot-scraper html https://datasette.io/

    Use -o to specify a filename:

        shot-scraper html https://datasette.io/ -o index.html
    """
    setup_common_config(verbose, debug, silent, skip, fail, enable_gpu)

    if output is None:
        output = filename_for_url(url, ext="html")

    shot_config = ShotConfig(locals())

    async def execute_html(page, **kwargs):
        from shot_power_scraper.page_utils import navigate_to_url
        response_handler = await navigate_to_url(
            page, shot_config,
        )

        if selector:
            element = await page.select(selector)
            if element:
                html_content = await element.get_html()
            else:
                raise click.ClickException(f"Selector '{selector}' not found")
        else:
            html_content = await page.get_content()

        return html_content

    html_content = run_browser_command(execute_html, shot_config)

    if output == "-":
        sys.stdout.write(html_content)
    else:
        with open(output, "w") as f:
            f.write(html_content)
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
@click.option(
    "browser_args", "--browser-arg", multiple=True, help="Additional arguments to pass to the browser",
)
def install(browser, browser_args):
    """
    Install note: nodriver automatically manages Chrome/Chromium installation.
    Also detects and sets the default user agent for stealth mode.

    Usage:

        shot-scraper install

    No manual browser installation is required with nodriver.
    This command will also detect the browser's user agent and set it as default.
    """
    click.echo("nodriver... does not require any drivers.")
    click.echo("Just needs Chrome or Chromium to be installed")
    click.echo()
    click.echo("Setting up default user agent for stealth mode...")

    async def set_user_agent_wrapper(browser_obj):
        page = await browser_obj.get("about:blank")
        user_agent = await page.evaluate("navigator.userAgent")

        if not user_agent:
            raise click.ClickException("Could not detect user agent")

        # Remove HeadlessChrome to avoid detection
        modified_user_agent = user_agent.replace("HeadlessChrome", "Chrome")
        set_config_value('user_agent', modified_user_agent)

        from shot_power_scraper.shot_config import get_config_file
        click.echo(f"Original user agent: {user_agent}")
        click.echo(f"Modified user agent: {modified_user_agent}")
        click.echo(f"Saved default user agent to: {get_config_file()}")
        click.echo("✓ Client Hints metadata will be generated from real user agent at runtime")

    shot_config = ShotConfig({"interactive": False, "browser_args": browser_args or []})
    run_browser_command(set_user_agent_wrapper, shot_config)



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
    "--paywall-block",
    type=bool,
    help="Set default paywall blocking (true/false)"
)
@click.option(
    "--user-agent",
    help="Set default user agent string"
)
@click.option(
    "--enable-gpu",
    type=bool,
    help="Set default GPU enable setting (true/false)"
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
def config_cmd(ad_block, popup_block, paywall_block, user_agent, enable_gpu, clear, show):
    """
    Configure default settings for shot-power-scraper

    Usage:

        shot-power-scraper config --ad-block true --popup-block false --paywall-block true
        shot-power-scraper config --user-agent "Mozilla/5.0 ..."
        shot-power-scraper config --enable-gpu true
        shot-power-scraper config --clear
        shot-power-scraper config --show
    """
    from shot_power_scraper.shot_config import load_config, set_config_value, get_config_file
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
        click.echo(f"paywall_block: {config.get('paywall_block', False)}")
        click.echo(f"user_agent: {config.get('user_agent', 'None')}")
        click.echo(f"enable_gpu: {config.get('enable_gpu', False)}")
        return

    if ad_block is not None:
        set_config_value('ad_block', ad_block)
        click.echo(f"Set default ad_block to: {ad_block}")

    if popup_block is not None:
        set_config_value('popup_block', popup_block)
        click.echo(f"Set default popup_block to: {popup_block}")

    if paywall_block is not None:
        set_config_value('paywall_block', paywall_block)
        click.echo(f"Set default paywall_block to: {paywall_block}")

    if user_agent is not None:
        set_config_value('user_agent', user_agent)
        click.echo(f"Set default user_agent to: {user_agent}")

    if enable_gpu is not None:
        set_config_value('enable_gpu', enable_gpu)
        click.echo(f"Set default enable_gpu to: {enable_gpu}")

    if ad_block is None and popup_block is None and paywall_block is None and user_agent is None and enable_gpu is None and not show and not clear:
        click.echo("No configuration changes specified. Use --show to view current settings.")
        click.echo("Use --ad-block true/false, --popup-block true/false, --paywall-block true/false, --user-agent 'string', --enable-gpu true/false, or --clear to modify settings.")


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
    async def execute_auth(browser_obj, **kwargs):
        page = await browser_obj.get(url)
        click.echo("Hit <enter> after you have signed in:", err=True)
        input()

        cookies = await page.send(uc.cdp.network.get_cookies())
        context_state = {
            "cookies": cookies.cookies if hasattr(cookies, 'cookies') else [],
            "origins": []
        }
        return context_state

    interactive = True
    shot_config = ShotConfig(locals())

    context_state = run_browser_command(execute_auth, shot_config)

    context_json = json.dumps(context_state, indent=2) + "\n"
    if context_file == "-":
        click.echo(context_json)
    else:
        with open(context_file, "w") as fp:
            fp.write(context_json)
        if os.name != "nt":
            pathlib.Path(context_file).chmod(0o600)
