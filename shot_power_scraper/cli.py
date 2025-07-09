import subprocess
import sys
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

from shot_power_scraper.utils import filename_for_url, load_github_script, url_or_file_path, set_default_user_agent, get_default_ad_block, get_default_popup_block
from shot_power_scraper.browser import Config, create_browser_context, cleanup_browser
from shot_power_scraper.screenshot import take_shot
from shot_power_scraper.page_utils import evaluate_js

BROWSERS = ("chromium", "chrome", "chrome-beta")


async def run_with_browser_cleanup(coro):
    """Run an async function and give nodriver time to cleanup afterwards."""
    result = await coro
    await asyncio.sleep(0.25)  # Give nodriver time to cleanup background processes
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


async def setup_blocking_extensions(extensions, ad_block, popup_block, verbose, silent):
    """Setup blocking extensions based on requested flags"""
    import tempfile
    import shutil

    base_extension_path = os.path.join(os.path.dirname(__file__), '..', 'extensions', 'shot-scraper-blocker')

    if not os.path.exists(base_extension_path):
        if not silent:
            click.echo(f"Warning: Base extension not found at {base_extension_path}", err=True)
        return

    # Create a temporary extension directory
    temp_ext_dir = tempfile.mkdtemp(prefix="shot_scraper_ext_")

    # Copy base extension files
    shutil.copytree(base_extension_path, temp_ext_dir, dirs_exist_ok=True)

    # Create custom rules.json based on selected filters
    rules_path = os.path.join(temp_ext_dir, "rules.json")
    create_filtered_rules(rules_path, ad_block, popup_block, base_extension_path, verbose)

    extensions.append(temp_ext_dir)

    if verbose:
        enabled_filters = []
        if ad_block:
            enabled_filters.append("ad blocking")
        if popup_block:
            enabled_filters.append("popup blocking")
        click.echo(f"Blocking enabled: {', '.join(enabled_filters)}", err=True)


def create_filtered_rules(rules_path, ad_block, popup_block, base_extension_path, verbose):
    """Create a rules.json file with only the selected filter categories"""
    import json

    # Load rules from category files
    combined_rules = []
    rule_id = 1

    downloads_dir = os.path.join(base_extension_path, "downloads")

    # Ad blocking rules
    if ad_block:
        ad_rules_file = os.path.join(base_extension_path, "ad-block-rules.json")
        if os.path.exists(ad_rules_file):
            try:
                with open(ad_rules_file, 'r') as f:
                    rules = json.load(f)
                for rule in rules:
                    rule["id"] = rule_id
                    rule_id += 1
                combined_rules.extend(rules)
                if verbose:
                    click.echo(f"Added {len(rules)} ad-block rules", err=True)
            except Exception as e:
                if verbose:
                    click.echo(f"Warning: Could not load ad-block rules: {e}", err=True)

    # Popup blocking rules
    if popup_block:
        popup_rules_file = os.path.join(base_extension_path, "popup-block-rules.json")
        if os.path.exists(popup_rules_file):
            try:
                with open(popup_rules_file, 'r') as f:
                    rules = json.load(f)
                for rule in rules:
                    rule["id"] = rule_id
                    rule_id += 1
                combined_rules.extend(rules)
                if verbose:
                    click.echo(f"Added {len(rules)} popup-block rules", err=True)
            except Exception as e:
                if verbose:
                    click.echo(f"Warning: Could not load popup-block rules: {e}", err=True)

    # Limit to Chrome's 30,000 rule limit
    if len(combined_rules) > 30000:
        combined_rules = combined_rules[:30000]
        if verbose:
            click.echo(f"Limited rules to 30,000 (Chrome's limit)", err=True)

    # Write combined rules
    with open(rules_path, 'w') as f:
        json.dump(combined_rules, f, indent=2)

    if verbose:
        click.echo(f"Created {len(combined_rules)} total blocking rules", err=True)


async def configure_blocking_extension(page, ad_block, popup_block, verbose):
    """No configuration needed - extension configured via file generation"""
    if verbose:
        click.echo("Extension configured via rules file", err=True)




# Small utility functions stay here
def console_log(msg):
    click.echo(msg, err=True)


