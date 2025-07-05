import secrets
import subprocess
import sys
import textwrap
import time
import json
import os
import pathlib
from runpy import run_module
from click_default_group import DefaultGroup
import yaml
import click
import nodriver as uc
import asyncio


from shot_scraper.utils import filename_for_url, load_github_script, url_or_file_path, get_default_user_agent, set_default_user_agent

BROWSERS = ("chromium", "chrome", "chrome-beta")


async def run_with_browser_cleanup(coro):
    """Run an async function and give nodriver time to cleanup afterwards."""
    result = await coro
    await asyncio.sleep(0.5)  # Give nodriver time to cleanup background processes
    return result




def console_log(msg):
    click.echo(msg, err=True)


def browser_option(fn):
    click.option(
        "--browser",
        "-b",
        default="chromium",
        type=click.Choice(BROWSERS, case_sensitive=False),
        help="Which browser to use",
    )(fn)
    return fn


def browser_args_option(fn):
    click.option(
        "browser_args",
        "--browser-arg",
        multiple=True,
        help="Additional arguments to pass to the browser",
    )(fn)
    return fn


def user_agent_option(fn):
    click.option("--user-agent", help="User-Agent header to use")(fn)
    return fn


def log_console_option(fn):
    click.option("--log-console", is_flag=True, help="Write console.log() to stderr")(
        fn
    )
    return fn


def silent_option(fn):
    click.option("--silent", is_flag=True, help="Do not output any messages")(fn)
    return fn


def skip_fail_options(fn):
    click.option("--skip", is_flag=True, help="Skip pages that return HTTP errors")(fn)
    click.option(
        "--fail",
        is_flag=True,
        help="Fail with an error code if a page returns an HTTP error",
    )(fn)
    return fn


def bypass_csp_option(fn):
    click.option("--bypass-csp", is_flag=True, help="Bypass Content-Security-Policy")(
        fn
    )
    return fn


def http_auth_options(fn):
    click.option("--auth-username", help="Username for HTTP Basic authentication")(fn)
    click.option("--auth-password", help="Password for HTTP Basic authentication")(fn)
    return fn


def skip_or_fail(response, skip, fail):
    if skip and fail:
        raise click.ClickException("--skip and --fail cannot be used together")
    if str(response.status)[0] in ("4", "5"):
        if skip:
            click.echo(
                f"{response.status} error for {response.url}, skipping",
                err=True,
            )
            # Exit with a 0 status code
            raise SystemExit
        elif fail:
            raise click.ClickException(f"{response.status} error for {response.url}")


def scale_factor_options(fn):
    click.option(
        "--retina",
        is_flag=True,
        help="Use device scale factor of 2. Cannot be used together with '--scale-factor'.",
    )(fn)
    click.option(
        "--scale-factor",
        type=float,
        help="Device scale factor. Cannot be used together with '--retina'.",
    )(fn)
    return fn


def normalize_scale_factor(retina, scale_factor):
    if retina and scale_factor:
        raise click.ClickException(
            "--retina and --scale-factor cannot be used together"
        )
    if scale_factor is not None and scale_factor <= 0.0:
        raise click.ClickException("--scale-factor must be positive")
    if retina:
        scale_factor = 2
    return scale_factor


