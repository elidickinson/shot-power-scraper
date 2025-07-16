"""Configuration classes for shot-power-scraper"""


class ShotConfig:
    """Configuration for screenshot and PDF operations"""
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
        self.full_page = not shot.get("height")
        self.ad_block = shot.get("ad_block", False)
        self.popup_block = shot.get("popup_block", False)
        self.skip_shot = shot.get("skip_shot")
        self.save_html = shot.get("save_html")
        self.width = shot.get("width")
        self.height = shot.get("height")
        self.trigger_lazy_load = shot.get("trigger_lazy_load", False)

        # PDF specific options
        self.pdf_landscape = shot.get("pdf_landscape", False)
        self.pdf_scale = shot.get("pdf_scale", 1.0)
        self.pdf_print_background = shot.get("pdf_print_background", False)
        self.pdf_media_screen = shot.get("pdf_media_screen", False)

        # Execution options
        self.log_console = shot.get("log_console", False)
        self.skip = shot.get("skip", False)
        self.fail = shot.get("fail", False)
        self.silent = shot.get("silent", False)
        self.return_js_result = shot.get("return_js_result", False)
        self.log_requests = shot.get("log_requests")

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