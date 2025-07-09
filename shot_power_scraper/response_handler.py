"""HTTP Response handler for shot-scraper"""
import asyncio
from typing import Optional, Tuple
import nodriver as uc
from shot_power_scraper.browser import Config
import click


class ResponseHandler:
    """Handles HTTP responses to capture status codes"""

    def __init__(self):
        self.response_status: Optional[int] = None
        self.response_url: Optional[str] = None
        self.main_request_id: Optional[str] = None
        self._response_received = asyncio.Event()

    async def on_response_received(self, event: uc.cdp.network.ResponseReceived):
        """Handler for ResponseReceived events"""
        # Only capture the main frame response
        if event.type_ == uc.cdp.network.ResourceType.DOCUMENT:
            self.response_status = event.response.status
            self.response_url = event.response.url
            self.main_request_id = event.request_id
            self._response_received.set()

            if Config.verbose:
                click.echo(f"Response received: {event.response.status} {event.response.url}", err=True)

    async def wait_for_response(self, timeout: float = 30) -> Tuple[Optional[int], Optional[str]]:
        """Wait for the main response and return status and URL"""
        await asyncio.wait_for(self._response_received.wait(), timeout=timeout)
        return self.response_status, self.response_url

    def reset(self):
        """Reset the handler for a new request"""
        self.response_status = None
        self.response_url = None
        self.main_request_id = None
        self._response_received.clear()