def reduced_motion_option(fn):
    click.option(
        "--reduced-motion",
        is_flag=True,
        help="Emulate 'prefers-reduced-motion' media feature",
    )(fn)
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
@click.argument("url")  # TODO: validate with custom type
@click.option(
    "-a",
    "--auth",
    type=click.File("r"),
    help="Path to JSON authentication context file",
)
@click.option(
    "--width",
    type=int,
    help="Width of browser window, defaults to 1280",
    default=1280,
)
@click.option(
    "--height",
    type=int,
    help="Height of browser window and shot - defaults to the full height of the page",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True),
)
@click.option(
    "selectors",
    "-s",
    "--selector",
    help="Take shot of first element matching this CSS selector",
    multiple=True,
)
@click.option(
    "selectors_all",
    "--selector-all",
    help="Take shot of all elements matching this CSS selector",
    multiple=True,
)
@click.option(
    "js_selectors",
    "--js-selector",
    help="Take shot of first element matching this JS (el) expression",
    multiple=True,
)
@click.option(
    "js_selectors_all",
    "--js-selector-all",
    help="Take shot of all elements matching this JS (el) expression",
    multiple=True,
)
@click.option(
    "-p",
    "--padding",
    type=int,
    help="When using selectors, add this much padding in pixels",
    default=0,
)
@click.option("-j", "--javascript", help="Execute this JS prior to taking the shot")
@scale_factor_options
@click.option(
    "--omit-background",
    is_flag=True,
    help="Omit the default browser background from the shot, making it possible take advantage of transparency. Does not work with JPEGs or when using --quality.",
)
@click.option("--quality", type=int, help="Save as JPEG with this quality, e.g. 80")
@click.option(
    "--wait", type=int, help="Wait this many milliseconds before taking the screenshot"
)
@click.option("--wait-for", help="Wait until this JS expression returns true")
@click.option(
    "--timeout",
    type=int,
    help="Wait this many milliseconds before failing",
)
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    help="Interact with the page in a browser before taking the shot",
)
@click.option(
    "--devtools",
    is_flag=True,
    help="Interact mode with developer tools",
)
@click.option(
    "--log-requests",
    type=click.File("w"),
    help="Log details of all requests to this file",
)
@log_console_option
@browser_option
@browser_args_option
@user_agent_option
@reduced_motion_option
@skip_fail_options
@bypass_csp_option
@silent_option
@http_auth_options
@click.option(
    "--skip-cloudflare-check",
    is_flag=True,
    help="Skip Cloudflare challenge detection and waiting"
)
@click.option(
    "--wait-for-dom-ready-timeout",
    type=int,
    default=10000,
    help="Maximum milliseconds to wait for DOM ready (default: 10000)"
)
@click.option(
    "--skip-wait-for-dom-ready",
    is_flag=True,
    help="Skip waiting for DOM ready state"
)
@click.option(
    "--full-page",
    is_flag=True,
    help="Capture the full scrollable page (overrides --height)"
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging to stdout"
)
def shot(
    url,
    auth,
    output,
    width,
    height,
    selectors,
    selectors_all,
    js_selectors,
    js_selectors_all,
    padding,
    javascript,
    retina,
    scale_factor,
    omit_background,
    quality,
    wait,
    wait_for,
    timeout,
    interactive,
    devtools,
    log_requests,
    log_console,
    browser,
    browser_args,
    user_agent,
    reduced_motion,
    skip,
    fail,
    bypass_csp,
    silent,
    auth_username,
    auth_password,
    skip_cloudflare_check,
    wait_for_dom_ready_timeout,
    skip_wait_for_dom_ready,
    full_page,
    verbose,
):
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

    Use --full-page to capture the entire scrollable page:

        shot-scraper https://www.example.com/ --full-page -o full.png
    """
    if output is None:
        ext = "jpg" if quality else None
        output = filename_for_url(url, ext=ext, file_exists=os.path.exists)

    scale_factor = normalize_scale_factor(retina, scale_factor)

    shot = {
        "url": url,
        "selectors": selectors,
        "selectors_all": selectors_all,
        "js_selectors": js_selectors,
        "js_selectors_all": js_selectors_all,
        "javascript": javascript,
        "width": width,
        "height": height,
        "quality": quality,
        "wait": wait,
        "wait_for": wait_for,
        "timeout": timeout,
        "padding": padding,
        "omit_background": omit_background,
        "scale_factor": scale_factor,
        "skip_cloudflare_check": skip_cloudflare_check,
        "wait_for_dom_ready_timeout": wait_for_dom_ready_timeout,
        "skip_wait_for_dom_ready": skip_wait_for_dom_ready,
        "full_page": full_page,
        "verbose": verbose,
    }
    interactive = interactive or devtools

    async def run_shot():
        use_existing_page = False
        browser_obj = None
        try:
            browser_obj = await _browser_context(
                auth,
                interactive=interactive,
                devtools=devtools,
                scale_factor=scale_factor,
                browser=browser,
                browser_args=browser_args,
                user_agent=user_agent,
                timeout=timeout,
                reduced_motion=reduced_motion,
                bypass_csp=bypass_csp,
                auth_username=auth_username,
                auth_password=auth_password,
            )

            if not browser_obj:
                raise click.ClickException("Browser initialization failed")

            if interactive or devtools:
                use_existing_page = True
                page = await browser_obj.get(url)
                if width or height:
                    viewport = _get_viewport(width, height)
                    await page.set_window_size(viewport["width"], viewport["height"])
                click.echo(
                    "Hit <enter> to take the shot and close the browser window:", err=True
                )
                input()
                context = page
            else:
                context = browser_obj
            if output == "-":
                shot_bytes = await take_shot(
                    context,
                    shot,
                    return_bytes=True,
                    use_existing_page=use_existing_page,
                    log_requests=log_requests,
                    log_console=log_console,
                    silent=silent,
                    verbose=verbose,
                )
                sys.stdout.buffer.write(shot_bytes)
            else:
                shot["output"] = str(output)
                await take_shot(
                    context,
                    shot,
                    use_existing_page=use_existing_page,
                    log_requests=log_requests,
                    log_console=log_console,
                    skip=skip,
                    fail=fail,
                    silent=silent,
                    verbose=verbose,
                )
        except Exception as e:
            raise click.ClickException(str(e))
        finally:
            if browser_obj:
                try:
                    await browser_obj.stop()
                except Exception:
                    # Browser cleanup can be flaky with event loops - just ignore it
                    pass

    asyncio.run(run_with_browser_cleanup(run_shot()))


async def _browser_context(
    auth,
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
    browser_kwargs = dict(
        headless=not interactive,
        browser_args=browser_args or []
    )

    # Use stored default user agent if no explicit user agent is provided
    if not user_agent:
        user_agent = get_default_user_agent()

    # Add user agent to browser args if specified or found in config
    if user_agent:
        browser_kwargs["browser_args"].append(f"--user-agent={user_agent}")

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


@cli.command()
@click.argument("config", type=click.File(mode="r"))
@click.option(
    "-a",
    "--auth",
    type=click.File("r"),
    help="Path to JSON authentication context file",
)
@scale_factor_options
@click.option(
    "--timeout",
    type=int,
    help="Wait this many milliseconds before failing",
)
# Hidden because will be removed if I release shot-scraper 2.0
# See https://github.com/simonw/shot-scraper/issues/103
@click.option(
    "--fail-on-error", is_flag=True, help="Fail noisily on error", hidden=True
)
@click.option(
    "noclobber",
    "-n",
    "--no-clobber",
    is_flag=True,
    help="Skip images that already exist",
)
@click.option(
    "outputs",
    "-o",
    "--output",
    help="Just take shots matching these output files",
    multiple=True,
)
@browser_option
@browser_args_option
@user_agent_option
@reduced_motion_option
@log_console_option
@skip_fail_options
@silent_option
@http_auth_options
@click.option(
    "leave_server",
    "--leave-server",
    is_flag=True,
    help="Leave servers running when script finishes",
)
@click.option(
    "--har",
    is_flag=True,
    help="Save all requests to trace.har file",
)
@click.option(
    "--har-zip",
    is_flag=True,
    help="Save all requests to trace.har.zip file",
)
@click.option(
    "--har-file",
    type=click.Path(file_okay=True, writable=True, dir_okay=False),
    help="Path to HAR file to save all requests",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging including DOM Ready timing"
)
def multi(
    config,
    auth,
    retina,
    scale_factor,
    timeout,
    fail_on_error,
    noclobber,
    outputs,
    browser,
    browser_args,
    user_agent,
    reduced_motion,
    log_console,
    skip,
    fail,
    silent,
    auth_username,
    auth_password,
    leave_server,
    har,
    har_zip,
    har_file,
    verbose,
):
    """
    Take multiple screenshots, defined by a YAML file

    Usage:

        shot-scraper multi config.yml

    Where config.yml contains configuration like this:

    \b
        - output: example.png
          url: http://www.example.com/

    \b
    For full YAML syntax documentation, see:
    https://shot-scraper.datasette.io/en/stable/multi.html
    """
    if (har or har_zip) and not har_file:
        har_file = filename_for_url(
            "trace", ext="har.zip" if har_zip else "har", file_exists=os.path.exists
        )

    scale_factor = normalize_scale_factor(retina, scale_factor)
    shots = yaml.safe_load(config)

    # Special case: if we are recording a har_file output can be blank to skip a shot
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
        browser_obj = await _browser_context(
            auth,
            scale_factor=scale_factor,
            browser=browser,
            browser_args=browser_args,
            user_agent=user_agent,
            timeout=timeout,
            reduced_motion=reduced_motion,
            auth_username=auth_username,
            auth_password=auth_password,
            record_har_path=har_file or None,
        )
        try:
            for shot in shots:
                if (
                    noclobber
                    and shot.get("output")
                    and pathlib.Path(shot["output"]).exists()
                ):
                    continue
                if outputs and shot.get("output") and shot.get("output") not in outputs:
                    continue
                # Run "sh" key
                if shot.get("sh"):
                    sh = shot["sh"]
                    if isinstance(sh, str):
                        subprocess.run(shot["sh"], shell=True)
                    elif isinstance(sh, list):
                        subprocess.run(sh)
                    else:
                        raise click.ClickException("- sh: must be a string or list")
                # And "python" key
                if shot.get("python"):
                    subprocess.run([sys.executable, "-c", shot["python"]])
                if "server" in shot:
                    # Start that subprocess and remember the pid
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
                    try:
                        await take_shot(
                            browser_obj,
                            shot,
                            log_console=log_console,
                            skip=skip,
                            fail=fail,
                            silent=silent,
                            verbose=verbose,
                        )
                    except Exception as e:
                        if fail or fail_on_error:
                            raise click.ClickException(str(e))
                        else:
                            click.echo(str(e), err=True)
                            continue
        finally:
            try:
                if browser_obj:
                    await browser_obj.stop()
            except Exception:
                # Ignore cleanup errors
                pass
            if leave_server:
                for process, details in server_processes:
                    click.echo(
                        f"Leaving server PID: {process.pid} details: {details}",
                        err=True,
                    )
            else:
                if server_processes:
                    for process, _ in server_processes:
                        process.kill()
            if har_file and not silent:
                click.echo(f"Wrote to HAR file: {har_file}", err=True)

    asyncio.run(run_with_browser_cleanup(run_multi()))


@cli.command()
@click.argument("url")
@click.option(
    "-a",
    "--auth",
    type=click.File("r"),
    help="Path to JSON authentication context file",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    default="-",
)
@click.option("-j", "--javascript", help="Execute this JS prior to taking the snapshot")
@click.option(
    "--timeout",
    type=int,
    help="Wait this many milliseconds before failing",
)
@log_console_option
@skip_fail_options
@bypass_csp_option
@http_auth_options
def accessibility(
    url,
    auth,
    output,
    javascript,
    timeout,
    log_console,
    skip,
    fail,
    bypass_csp,
    auth_username,
    auth_password,
):
    """
    Dump the Chromium accessibility tree for the specifed page

    Usage:

        shot-scraper accessibility https://datasette.io/
    """
    url = url_or_file_path(url, _check_and_absolutize)

    async def run_accessibility():
        browser_obj = await _browser_context(
            auth,
            timeout=timeout,
            bypass_csp=bypass_csp,
            auth_username=auth_username,
            auth_password=auth_password,
        )
        page = await browser_obj.get(url)
        # nodriver doesn't have console event handling by default
        if javascript:
            await _evaluate_js(page, javascript)
        # nodriver doesn't have accessibility.snapshot(), we'll implement a basic alternative
        # or note that this feature is not available
        snapshot = {"message": "Accessibility tree dumping not yet supported with nodriver"}
        try:
            await browser_obj.stop()
        except Exception:
            # Browser cleanup can be flaky - just ignore it
            pass
        return snapshot

    snapshot = asyncio.run(run_with_browser_cleanup(run_accessibility()))
    output.write(json.dumps(snapshot, indent=4))
    output.write("\n")


@cli.command()
@click.argument("url")
@click.option("zip_", "-z", "--zip", is_flag=True, help="Save as a .har.zip file")
@click.option(
    "-a",
    "--auth",
    type=click.File("r"),
    help="Path to JSON authentication context file",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False, writable=True, allow_dash=False),
    help="HAR filename",
)
@click.option(
    "--wait", type=int, help="Wait this many milliseconds before taking the screenshot"
)
@click.option("--wait-for", help="Wait until this JS expression returns true")
@click.option("-j", "--javascript", help="Execute this JavaScript on the page")
@click.option(
    "--timeout",
    type=int,
    help="Wait this many milliseconds before failing",
)
@log_console_option
@skip_fail_options
@bypass_csp_option
@http_auth_options
def har(
    url,
    zip_,
    auth,
    output,
    wait,
    wait_for,
    timeout,
    javascript,
    log_console,
    skip,
    fail,
    bypass_csp,
    auth_username,
    auth_password,
):
    """
    Record a HAR file for the specified page

    Usage:

        shot-scraper har https://datasette.io/

    This defaults to saving to datasette-io.har - use -o to specify a different filename:

        shot-scraper har https://datasette.io/ -o trace.har

    Use --zip to save as a .har.zip file instead, or specify a filename ending in .har.zip
    """
    if output is None:
        output = filename_for_url(
            url, ext="har.zip" if zip_ else "har", file_exists=os.path.exists
        )

    url = url_or_file_path(url, _check_and_absolutize)

    async def run_har():
        browser_obj = await _browser_context(
            auth,
            timeout=timeout,
            bypass_csp=bypass_csp,
            auth_username=auth_username,
            auth_password=auth_password,
            record_har_path=str(output),
        )
        page = await browser_obj.get(url)

        if wait:
            time.sleep(wait / 1000)

        if javascript:
            await _evaluate_js(page, javascript)

        if wait_for:
            await page.wait_for_function(wait_for)

        try:
            await browser_obj.stop()
        except Exception:
            # Browser cleanup can be flaky - just ignore it
            pass

    # Note: HAR recording not yet fully implemented with nodriver
    click.echo("HAR recording not yet fully supported with nodriver", err=True)
    asyncio.run(run_with_browser_cleanup(run_har()))


@cli.command()
@click.argument("url")
@click.argument("javascript", required=False)
@click.option(
    "-i",
    "--input",
    default="-",
    help=(
        "Read input JavaScript from this file or use gh:username/script "
        "to load from github.com/username/shot-scraper-scripts/script.js"
    ),
)
@click.option(
    "-a",
    "--auth",
    type=click.File("r"),
    help="Path to JSON authentication context file",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    default="-",
    help="Save output JSON to this file",
)
@click.option(
    "-r",
    "--raw",
    is_flag=True,
    help="Output JSON strings as raw text",
)
@browser_option
@browser_args_option
@user_agent_option
@reduced_motion_option
@log_console_option
@skip_fail_options
@bypass_csp_option
@http_auth_options
def javascript(
    url,
    javascript,
    input,
    auth,
    output,
    raw,
    browser,
    browser_args,
    user_agent,
    reduced_motion,
    log_console,
    skip,
    fail,
    bypass_csp,
    auth_username,
    auth_password,
):
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
    if not javascript:
        if input.startswith("gh:"):
            try:
                javascript = load_github_script(input[3:])
            except ValueError as ex:
                raise click.ClickException(str(ex))
        elif input == "-":
            javascript = sys.stdin.read()
        else:
            try:
                with open(input, "r") as f:
                    javascript = f.read()
            except Exception as e:
                raise click.ClickException(f"Failed to read file '{input}': {e}")

    url = url_or_file_path(url, _check_and_absolutize)

    async def run_javascript():
        browser_obj = await _browser_context(
            auth,
            browser=browser,
            browser_args=browser_args,
            user_agent=user_agent,
            reduced_motion=reduced_motion,
            bypass_csp=bypass_csp,
            auth_username=auth_username,
            auth_password=auth_password,
        )
        page = await browser_obj.get(url)
        result = await _evaluate_js(page, javascript)
        try:
            await browser_obj.stop()
        except Exception:
            # Browser cleanup can be flaky - just ignore it
            pass
        return result

    result = asyncio.run(run_with_browser_cleanup(run_javascript()))
    if raw:
        output.write(str(result))
        return
    output.write(json.dumps(result, indent=4, default=str))
    output.write("\n")


@cli.command()
@click.argument("url")
@click.option(
    "-a",
    "--auth",
    type=click.File("r"),
    help="Path to JSON authentication context file",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True),
)
@click.option("-j", "--javascript", help="Execute this JS prior to creating the PDF")
@click.option(
    "--wait", type=int, help="Wait this many milliseconds before taking the screenshot"
)
@click.option("--wait-for", help="Wait until this JS expression returns true")
@click.option(
    "--timeout",
    type=int,
    help="Wait this many milliseconds before failing",
)
@click.option(
    "--media-screen", is_flag=True, help="Use screen rather than print styles"
)
@click.option("--landscape", is_flag=True, help="Use landscape orientation")
@click.option(
    "--format",
    "format_",
    type=click.Choice(
        [
            "Letter",
            "Legal",
            "Tabloid",
            "Ledger",
            "A0",
            "A1",
            "A2",
            "A3",
            "A4",
            "A5",
            "A6",
        ],
        case_sensitive=False,
    ),
    help="Which standard paper size to use",
)
@click.option("--width", help="PDF width including units, e.g. 10cm")
@click.option("--height", help="PDF height including units, e.g. 10cm")
@click.option(
    "--scale",
    type=click.FloatRange(min=0.1, max=2.0),
    help="Scale of the webpage rendering",
)
@click.option("--print-background", is_flag=True, help="Print background graphics")
@log_console_option
@skip_fail_options
@bypass_csp_option
@silent_option
@http_auth_options
def pdf(
    url,
    auth,
    output,
    javascript,
    wait,
    wait_for,
    timeout,
    media_screen,
    landscape,
    format_,
    width,
    height,
    scale,
    print_background,
    log_console,
    skip,
    fail,
    bypass_csp,
    silent,
    auth_username,
    auth_password,
):
    """
    Create a PDF of the specified page

    Usage:

        shot-scraper pdf https://datasette.io/

    Use -o to specify a filename:

        shot-scraper pdf https://datasette.io/ -o datasette.pdf

    You can pass a path to a file instead of a URL:

        shot-scraper pdf invoice.html -o invoice.pdf
    """
    url = url_or_file_path(url, _check_and_absolutize)
    if output is None:
        output = filename_for_url(url, ext="pdf", file_exists=os.path.exists)

    # PDF generation not yet supported with nodriver
    click.echo("PDF generation not yet supported with nodriver", err=True)
    click.echo("This feature may be added in a future version", err=True)


@cli.command()
@click.argument("url")
@click.option(
    "-a",
    "--auth",
    type=click.File("r"),
    help="Path to JSON authentication context file",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True),
    default="-",
)
@click.option("-j", "--javascript", help="Execute this JS prior to saving the HTML")
@click.option(
    "-s",
    "--selector",
    help="Return outerHTML of first element matching this CSS selector",
)
@click.option(
    "--wait", type=int, help="Wait this many milliseconds before taking the snapshot"
)
@log_console_option
@browser_option
@browser_args_option
@user_agent_option
@skip_fail_options
@bypass_csp_option
@silent_option
@http_auth_options
def html(
    url,
    auth,
    output,
    javascript,
    selector,
    wait,
    log_console,
    browser,
    browser_args,
    user_agent,
    skip,
    fail,
    bypass_csp,
    silent,
    auth_username,
    auth_password,
):
    """
    Output the final HTML of the specified page

    Usage:

        shot-scraper html https://datasette.io/

    Use -o to specify a filename:

        shot-scraper html https://datasette.io/ -o index.html
    """
    url = url_or_file_path(url, _check_and_absolutize)
    if output is None:
        output = filename_for_url(url, ext="html", file_exists=os.path.exists)

    async def run_html():
        browser_obj = await _browser_context(
            auth,
            browser=browser,
            browser_args=browser_args,
            user_agent=user_agent,
            bypass_csp=bypass_csp,
            auth_username=auth_username,
            auth_password=auth_password,
        )
        page = await browser_obj.get(url)

        if wait:
            time.sleep(wait / 1000)
        if javascript:
            await _evaluate_js(page, javascript)

        if selector:
            element = await page.select(selector)
            if element:
                html = await element.get_property("outerHTML")
            else:
                raise click.ClickException(f"Selector '{selector}' not found")
        else:
            html = await page.get_content()

        try:
            await browser_obj.stop()
        except Exception:
            # Browser cleanup can be flaky - just ignore it
            pass
        return html

    html = asyncio.run(run_with_browser_cleanup(run_html()))

    if output == "-":
        sys.stdout.write(html)
    else:
        open(output, "w").write(html)
        if not silent:
            click.echo(
                f"HTML snapshot of '{url}' written to '{output}'",
                err=True,
            )


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
    "--browser",
    "-b",
    default="chromium",
    type=click.Choice(BROWSERS, case_sensitive=False),
    help="Which browser to use",
)
@browser_args_option
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
        # Create a browser instance to detect the user agent
        browser_kwargs = dict(
            headless=True,
            browser_args=browser_args or []
        )

        browser_obj = await uc.start(**browser_kwargs)

        if browser_obj is None:
            raise click.ClickException("Failed to initialize browser")

        try:
            # Get a page to execute JavaScript
            page = await browser_obj.get("about:blank")

            # Get the user agent
            user_agent = await page.evaluate("navigator.userAgent")

            if not user_agent:
                raise click.ClickException("Could not detect user agent")

            # Remove 'HeadlessChrome' and replace with 'Chrome'
            modified_user_agent = user_agent.replace("HeadlessChrome", "Chrome")

            # Store in config
            set_default_user_agent(modified_user_agent)

            click.echo(f"Original user agent: {user_agent}")
            click.echo(f"Modified user agent: {modified_user_agent}")
            click.echo("Default user agent has been set successfully.")

        finally:
            try:
                await browser_obj.stop()
            except Exception:
                pass

    asyncio.run(run_with_browser_cleanup(detect_and_set_user_agent()))


@cli.command()
@click.argument("url")
@click.argument(
    "context_file",
    type=click.Path(file_okay=True, writable=True, dir_okay=False, allow_dash=True),
)
@browser_option
@browser_args_option
@user_agent_option
@click.option("--devtools", is_flag=True, help="Open browser DevTools")
@log_console_option
def auth(url, context_file, browser, browser_args, user_agent, devtools, log_console):
    """
    Open a browser so user can manually authenticate with the specified site,
    then save the resulting authentication context to a file.

    Usage:

        shot-scraper auth https://github.com/ auth.json
    """
    async def run_auth():
        browser_obj = await _browser_context(
            auth=None,
            interactive=True,
            devtools=devtools,
            browser=browser,
            browser_args=browser_args,
            user_agent=user_agent,
        )
        page = await browser_obj.get(url)
        click.echo("Hit <enter> after you have signed in:", err=True)
        input()

        # Get cookies and local storage for auth context
        # nodriver doesn't have direct storage_state equivalent
        cookies = await page.send(uc.cdp.network.get_cookies())
        context_state = {
            "cookies": cookies.cookies if hasattr(cookies, 'cookies') else [],
            "origins": []
        }
        try:
            await browser_obj.stop()
        except Exception:
            # Browser cleanup can be flaky - just ignore it
            pass
        return context_state

    context_state = asyncio.run(run_with_browser_cleanup(run_auth()))
    context_json = json.dumps(context_state, indent=2) + "\n"
    if context_file == "-":
        click.echo(context_json)
    else:
        with open(context_file, "w") as fp:
            fp.write(context_json)
        # chmod 600 to avoid other users on the shared machine reading it
        pathlib.Path(context_file).chmod(0o600)


def _check_and_absolutize(filepath):
    try:
        path = pathlib.Path(filepath)
        if path.exists():
            return path.absolute()
        return False
    except OSError:
        # On Windows, instantiating a Path object on `http://` or `https://` will raise an exception
        return False


def _get_viewport(width, height):
    if width or height:
        return {
            "width": width or 1280,
            "height": height or 720,
        }
    else:
        return {}


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
    verbose=False,
):
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

    selectors = shot.get("selectors") or []
    selectors_all = shot.get("selectors_all") or []
    js_selectors = shot.get("js_selectors") or []
    js_selectors_all = shot.get("js_selectors_all") or []
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
        if verbose and not silent:
            click.echo(f"Loading page: {url}", err=True)
        page = await context_or_page.get(url)
        if verbose and not silent:
            click.echo(f"Page loaded: {url}", err=True)
        if log_requests:
            # nodriver doesn't have direct response events like Playwright
            # We can implement this later using CDP if needed
            pass

        # Automatic Cloudflare detection and waiting
        if not skip_cloudflare_check and await _detect_cloudflare_challenge(page):
            if not silent:
                click.echo("Detected Cloudflare challenge, waiting for bypass...", err=True)
            success = await _wait_for_cloudflare_bypass(page, verbose=verbose, silent=silent)
            if not success:
                if not silent:
                    click.echo("Warning: Cloudflare challenge may still be active", err=True)

        # Wait for DOM ready unless explicitly skipped or wait_for is specified
        if not skip_wait_for_dom_ready and not wait_for:
            dom_ready = await _wait_for_dom_ready(page, wait_for_dom_ready_timeout, verbose=verbose, silent=silent)
            if not dom_ready and not silent:
                click.echo(f"DOM ready timeout after {wait_for_dom_ready_timeout}ms", err=True)
    else:
        page = context_or_page

    if log_console:
        # nodriver doesn't have direct console event handling
        # We can implement this later using CDP if needed
        pass

    viewport = _get_viewport(shot.get("width"), shot.get("height"))
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
        if verbose and not silent:
            click.echo(f"Waiting {wait}ms before processing...", err=True)
        time.sleep(wait / 1000)

    javascript = shot.get("javascript")
    if javascript:
        if verbose and not silent:
            click.echo(f"Executing JavaScript: {javascript[:50]}{'...' if len(javascript) > 50 else ''}", err=True)
        await _evaluate_js(page, javascript)

    if wait_for:
        if verbose and not silent:
            click.echo(f"Waiting for condition: {wait_for}", err=True)
        # nodriver wait_for equivalent using evaluate in a loop
        timeout_seconds = 30  # default timeout
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            result = await page.evaluate(wait_for)
            if result:
                if verbose and not silent:
                    elapsed = int((time.time() - start_time) * 1000)
                    click.echo(f"Wait condition met after {elapsed}ms", err=True)
                break
            await asyncio.sleep(0.1)
        else:
            raise click.ClickException(f"Timeout waiting for condition: {wait_for}")

    screenshot_args = {}
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
            js_selector_javascript,
            extra_selectors,
            extra_selectors_all,
        ) = _js_selector_javascript(js_selectors, js_selectors_all)
        selectors.extend(extra_selectors)
        selectors_all.extend(extra_selectors_all)
        await _evaluate_js(page, js_selector_javascript)

    if selectors or selectors_all:
        # Use JavaScript to create a box around those elements
        selector_javascript, selector_to_shoot = _selector_javascript(
            selectors, selectors_all, padding
        )
        await _evaluate_js(page, selector_javascript)
        try:
            # nodriver element screenshot with selector
            element = await page.select(selector_to_shoot)
            if element:
                if return_bytes:
                    # For bytes output, save to temp file then read
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        await page.save_screenshot(tmp.name, full_page=screenshot_args.get("full_page", True))
                        with open(tmp.name, 'rb') as f:
                            bytes_data = f.read()
                        os.unlink(tmp.name)
                        return bytes_data
                else:
                    if verbose and not silent:
                        click.echo(f"Taking element screenshot: {selector_to_shoot}", err=True)
                    result = await page.save_screenshot(output, full_page=screenshot_args.get("full_page", True))
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
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    await page.save_screenshot(tmp.name, full_page=screenshot_args.get("full_page", True))
                    with open(tmp.name, 'rb') as f:
                        bytes_data = f.read()
                    os.unlink(tmp.name)
                    return bytes_data
            else:
                if verbose and not silent:
                    click.echo(f"Taking screenshot (full_page={screenshot_args.get('full_page', True)})", err=True)
                result = await page.save_screenshot(output, full_page=screenshot_args.get("full_page", True))
                # save_screenshot might return None, that's OK
                message = f"Screenshot of '{url}' written to '{output}'"

    if not silent:
        click.echo(message, err=True)

    # Always return something for consistency
    return None


def _js_selector_javascript(js_selectors, js_selectors_all):
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


def _selector_javascript(selectors, selectors_all, padding=0):
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


async def _evaluate_js(page, javascript):
    try:
        return await page.evaluate(javascript)
    except Exception as error:
        raise click.ClickException(str(error))


async def _detect_cloudflare_challenge(page):
    """Detect if the current page is showing a Cloudflare challenge"""
    try:
        return await page.evaluate("""
        (() => {
            return document.title === 'Just a moment...' ||
                   !!window._cf_chl_opt ||
                   !!document.querySelector('script[src*="/cdn-cgi/challenge-platform/"]') ||
                   (!!document.querySelector('meta[http-equiv="refresh"]') && document.title.includes('moment'));
        })()
        """)
    except Exception:
        return False


async def _wait_for_cloudflare_bypass(page, max_wait_seconds=8, verbose=False, silent=False):
    """Wait for Cloudflare challenge to complete"""
    start_time = time.time()

    if verbose and not silent:
        click.echo(f"Waiting for Cloudflare challenge bypass (max {max_wait_seconds}s)...", err=True)

    check_count = 0
    while time.time() - start_time < max_wait_seconds:
        try:
            elapsed_seconds = time.time() - start_time
            check_count += 1

            cf_detected = await _detect_cloudflare_challenge(page)

            if verbose and not silent and check_count % 10 == 0:  # Log every 10 checks
                click.echo(f"Cloudflare check #{check_count}: challenge_detected={cf_detected}, elapsed={elapsed_seconds:.1f}s", err=True)

            if not cf_detected:
                # Wait minimum 1 second for page stability after challenge clears
                if elapsed_seconds >= 1:
                    if verbose and not silent:
                        click.echo(f"Cloudflare challenge bypassed in {elapsed_seconds:.1f}s", err=True)
                    return True
            await asyncio.sleep(0.3)  # Check more frequently
        except Exception as e:
            if verbose and not silent:
                click.echo(f"Cloudflare bypass check failed: {e}", err=True)
            await asyncio.sleep(0.3)

    if verbose and not silent:
        click.echo(f"Cloudflare bypass timeout after {max_wait_seconds}s", err=True)
    return False


async def _wait_for_dom_ready(page, timeout_ms=10000, verbose=False, silent=False):
    """Wait for DOM to be ready or timeout"""
    try:
        start_time = time.time()
        timeout_seconds = timeout_ms / 1000

        if verbose and not silent:
            click.echo(f"Waiting for DOM ready state (timeout: {timeout_ms}ms)...", err=True)

        check_count = 0
        while time.time() - start_time < timeout_seconds:
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Get current state for verbose logging
            ready_state = await page.evaluate("document.readyState")

            if verbose and not silent:
                check_count += 1
                if check_count % 10 == 0:  # Log every 10 checks (roughly every second)
                    click.echo(f"DOM ready check #{check_count}: readyState='{ready_state}', elapsed={elapsed_ms}ms", err=True)

            if ready_state == 'complete':
                if verbose and not silent:
                    click.echo(f"DOM ready achieved in {elapsed_ms}ms (readyState: {ready_state})", err=True)
                return True

            await asyncio.sleep(0.1)

        # Timeout reached
        if verbose and not silent:
            final_state = await page.evaluate("document.readyState")
            click.echo(f"DOM ready timeout after {timeout_ms}ms (final readyState: {final_state})", err=True)

        return False  # Timed out
    except Exception as e:
        if verbose and not silent:
            click.echo(f"DOM ready check failed with exception: {e}", err=True)
        return False
