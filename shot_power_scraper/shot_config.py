"""Configuration classes for shot-power-scraper"""
import json
import pathlib


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


class ShotConfig:
    """Configuration for screenshot and PDF operations"""
    def __init__(self, shot):
        # We treat keys = None as using the default value
        # pass False or 0 or "" if you want it to be "nothing"
        shot = {k: v for k, v in shot.items() if v is not None}
        # load any settings from config.json file
        config_file_settings = load_config()
        self.url = shot.get("url")
        self.output = shot.get("output", "").strip()
        self.quality = shot.get("quality")
        self.omit_background = shot.get("omit_background")
        self.wait = shot.get("wait", 250)
        self.wait_for = shot.get("wait_for")
        self.padding = shot.get("padding", 0)
        self.skip_cloudflare_check = shot.get("skip_cloudflare_check", False)
        self.timeout = shot.get("timeout", 30)
        self.skip_wait_for_load = shot.get("skip_wait_for_load", False)
        self.javascript = shot.get("javascript")
        self.full_page = not shot.get("height")
        self.ad_block = shot.get("ad_block", config_file_settings.get("ad_block", False))
        self.popup_block = shot.get("popup_block", config_file_settings.get("popup_block", False))
        self.user_agent = shot.get("user_agent", config_file_settings.get("user_agent"))
        self.skip_shot = shot.get("skip_shot", False)
        self.save_html = shot.get("save_html", False)
        self.width = shot.get("width", 1280)
        self.height = shot.get("height", 720)
        self.trigger_lazy_load = shot.get("trigger_lazy_load", False)
        self.resize_viewport = shot.get("resize_viewport", True)

        # PDF specific options
        self.pdf_landscape = shot.get("pdf_landscape", False)
        self.pdf_scale = shot.get("pdf_scale", 1.0)
        self.pdf_print_background = shot.get("pdf_print_background", False)
        self.pdf_media_screen = shot.get("pdf_media_screen", False)
        self.pdf_css = shot.get("pdf_css")

        # Execution options
        self.log_console = shot.get("log_console", False)
        self.return_js_result = shot.get("return_js_result", False)
        self.log_requests = shot.get("log_requests", False)

        # Browser options
        self.auth = shot.get("auth")
        self.interactive = shot.get("interactive", False)
        self.devtools = shot.get("devtools", False)
        self.scale_factor = shot.get("scale_factor")
        self.browser = shot.get("browser", "chromium")
        self.browser_args = shot.get("browser_args")
        self.reduced_motion = shot.get("reduced_motion", False)
        self.bypass_csp = shot.get("bypass_csp", False)
        self.auth_username = shot.get("auth_username")
        self.auth_password = shot.get("auth_password")
        self.record_har_path = shot.get("record_har_path")

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