def _check_and_absolutize(filepath):
    try:
        path = pathlib.Path(filepath)
        if path.exists():
            return path.absolute()
        return False
    except OSError:
        # On Windows, instantiating a Path object on `http://` or `https://` will raise an exception
        return False


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
    click.option("--log-console", "--console-log", is_flag=True, help="Write console.log() to stderr")(
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
    "--wait", type=int, default=250, help="Wait this many milliseconds before taking the screenshot (default: 250)"
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
    "--skip-wait-for-load",
    is_flag=True,
    help="Skip waiting for window load event"
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
@click.option(
    "--save-html",
    is_flag=True,
    help="Save HTML content alongside the screenshot with the same base name"
)
@click.option(
    "--ad-block/--no-ad-block",
    default=None,
    help="Enable/disable ad blocking (overrides config file setting)"
)
@click.option(
    "--popup-block/--no-popup-block",
    "--block-popups/--no-block-popups",
    default=None,
    help="Enable/disable popup blocking (overrides config file setting)"
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
    skip_wait_for_load,
    full_page,
    verbose,
    save_html,
    ad_block,
    popup_block,
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
    # Set global config
    Config.verbose = verbose
    Config.silent = silent

    if output is None:
        ext = "jpg" if quality else None
        output = filename_for_url(url, ext=ext, file_exists=os.path.exists)

    scale_factor = normalize_scale_factor(retina, scale_factor)

    # Resolve ad_block and popup_block from config if not explicitly set
    ad_block, popup_block = resolve_blocking_config(ad_block, popup_block)

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
        "skip_wait_for_load": skip_wait_for_load,
        "full_page": full_page,
        "verbose": verbose,
        "save_html": save_html,
        "configure_extension": ad_block or popup_block,
        "ad_block": ad_block,
        "popup_block": popup_block,
    }
    interactive = interactive or devtools

    async def run_shot():
        use_existing_page = False
        browser_obj = None
        try:
            # Add blocking extensions if requested
            extensions = []
            if ad_block or popup_block:
                await setup_blocking_extensions(extensions, ad_block, popup_block, verbose, silent)

            browser_obj = await create_browser_context(
                auth=auth,
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
                extensions=extensions if extensions else None,
            )

            # Don't configure extension here - do it after page loads

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
                )
        except Exception as e:
            raise click.ClickException(str(e))
        finally:
            if browser_obj:
                await cleanup_browser(browser_obj)

    run_async(run_with_browser_cleanup(run_shot()))




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
@click.option(
    "--ad-block/--no-ad-block",
    default=None,
    help="Enable/disable ad blocking (overrides config file setting)"
)
@click.option(
    "--popup-block/--no-popup-block",
    "--block-popups/--no-block-popups",
    default=None,
    help="Enable/disable popup blocking (overrides config file setting)"
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
    ad_block,
    popup_block,
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
    # Set global config
    Config.verbose = verbose
    Config.silent = silent

    if (har or har_zip) and not har_file:
        har_file = filename_for_url(
            "trace", ext="har.zip" if har_zip else "har", file_exists=os.path.exists
        )

    scale_factor = normalize_scale_factor(retina, scale_factor)

    # Resolve ad_block and popup_block from config if not explicitly set
    ad_block, popup_block = resolve_blocking_config(ad_block, popup_block)
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

    # Set global config
    Config.verbose = verbose
    Config.silent = silent

    async def run_multi():
        # Add blocking extensions if requested
        extensions = []
        if ad_block or popup_block:
            await setup_blocking_extensions(extensions, ad_block, popup_block, verbose, silent)

        browser_obj = await create_browser_context(
            auth=auth,
            scale_factor=scale_factor,
            browser=browser,
            browser_args=browser_args,
            user_agent=user_agent,
            timeout=timeout,
            reduced_motion=reduced_motion,
            auth_username=auth_username,
            auth_password=auth_password,
            record_har_path=har_file or None,
            extensions=extensions if extensions else None,
        )

        # Extension will be configured per-shot in take_shot() function
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
                    # Add extension configuration to each shot
                    if ad_block or popup_block:
                        shot["configure_extension"] = True
                        shot["ad_block"] = ad_block
                        shot["popup_block"] = popup_block

                    # Set timeout if not already specified in the shot
                    if timeout and "timeout" not in shot:
                        shot["timeout"] = timeout

                    try:
                        await take_shot(
                            browser_obj,
                            shot,
                            log_console=log_console,
                            skip=skip,
                            fail=fail,
                            silent=silent,
                        )
                    except Exception as e:
                        if fail or fail_on_error:
                            raise click.ClickException(str(e))
                        else:
                            click.echo(str(e), err=True)
                            continue
        finally:
            if browser_obj:
                await cleanup_browser(browser_obj)
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

    run_async(run_with_browser_cleanup(run_multi()))


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
        browser_obj = await create_browser_context(
            auth,
            timeout=timeout,
            bypass_csp=bypass_csp,
            auth_username=auth_username,
            auth_password=auth_password,
        )

        # Get a blank page first to set up console logging
        page = await browser_obj.get("about:blank")

        # Set up console logging BEFORE navigating
        if log_console:
            from shot_power_scraper.console_logger import ConsoleLogger
            console_logger = ConsoleLogger(silent=False)
            await console_logger.setup(page)

        # Now navigate to the actual URL
        await page.get(url)

        if javascript:
            await evaluate_js(page, javascript)

        # Accessibility not implemented
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
    "--wait", type=int, default=250, help="Wait this many milliseconds before taking the screenshot (default: 250)"
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
        browser_obj = await create_browser_context(
            auth,
            browser=browser,
            browser_args=browser_args,
            user_agent=user_agent,
            reduced_motion=reduced_motion,
            bypass_csp=bypass_csp,
            auth_username=auth_username,
            auth_password=auth_password,
        )

        # Get a blank page first to set up console logging
        page = await browser_obj.get("about:blank")

        # Set up console logging BEFORE navigating
        if log_console:
            from shot_power_scraper.console_logger import ConsoleLogger
            console_logger = ConsoleLogger(silent=False)
            await console_logger.setup(page)

        # Now navigate to the actual URL
        await page.get(url)

        result = await evaluate_js(page, javascript)
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
    "--wait", type=int, default=250, help="Wait this many milliseconds before taking the screenshot (default: 250)"
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
    NOT IMPLEMENTED - Create a PDF of the specified page

    This command is not yet implemented with nodriver.
    """
    click.echo("Error: PDF generation is not implemented with nodriver", err=True)
    click.echo("Use the screenshot commands instead for capturing page content.", err=True)
    raise click.Abort()


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
    "--wait", type=int, default=250, help="Wait this many milliseconds before taking the snapshot (default: 250)"
)
@click.option(
    "--timeout",
    type=int,
    help="Wait this many milliseconds before failing",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging to stdout"
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
    timeout,
    verbose,
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

    # Set global config
    Config.verbose = verbose
    Config.silent = silent

    async def run_html():
        browser_obj = await create_browser_context(
            auth,
            browser=browser,
            browser_args=browser_args,
            user_agent=user_agent,
            bypass_csp=bypass_csp,
            auth_username=auth_username,
            auth_password=auth_password,
        )

        # Get a blank page first to set up console logging
        page = await browser_obj.get("about:blank")

        # Set up console logging BEFORE navigating
        console_logger = None
        if log_console:
            from shot_power_scraper.console_logger import ConsoleLogger
            console_logger = ConsoleLogger(silent=silent)
            await console_logger.setup(page)

        # Now navigate to the actual URL
        await page.get(url)

        # Check if page failed to load
        from shot_power_scraper.page_utils import detect_navigation_error
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

        if wait:
            if verbose:
                click.echo(f"Waiting {wait}ms before processing...", err=True)
            time.sleep(wait / 1000)
        if javascript:
            await evaluate_js(page, javascript)

        # Wait for page to be ready with timeout
        if timeout:
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

        if selector:
            element = await page.select(selector)
            if element:
                html = await element.get_property("outerHTML")
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

            # Import here to avoid circular imports
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
        browser_obj = await create_browser_context(
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
        await cleanup_browser(browser_obj)
        return context_state

    context_state = run_async(run_with_browser_cleanup(run_auth()))
    context_json = json.dumps(context_state, indent=2) + "\n"
    if context_file == "-":
        click.echo(context_json)
    else:
        with open(context_file, "w") as fp:
            fp.write(context_json)
        # chmod 600 to avoid other users on the shared machine reading it
        pathlib.Path(context_file).chmod(0o600)
