#!/usr/bin/env python3
"""
Screenshot API Server

A FastAPI server that provides REST endpoints for taking screenshots using shot-power-scraper.

Usage:
    python api_server.py [--browser-arg ARG ...]

Example server startup:
    # Start server with custom browser arguments
    python api_server.py --browser-arg --window-size=1920,1080 --browser-arg --disable-dev-shm-usage

    # Start server with proxy settings
    python api_server.py --browser-arg "--proxy-server=http://localhost:8888"

    # Start server on different host/port
    python api_server.py --host 0.0.0.0 --port 8080

Example API calls:
    # Simple screenshot
    curl -X POST http://localhost:8123/shot \
        -H "Content-Type: application/json" \
        -d '{"url": "https://example.com"}' \
        -o screenshot.png

    # Screenshot with options
    curl -X POST http://localhost:8123/shot \
        -H "Content-Type: application/json" \
        -d '{
            "url": "https://example.com",
            "width": 1280,
            "height": 720,
            "wait": 2000,
            "full_page": true
        }' \
        -o screenshot.png

    # Screenshot with selector
    curl -X POST http://localhost:8123/shot \
        -H "Content-Type: application/json" \
        -d '{
            "url": "https://example.com",
            "selector": "#main-content",
            "padding": 20
        }' \
        -o screenshot.png

    # Extract HTML content
    curl -X POST http://localhost:8123/html \
        -H "Content-Type: application/json" \
        -d '{"url": "https://example.com"}' \
        | jq '.html'

    # Extract HTML with selector
    curl -X POST http://localhost:8123/html \
        -H "Content-Type: application/json" \
        -d '{
            "url": "https://example.com",
            "selector": "#main-content",
            "wait": 1000
        }' \
        | jq '.html'
"""

from fastapi import FastAPI, HTTPException, Response, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from contextlib import asynccontextmanager
import asyncio
import os
import sys
from pathlib import Path
import click
import logging
from datetime import datetime

# Add parent directory to path to import shot_power_scraper
sys.path.insert(0, str(Path(__file__).parent))

from shot_power_scraper.browser import create_browser_context, Config
from shot_power_scraper.screenshot import take_shot
from shot_power_scraper.cli import browser_args_option
from shot_power_scraper.page_utils import evaluate_js, detect_navigation_error
import time

# Global browser instance for reuse
browser_instance = None
browser_lock = asyncio.Lock()
# Global browser args from CLI - will be set before app creation
global_browser_args = []

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("shot-power-scraper-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup
    global browser_instance
    if os.getenv("PRELOAD_BROWSER", "true").lower() in ("true", "1", "yes"):
        await get_browser()

    yield

    # Shutdown
    if browser_instance:
        try:
            await browser_instance.stop()
        except:
            pass
        browser_instance = None


# Create app after parsing CLI args (see main function)
app = None

class ShotRequest(BaseModel):
    """Request model for screenshot endpoint"""
    url: str = Field(..., description="URL to screenshot")
    width: Optional[int] = Field(None, description="Viewport width in pixels")
    height: Optional[int] = Field(None, description="Viewport height in pixels")
    selector: Optional[str] = Field(None, description="CSS selector for element to screenshot")
    selectors: Optional[List[str]] = Field(None, description="Multiple CSS selectors")
    selector_all: Optional[str] = Field(None, description="CSS selector for all matching elements")
    selectors_all: Optional[List[str]] = Field(None, description="Multiple CSS selectors for all matches")
    js_selector: Optional[str] = Field(None, description="JavaScript selector expression")
    js_selectors: Optional[List[str]] = Field(None, description="Multiple JavaScript selectors")
    js_selector_all: Optional[str] = Field(None, description="JavaScript selector for all matches")
    js_selectors_all: Optional[List[str]] = Field(None, description="Multiple JavaScript selectors for all matches")
    padding: Optional[int] = Field(0, description="Padding around selected elements in pixels")
    javascript: Optional[str] = Field(None, description="JavaScript to execute before screenshot")
    quality: Optional[int] = Field(None, description="JPEG quality (1-100)")
    wait: Optional[int] = Field(None, description="Wait time in milliseconds before screenshot")
    wait_for: Optional[str] = Field(None, description="JavaScript expression to wait for")
    timeout: Optional[int] = Field(30000, description="Timeout in milliseconds")
    scale_factor: Optional[float] = Field(1.0, description="Scale factor for screenshot")
    omit_background: Optional[bool] = Field(False, description="Omit background for transparency")
    full_page: Optional[bool] = Field(None, description="Capture full scrollable page")
    skip_cloudflare_check: Optional[bool] = Field(False, description="Skip Cloudflare challenge detection")
    wait_for_dom_ready_timeout: Optional[int] = Field(10000, description="DOM ready timeout in milliseconds")
    skip_wait_for_dom_ready: Optional[bool] = Field(False, description="Skip waiting for DOM ready")
    user_agent: Optional[str] = Field(None, description="Custom User-Agent header")
    auth_username: Optional[str] = Field(None, description="HTTP Basic Auth username")
    auth_password: Optional[str] = Field(None, description="HTTP Basic Auth password")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "width": 1280,
                "height": 720,
                "wait": 2000,
                "full_page": False
            }
        }


