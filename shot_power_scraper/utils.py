import urllib.parse
import urllib.request
import urllib.error
import re
import pathlib
import os
import nodriver as uc

disallowed_re = re.compile("[^a-zA-Z0-9_-]")


def filename_for_url(url, ext=None):
    ext = ext or "png"
    bits = urllib.parse.urlparse(url)

    # Special handling for file:// URLs - use basename
    if bits.scheme == 'file':
        path = pathlib.Path(bits.path)
        base_filename = path.stem  # filename without extension
    else:
        # Original logic for HTTP URLs
        filename = (bits.netloc + bits.path).replace(".", "-").replace("/", "-").rstrip("-")
        # Remove any characters outside of the allowed range
        base_filename = disallowed_re.sub("", filename).lstrip("-")

    filename = base_filename + "." + ext
    suffix = 0
    while os.path.exists(filename):
        suffix += 1
        filename = f"{base_filename}.{suffix}.{ext}"
    return filename


def url_or_file_path(url):
    # Check if url exists as a file and convert to file:// URL
    try:
        path = pathlib.Path(url)
        if path.exists():
            return f"file://{path.absolute()}"
    except OSError:
        # On Windows, instantiating a Path object on `http://` or `https://` will raise an exception
        pass

    # Add http:// prefix if no scheme provided
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
        return f"http://{url}"
    return url


def load_github_script(github_path: str) -> str:
    """
    Load JavaScript script from GitHub

    Format: username/repo/path/to/file.js
      or username/file.js which means username/shot-scraper-scripts/file.js
    """
    if not github_path.endswith(".js"):
        github_path += ".js"
    parts = github_path.split("/")

    if len(parts) == 2:
        # Short form: username/file.js
        username, file_name = parts
        parts = [username, "shot-power-scraper-scripts", file_name]

    if len(parts) < 3:
        raise ValueError(
            "GitHub path format should be 'username/repo/path/to/file.js' or 'username/file.js'"
        )

    username = parts[0]
    repo = parts[1]
    file_path = "/".join(parts[2:])

    # Fetch from GitHub
    import urllib.request

    url = f"https://raw.githubusercontent.com/{username}/{repo}/main/{file_path}"
    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                return response.read().decode("utf-8")
            else:
                raise ValueError(
                    f"Failed to load content from GitHub: HTTP {response.status}\n"
                    f"URL: {url}"
                )
    except urllib.error.URLError as e:
        raise ValueError(f"Error fetching from GitHub: {e}")


async def capture_mhtml(page):
    """Capture MHTML (web archive) content from a page using Chrome DevTools Protocol"""
    try:
        # Use Chrome DevTools Protocol Page.captureSnapshot to get MHTML
        result = await page.send(uc.cdp.page.capture_snapshot())
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to capture MHTML: {e}")
