import urllib.parse
import urllib.request
import urllib.error
import re
import json
import os
import pathlib

disallowed_re = re.compile("[^a-zA-Z0-9_-]")


def file_exists_never(filename):
    return False


def filename_for_url(url, ext=None, file_exists=file_exists_never):
    ext = ext or "png"
    bits = urllib.parse.urlparse(url)
    filename = (bits.netloc + bits.path).replace(".", "-").replace("/", "-").rstrip("-")
    # Remove any characters outside of the allowed range
    base_filename = disallowed_re.sub("", filename).lstrip("-")
    filename = base_filename + "." + ext
    suffix = 0
    while file_exists(filename):
        suffix += 1
        filename = f"{base_filename}.{suffix}.{ext}"
    return filename


def url_or_file_path(url, file_exists=file_exists_never):
    # If url exists as a file, convert that to file:/
    file_path = file_exists(url)
    if file_path:
        return f"file:{file_path}"
    if not (url.startswith("http://") or url.startswith("https://")):
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


def get_config_dir():
    """Get the shot-power-scraper config directory path"""
    return pathlib.Path.home() / ".config" / "shot-power-scraper"


def get_config_file():
    """Get the shot-power-scraper config file path"""
    return get_config_dir() / "config.json"


def load_config():
    """Load configuration from the config file"""
    config_file = get_config_file()
    if not config_file.exists():
        return {}
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config):
    """Save configuration to the config file"""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = get_config_file()
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)


def get_default_user_agent():
    """Get the default user agent from config"""
    config = load_config()
    return config.get('user_agent')


def set_default_user_agent(user_agent):
    """Set the default user agent in config"""
    config = load_config()
    config['user_agent'] = user_agent
    save_config(config)


def get_default_ad_block():
    """Get the default ad block setting from config"""
    config = load_config()
    return config.get('ad_block', False)


def get_default_popup_block():
    """Get the default popup block setting from config"""
    config = load_config()
    return config.get('popup_block', False)


def set_default_ad_block(ad_block):
    """Set the default ad block setting in config"""
    config = load_config()
    config['ad_block'] = ad_block
    save_config(config)


def set_default_popup_block(popup_block):
    """Set the default popup block setting in config"""
    config = load_config()
    config['popup_block'] = popup_block
    save_config(config)