class HtmlRequest(BaseModel):
    """Request model for HTML content extraction endpoint"""
    url: str = Field(..., description="URL to extract HTML from")
    selector: Optional[str] = Field(None, description="CSS selector for specific element (returns outerHTML)")
    javascript: Optional[str] = Field(None, description="JavaScript to execute before extracting HTML")
    wait: Optional[int] = Field(250, description="Wait time in milliseconds before extracting HTML")
    timeout: Optional[int] = Field(30000, description="Timeout in milliseconds")
    user_agent: Optional[str] = Field(None, description="Custom User-Agent header")
    auth_username: Optional[str] = Field(None, description="HTTP Basic Auth username")
    auth_password: Optional[str] = Field(None, description="HTTP Basic Auth password")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "selector": "#main-content",
                "wait": 1000
            }
        }


async def get_browser():
    """Get or create a shared browser instance"""
    global browser_instance, global_browser_args
    async with browser_lock:
        if browser_instance is None:
            Config.verbose = os.getenv("VERBOSE", "").lower() in ("true", "1", "yes")
            Config.silent = not Config.verbose

            # Debug logging
            if global_browser_args:
                logger.info(f"Creating browser with args: {global_browser_args}")

            browser_instance = await create_browser_context(
                browser="chromium",
                browser_args=global_browser_args,
                timeout=60000,
            )
            logger.info("Browser instance created successfully")
        return browser_instance


