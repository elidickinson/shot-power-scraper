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
from shot_power_scraper.shot_config import ShotConfig
from shot_power_scraper.cli import browser_args_option
from shot_power_scraper.page_utils import evaluate_js, detect_navigation_error, navigate_to_page

# Global browser instance for reuse
browser_instance = None

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
        browser_args = getattr(app.state, 'browser_args', [])
        await get_browser(browser_args)

    yield

    # Shutdown
    if browser_instance:
        try:
            await browser_instance.stop()
        except:
            pass
        browser_instance = None


# Create FastAPI app
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

class ShotRequest(BaseModel):
    """Request model for screenshot endpoint"""
    url: str = Field(..., description="URL to screenshot")
    width: Optional[int] = Field(None, description="Viewport width in pixels")
    height: Optional[int] = Field(None, description="Viewport height in pixels")
    selectors: Optional[List[str]] = Field([], description="CSS selectors for elements to screenshot")
    selectors_all: Optional[List[str]] = Field([], description="CSS selectors for all matching elements")
    js_selectors: Optional[List[str]] = Field([], description="JavaScript selector expressions")
    js_selectors_all: Optional[List[str]] = Field([], description="JavaScript selectors for all matches")
    padding: Optional[int] = Field(0, description="Padding around selected elements in pixels")
    javascript: Optional[str] = Field(None, description="JavaScript to execute before screenshot")
    quality: Optional[int] = Field(None, description="JPEG quality (1-100)")
    wait: Optional[int] = Field(None, description="Wait time in milliseconds before screenshot")
    wait_for: Optional[str] = Field(None, description="JavaScript expression to wait for")
    timeout: Optional[int] = Field(30000, description="Timeout in milliseconds")
    # Note: scale_factor not used by ShotConfig, removed
    omit_background: Optional[bool] = Field(False, description="Omit background for transparency")
    skip_cloudflare_check: Optional[bool] = Field(False, description="Skip Cloudflare challenge detection")
    skip_wait_for_load: Optional[bool] = Field(False, description="Skip waiting for page load")
    trigger_lazy_load: Optional[bool] = Field(False, description="Trigger lazy loading of images")
    user_agent: Optional[str] = Field(None, description="Custom User-Agent header")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "width": 1280,
                "height": 720,
                "wait": 2000,
                "trigger_lazy_load": True
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

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "selector": "#main-content",
                "wait": 1000
            }
        }


async def get_browser(browser_args=None):
    """Get or create a shared browser instance"""
    global browser_instance
    if browser_instance is None:
        Config.verbose = os.getenv("VERBOSE", "").lower() in ("true", "1", "yes")
        Config.silent = not Config.verbose

        # Debug logging
        if browser_args:
            logger.info(f"Creating browser with args: {browser_args}")

        browser_instance = await create_browser_context(
            browser="chromium",
            browser_args=browser_args or [],
            timeout=60000,
        )
        logger.info("Browser instance created successfully")
    return browser_instance


@app.middleware("http")
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


@app.get("/", tags=["utility"], summary="API Information")
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


@app.get("/health", tags=["utility"], summary="Health Check")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/shot", tags=["screenshots"], summary="Capture Screenshot")
async def shot(request: ShotRequest):
    """Take a screenshot and return the image"""
    try:
        # Get browser instance
        browser = await get_browser()

        # Build shot configuration
        shot_config = ShotConfig({
            "url": request.url,
            "width": request.width,
            "height": request.height,
            "selectors": request.selectors,
            "selectors_all": request.selectors_all,
            "js_selectors": request.js_selectors,
            "js_selectors_all": request.js_selectors_all,
            "padding": request.padding,
            "javascript": request.javascript,
            "quality": request.quality,
            "wait": request.wait,
            "wait_for": request.wait_for,
            "timeout": request.timeout // 1000 if request.timeout else 30,  # Convert to seconds
            "omit_background": request.omit_background,
            "skip_cloudflare_check": request.skip_cloudflare_check,
            "skip_wait_for_load": request.skip_wait_for_load,
            "trigger_lazy_load": request.trigger_lazy_load,
            "silent": True
        })

        # Take the screenshot
        screenshot_bytes = await take_shot(
            browser,
            shot_config,
            return_bytes=True,
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


@app.post("/html", tags=["content"], summary="Extract HTML Content")
async def html(request: HtmlRequest):
    """Extract HTML content from a page"""
    try:
        # Get browser instance
        browser = await get_browser()

        # Use navigate_to_page for consistent page setup including Cloudflare detection
        shot_config = ShotConfig({
            "url": request.url,
            "timeout": request.timeout // 1000,  # Convert to seconds
            "wait": request.wait,
            "javascript": request.javascript,
            "silent": True
        })
        
        page, response_handler = await navigate_to_page(
            browser,
            shot_config,
        )

        # Extract HTML
        if request.selector:
            element = await page.select(request.selector)
            if element:
                html_content = await element.get_html()
            else:
                raise HTTPException(status_code=404, detail=f"Selector '{request.selector}' not found")
        else:
            html_content = await page.get_content()

        return {
            "url": request.url,
            "html": html_content,
            "selector": request.selector,
            "timestamp": datetime.now().timestamp()
        }

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

    # Store browser args in app state for lifespan to access
    app.state.browser_args = list(browser_args)

    click.echo(f"Starting Shot Power Scraper API Server on {host}:{port}")
    click.echo(f"API documentation available at http://{host}:{port}/docs")

    if browser_args:
        click.echo(f"Browser args: {list(browser_args)}")

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    main()