async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses"""
    start_time = datetime.now()

    # Log request
    logger.info(f"Request: {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")

    # Process request
    try:
        response = await call_next(request)

        # Calculate response time
        duration = (datetime.now() - start_time).total_seconds()

        # Log response
        logger.info(f"Response: {response.status_code} - {duration:.3f}s")

        return response

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Request failed after {duration:.3f}s: {str(e)}")
        raise




async def root():
    """API documentation"""
    return {
        "message": "Shot Power Scraper API Server",
        "version": "1.0.0",
        "endpoints": {
            "/shot": "POST - Take a screenshot",
            "/html": "POST - Extract HTML content",
            "/health": "GET - Health check"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "features": [
            "Screenshot capture with CSS/JS selectors",
            "HTML content extraction",
            "JavaScript execution before capture",
            "Cloudflare bypass support",
            "Full page screenshots"
        ]
    }


async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


async def shot(request: ShotRequest):
    """Take a screenshot and return the image"""
    try:
        # Get browser instance
        browser = await get_browser()

        # Build shot configuration
        shot_config = {
            "url": request.url,
            "width": request.width,
            "height": request.height,
            "selectors": request.selectors or [],
            "selectors_all": request.selectors_all or [],
            "js_selectors": request.js_selectors or [],
            "js_selectors_all": request.js_selectors_all or [],
            "padding": request.padding,
            "javascript": request.javascript,
            "quality": request.quality,
            "wait": request.wait,
            "wait_for": request.wait_for,
            "timeout": request.timeout,
            "scale_factor": request.scale_factor,
            "omit_background": request.omit_background,
            "full_page": request.full_page,
            "skip_cloudflare_check": request.skip_cloudflare_check,
            "wait_for_dom_ready_timeout": request.wait_for_dom_ready_timeout,
            "skip_wait_for_dom_ready": request.skip_wait_for_dom_ready,
        }

        # Add single selector fields to arrays if provided
        if request.selector:
            shot_config["selectors"].append(request.selector)
        if request.selector_all:
            shot_config["selectors_all"].append(request.selector_all)
        if request.js_selector:
            shot_config["js_selectors"].append(request.js_selector)
        if request.js_selector_all:
            shot_config["js_selectors_all"].append(request.js_selector_all)

        # Handle authentication
        if request.auth_username and request.auth_password:
            # Note: nodriver doesn't have built-in HTTP auth like Playwright
            # This would need to be implemented via CDP or page manipulation
            pass

        # Take the screenshot
        screenshot_bytes = await take_shot(
            browser,
            shot_config,
            return_bytes=True,
            silent=True
        )

        # Determine content type based on quality setting
        if request.quality:
            content_type = "image/jpeg"
        else:
            content_type = "image/png"

        # Return the image
        return Response(
            content=screenshot_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=screenshot.{'jpg' if request.quality else 'png'}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def html(request: HtmlRequest):
    """Extract HTML content from a page"""
    try:
        # Get browser instance
        browser = await get_browser()

        # Get a new page
        page = await browser.get(request.url)

        # Check if page failed to load
        has_error, error_msg = await detect_navigation_error(page, request.url)
        if has_error:
            raise HTTPException(status_code=400, detail=f"Page failed to load: {error_msg}")

        # Wait if specified
        if request.wait:
            time.sleep(request.wait / 1000)

        # Execute JavaScript if provided
        if request.javascript:
            await evaluate_js(page, request.javascript)

        # Extract HTML
        if request.selector:
            element = await page.select(request.selector)
            if element:
                html_content = await element.get_property("outerHTML")
            else:
                raise HTTPException(status_code=404, detail=f"Selector '{request.selector}' not found")
        else:
            html_content = await page.get_content()

        return {
            "url": request.url,
            "html": html_content,
            "selector": request.selector,
            "timestamp": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@click.command()
@browser_args_option
@click.option(
    "--host",
    default=lambda: os.getenv("HOST", "127.0.0.1"),
    help="Host to bind to (default: 127.0.0.1, can be overridden with HOST env var)"
)
@click.option(
    "--port",
    type=int,
    default=lambda: int(os.getenv("PORT", "8123")),
    help="Port to bind to (default: 8123, can be overridden with PORT env var)"
)
@click.option(
    "--reload",
    is_flag=True,
    default=lambda: os.getenv("RELOAD", "false").lower() in ("true", "1", "yes"),
    help="Enable auto-reload (default: false, can be overridden with RELOAD env var)"
)
def main(browser_args, host, port, reload):
    """Start the Shot Power Scraper API Server"""
    import uvicorn

    # Store browser args globally BEFORE creating the app
    global global_browser_args, app
    global_browser_args = list(browser_args)

    # Now create the FastAPI app with the browser args already set
    app = FastAPI(
        title="Shot Power Scraper API",
        version="1.0.0",
        description="""
        A powerful API for automated web screenshots and HTML extraction with anti-detection capabilities.

        ## Features
        - Screenshot capture with CSS/JS selectors
        - HTML content extraction
        - JavaScript execution before capture
        - Cloudflare bypass support
        - Full page screenshots
        - Shared browser instance for performance

        ## Authentication
        Currently no authentication required. Set environment variables for production use.

        ## Rate Limiting
        No rate limiting implemented. Consider adding for production use.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "screenshots", "description": "Screenshot capture operations"},
            {"name": "content", "description": "HTML content extraction"},
            {"name": "utility", "description": "Health checks and API information"}
        ],
        lifespan=lifespan
    )

    # Add logging middleware
    app.middleware("http")(log_requests)

    # Register routes with tags
    app.get("/", tags=["utility"], summary="API Information")(root)
    app.get("/health", tags=["utility"], summary="Health Check")(health)
    app.post("/shot", tags=["screenshots"], summary="Capture Screenshot")(shot)
    app.post("/html", tags=["content"], summary="Extract HTML Content")(html)

    click.echo(f"Starting Shot Power Scraper API Server on {host}:{port}")
    click.echo(f"API documentation available at http://{host}:{port}/docs")
    click.echo("\nAvailable endpoints:")
    click.echo(f"  POST /shot - Take screenshots")
    click.echo(f"  POST /html - Extract HTML content")
    click.echo(f"  GET /health - Health check")
    click.echo(f"  GET / - API information")
    click.echo("\nConfiguration:")
    click.echo(f"  HOST={host}")
    click.echo(f"  PORT={port}")
    click.echo(f"  RELOAD={reload}")
    click.echo(f"  VERBOSE={os.getenv('VERBOSE', 'false')}")
    click.echo(f"  PRELOAD_BROWSER={os.getenv('PRELOAD_BROWSER', 'true')}")

    if browser_args:
        click.echo(f"  Browser args: {list(browser_args)}")

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    main()
