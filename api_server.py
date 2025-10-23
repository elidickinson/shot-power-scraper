#!/usr/bin/env python3
"""
Screenshot API Server

A FastAPI server that provides REST endpoints for taking screenshots using shot-power-scraper.

Usage:
    python api_server.py [--browser-arg ARG ...] [--ad-block] [--paywall-block] [--trigger-lazy-load]

Example server startup:
    # Start server with custom browser arguments
    python api_server.py --browser-arg --window-size=1920,1080 --browser-arg --disable-dev-shm-usage

    # Start server with blocking features and lazy loading
    python api_server.py --ad-block --paywall-block --trigger-lazy-load

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

import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import click
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

# Add parent directory to path to import shot_power_scraper
sys.path.insert(0, str(Path(__file__).parent))

from shot_power_scraper.browser import create_browser_context, Config, setup_blocking_extensions
from shot_power_scraper.screenshot import take_shot
from shot_power_scraper.shot_config import ShotConfig
from shot_power_scraper.page_utils import create_tab_context, navigate_to_url
from shot_power_scraper.utils import filename_for_url

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
        # Read browser args from env (for multi-worker) or app.state (single worker)
        env_args = os.getenv("SHOT_API_BROWSER_ARGS")
        browser_args = env_args.split(",") if env_args else getattr(app.state, 'browser_args', [])
        await get_browser(browser_args=browser_args)

    yield

    # Shutdown
    if browser_instance:
        try:
            await browser_instance.stop()
        except Exception as e:
            logger.warning(f"Error stopping browser during shutdown: {e}")
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

class BaseRequest(BaseModel):
    """Base request model with shared validation"""
    url: str = Field(..., description="URL to process")

    @field_validator('url', mode='before')
    @classmethod
    def validate_url(cls, v):
        """Auto-add https:// if URL has no schema"""
        if not re.match(r'^https?://', v):
            v = f'https://{v}'
        return v


class ShotRequest(BaseRequest):
    """Request model for screenshot endpoint"""
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
    omit_background: Optional[bool] = Field(False, description="Omit background for transparency")
    skip_challenge_page_check: Optional[bool] = Field(False, description="Skip challenge page detection (Cloudflare, SiteGround, etc.)")
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


class HtmlRequest(BaseRequest):
    """Request model for HTML content extraction endpoint"""
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

        # Read configuration from environment variables (for multi-worker) or app.state (single worker)
        enable_gpu = os.getenv("SHOT_API_ENABLE_GPU") == "1" or getattr(app.state, 'enable_gpu', False)
        ad_block = os.getenv("SHOT_API_AD_BLOCK") == "1" or getattr(app.state, 'ad_block', False)
        paywall_block = os.getenv("SHOT_API_PAYWALL_BLOCK") == "1" or getattr(app.state, 'paywall_block', False)
        headful = os.getenv("SHOT_API_HEADFUL") == "1" or getattr(app.state, 'headful', False)
        reduced_motion = os.getenv("SHOT_API_REDUCED_MOTION") == "1" or getattr(app.state, 'reduced_motion', False)
        user_agent = os.getenv("SHOT_API_USER_AGENT") or getattr(app.state, 'user_agent', None)

        # Parse browser args from env if not provided
        if not browser_args:
            env_args = os.getenv("SHOT_API_BROWSER_ARGS")
            if env_args:
                browser_args = env_args.split(",")
            else:
                browser_args = getattr(app.state, 'browser_args', [])

        # Set global Config values
        Config.enable_gpu = enable_gpu

        # Get blocking options
        blocking_options = {
            'ad_block': ad_block,
            'paywall_block': paywall_block,
        }

        # Create a ShotConfig object with the browser settings
        config_dict = {
            "browser_args": browser_args or [],
            "headful": headful,
            "reduced_motion": reduced_motion,
            **blocking_options,
        }

        # Only set user_agent if provided
        if user_agent:
            config_dict["user_agent"] = user_agent

        shot_config = ShotConfig(config_dict)

        # Debug logging
        if browser_args:
            logger.info(f"Creating browser with args: {browser_args}")

        blocking_features = [
            name for name, enabled in [
                ('ad_block', blocking_options['ad_block']),
                ('paywall_block', blocking_options['paywall_block'])
            ]
            if enabled
        ]
        if blocking_features:
            logger.info(f"Creating browser with blocking: {' + '.join(blocking_features)}")

        # Setup blocking extensions if needed
        extensions = []
        if any(blocking_options.values()):
            await setup_blocking_extensions(extensions, blocking_options['ad_block'], blocking_options['paywall_block'])

        browser_instance = await create_browser_context(shot_config, extensions)
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


@app.get("/api", tags=["utility"], summary="API Information")
async def api_info():
    """API information and server settings"""
    # Read from env vars (for multi-worker) or app.state (single worker)
    ad_block = os.getenv("SHOT_API_AD_BLOCK") == "1" or getattr(app.state, 'ad_block', False)
    paywall_block = os.getenv("SHOT_API_PAYWALL_BLOCK") == "1" or getattr(app.state, 'paywall_block', False)
    user_agent = os.getenv("SHOT_API_USER_AGENT") or getattr(app.state, 'user_agent', None)
    enable_gpu = os.getenv("SHOT_API_ENABLE_GPU") == "1" or getattr(app.state, 'enable_gpu', False)
    reduced_motion = os.getenv("SHOT_API_REDUCED_MOTION") == "1" or getattr(app.state, 'reduced_motion', False)
    trigger_lazy_load = os.getenv("SHOT_API_TRIGGER_LAZY_LOAD") == "1" or getattr(app.state, 'trigger_lazy_load', False)

    blocking_features = []
    if ad_block:
        blocking_features.append("ad_block")
    if paywall_block:
        blocking_features.append("paywall_block")

    return {
        "message": "Shot Power Scraper API Server",
        "version": "1.0.0",
        "endpoints": {
            "/shot": "POST - Take a screenshot",
            "/html": "POST - Extract HTML content",
            "/api": "GET - API information"
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
        ],
        "server_settings": {
            "blocking_features": blocking_features,
            "user_agent": user_agent,
            "enable_gpu": enable_gpu,
            "reduced_motion": reduced_motion,
            "trigger_lazy_load": trigger_lazy_load
        }
    }


@app.get("/", response_class=HTMLResponse, tags=["utility"], summary="Web Client")
async def web_client():
    """Web client for taking screenshots"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shot Power Scraper</title>
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; color: #333; }
.container { max-width: 900px; margin: 0 auto; }
.header { background: white; padding: 20px 30px; border-radius: 12px 12px 0 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
.header h1 { font-size: 24px; color: #667eea; margin-bottom: 8px; }
.server-info { font-size: 14px; color: #666; }
.badge { display: inline-block; background: #10b981; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; margin-left: 8px; font-weight: 500; }
.form-container { background: white; padding: 24px; border-radius: 0 0 12px 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 8px; font-weight: 500; color: #444; font-size: 14px; }
.form-group input[type="text"], .form-group input[type="number"], .form-group select, .form-group textarea { width: 100%; padding: 12px 16px; border: 2px solid #e5e7eb; border-radius: 8px; font-size: 15px; transition: border-color 0.2s; }
.form-group input[type="text"]:focus, .form-group input[type="number"]:focus, .form-group select:focus, .form-group textarea:focus { outline: none; border-color: #667eea; }
.form-group textarea { resize: vertical; min-height: 80px; font-family: monospace; }
.form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
.checkbox-group { display: flex; align-items: center; gap: 8px; }
.checkbox-group input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }
.checkbox-group label { margin: 0; cursor: pointer; font-weight: normal; }
.advanced-toggle { background: #f9fafb; padding: 10px 16px; border-radius: 8px; cursor: pointer; user-select: none; margin-bottom: 12px; font-weight: 500; color: #667eea; border: 1px solid #e5e7eb; }
.advanced-toggle:hover { background: #f3f4f6; }
.advanced-options { display: none; background: #f9fafb; padding: 16px; border-radius: 8px; margin-top: 12px; margin-bottom: 16px; }
.advanced-options.visible { display: block; }
.btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 28px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
.btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(102, 126, 234, 0.5); }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #ffffff; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 8px; }
@keyframes spin { to { transform: rotate(360deg); } }
.result-container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); display: none; }
.result-container.visible { display: block; }
.result-actions { display: flex; gap: 12px; margin-bottom: 20px; }
.btn-secondary { background: white; color: #667eea; border: 2px solid #667eea; flex: 1; }
.btn-secondary:hover { background: #667eea; color: white; }
.screenshot-preview { border: 2px solid #e5e7eb; border-radius: 8px; overflow: auto; max-height: 600px; background: #f9fafb; }
.screenshot-preview img { display: block; max-width: 100%; height: auto; }
.error { background: #fee2e2; color: #991b1b; padding: 16px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #dc2626; }
.error-title { font-weight: 600; margin-bottom: 4px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📸 Shot Power Scraper</h1>
    <div class="server-info"><span id="server-badges"></span></div>
  </div>
  <div class="form-container">
    <form id="screenshot-form">
      <div class="form-group">
        <label for="url">URL</label>
        <input type="text" id="url" name="url" placeholder="example.com" autofocus required>
      </div>
      <div class="form-row">
        <div class="form-group"><label for="width">Width (px)</label><input type="number" id="width" name="width" placeholder="Full Page"></div>
        <div class="form-group"><label for="height">Height (px)</label><input type="number" id="height" name="height" placeholder="Full Page"></div>
        <div class="form-group"><label for="wait">Wait (ms)</label><input type="number" id="wait" name="wait" placeholder="0" min="0" step="100"></div>
      </div>
      <div class="checkbox-group">
        <input type="checkbox" id="trigger_lazy_load" name="trigger_lazy_load">
        <label for="trigger_lazy_load">Trigger Lazy Load</label>
      </div>
      <div class="advanced-toggle" onclick="toggleAdvanced()">⚙️ Advanced Options</div>
      <div id="advanced-options" class="advanced-options">
        <div class="form-group"><label for="selector">CSS Selector</label><input type="text" id="selector" name="selector" placeholder=".main-content"></div>
        <div class="form-group"><label for="javascript">JavaScript to Execute</label><textarea id="javascript" name="javascript" placeholder="document.querySelector('.ads').remove()"></textarea></div>
        <div class="form-row">
          <div class="form-group"><label for="padding">Selector Padding (px)</label><input type="number" id="padding" name="padding" placeholder="0" min="0"></div>
          <div class="form-group"><label for="quality">JPEG Quality (1-100)</label><input type="number" id="quality" name="quality" placeholder="PNG" min="1" max="100"></div>
          <div class="form-group"><label for="timeout">Timeout (ms)</label><input type="number" id="timeout" name="timeout" placeholder="30000" min="1000"></div>
        </div>
        <div class="checkbox-group">
          <input type="checkbox" id="omit_background" name="omit_background">
          <label for="omit_background">Transparent Background</label>
        </div>
      </div>
      <button type="submit" class="btn" id="submit-btn">📸 Capture Screenshot</button>
    </form>
  </div>
  <div id="result-container" class="result-container">
    <div class="result-actions">
      <button class="btn btn-secondary" onclick="downloadScreenshot()">⬇️ Download</button>
      <button class="btn btn-secondary" onclick="resetForm()">🔄 New Screenshot</button>
    </div>
    <div class="screenshot-preview"><img id="screenshot-img" alt="Screenshot"></div>
  </div>
</div>
<script>
let screenshotBlob = null;
let currentFilename = 'screenshot.png';

async function loadServerSettings() {
    try {
        const {server_settings} = await fetch('/api').then(r => r.json());
        if (server_settings?.blocking_features?.length) {
            const labels = {ad_block: 'Ad Block', paywall_block: 'Paywall Bypass'};
            server_settings.blocking_features.forEach(f => {
                const badge = document.createElement('span');
                badge.className = 'badge';
                badge.textContent = labels[f] || f;
                document.getElementById('server-badges').appendChild(badge);
            });
        }
    } catch (e) {}
}

function toggleAdvanced() {
    document.getElementById('advanced-options').classList.toggle('visible');
}

function showError(message) {
    document.querySelector('.error')?.remove();
    const err = document.createElement('div');
    err.className = 'error';
    err.innerHTML = `<div class="error-title">Error</div><div>${message}</div>`;
    document.querySelector('.form-container').prepend(err);
}

async function captureScreenshot(e) {
    e.preventDefault();
    const btn = document.getElementById('submit-btn');
    const data = new FormData(e.target);
    const body = {url: data.get('url')};

    ['width', 'height', 'wait', 'quality', 'padding', 'timeout'].forEach(f => {
        const v = data.get(f);
        if (v) body[f] = parseInt(v);
    });

    if (data.get('selector')) body.selectors = [data.get('selector')];
    if (data.get('javascript')) body.javascript = data.get('javascript');
    body.trigger_lazy_load = data.get('trigger_lazy_load') === 'on';
    body.omit_background = data.get('omit_background') === 'on';

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Capturing...';
    document.querySelector('.error')?.remove();

    try {
        const res = await fetch('/shot', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });

        if (!res.ok) throw new Error((await res.json()).detail || 'Screenshot failed');

        const cd = res.headers.get('Content-Disposition');
        if (cd) {
            const match = cd.match(/filename=(.+)/);
            if (match) currentFilename = match[1];
        }

        screenshotBlob = await res.blob();
        document.getElementById('screenshot-img').src = URL.createObjectURL(screenshotBlob);
        document.getElementById('result-container').classList.add('visible');
        document.getElementById('result-container').scrollIntoView({behavior: 'smooth'});
    } catch (error) {
        showError(error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '📸 Capture Screenshot';
    }
}

function downloadScreenshot() {
    if (!screenshotBlob) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(screenshotBlob);
    a.download = currentFilename;
    a.click();
    URL.revokeObjectURL(a.href);
}

function resetForm() {
    document.getElementById('screenshot-form').reset();
    document.getElementById('result-container').classList.remove('visible');
    document.getElementById('url').focus();
    screenshotBlob = null;
}

document.getElementById('screenshot-form').addEventListener('submit', captureScreenshot);
loadServerSettings();
</script>
</body>
</html>
    """


@app.post("/shot", tags=["screenshots"], summary="Capture Screenshot")
async def shot(request: ShotRequest):
    """Take a screenshot and return the image"""
    browser = await get_browser()

    # Use server-level trigger_lazy_load as default if request doesn't specify
    server_trigger_lazy_load = os.getenv("SHOT_API_TRIGGER_LAZY_LOAD") == "1" or getattr(app.state, 'trigger_lazy_load', False)
    trigger_lazy_load = request.trigger_lazy_load if request.trigger_lazy_load else server_trigger_lazy_load

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
        "skip_challenge_page_check": request.skip_challenge_page_check,
        "skip_wait_for_load": request.skip_wait_for_load,
        "trigger_lazy_load": trigger_lazy_load,
        "silent": True
    })

    # Create a tab context using the browser object
    from shot_power_scraper.page_utils import create_tab_context, navigate_to_url
    page = await create_tab_context(browser, shot_config)

    try:
        await navigate_to_url(page, shot_config)

        # Take the screenshot using the page context
        screenshot_bytes = await take_shot(
            page,
            shot_config,
            return_bytes=True,
            skip_navigation=True,  # Already navigated above
        )

        # Determine content type based on quality setting
        if request.quality:
            content_type = "image/jpeg"
            ext = "jpg"
        else:
            content_type = "image/png"
            ext = "png"

        filename = filename_for_url(request.url, ext=ext)

        # Return the image
        return Response(
            content=screenshot_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await page.close()


@app.post("/html", tags=["content"], summary="Extract HTML Content")
async def html(request: HtmlRequest) -> HTMLResponse:
    """Extract HTML content from a page"""
    browser = await get_browser()

    shot_config = ShotConfig({
        "url": request.url,
        "timeout": request.timeout // 1000,  # Convert to seconds
        "wait": request.wait,
        "javascript": request.javascript,
        "silent": True
    })

    page = await create_tab_context(browser, shot_config)

    try:
        await navigate_to_url(page, shot_config)

        # Extract HTML
        if request.selector:
            element = await page.select(request.selector)
            if element:
                html_content = await element.get_html()
            else:
                raise HTTPException(status_code=404, detail=f"Selector '{request.selector}' not found")
        else:
            html_content = await page.get_content()

        return HTMLResponse(content=html_content, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await page.close()


@click.command()
@click.option("--headful", "--no-headless", is_flag=True, help="Run with visible browser (non-headless mode)")
@click.option("--reduced-motion", is_flag=True, help="Emulate 'prefers-reduced-motion' media feature")
@click.option("--user-agent", help="User-Agent header to use")
@click.option("--enable-gpu", is_flag=True, help="Enable GPU acceleration (GPU is disabled by default)")
@click.option("browser_args", "--browser-arg", multiple=True,
            help="Additional arguments to pass to the browser")
@click.option("--ad-block/--no-ad-block", default=False, help="Enable ad blocking using built-in filter lists")
@click.option("--paywall-block/--no-paywall-block", default=False, help="Enable paywall bypass using Bypass Paywalls Clean extension")
@click.option("--trigger-lazy-load", is_flag=True, help="Trigger lazy loading of images for all requests by default")
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
@click.option(
    "--workers",
    type=int,
    default=lambda: int(os.getenv("WORKERS", "1")),
    help="Number of worker processes (default: 1, can be overridden with WORKERS env var)"
)
def main(browser_args, host, port, reload, workers, user_agent, enable_gpu, headful, reduced_motion,
         ad_block, paywall_block, trigger_lazy_load):
    """Start the Shot Power Scraper API Server"""
    import uvicorn

    # Store browser args and blocking options in app state for lifespan to access
    app.state.browser_args = list(browser_args)
    app.state.user_agent = user_agent
    app.state.enable_gpu = enable_gpu
    app.state.headful = headful
    app.state.reduced_motion = reduced_motion
    app.state.ad_block = ad_block
    app.state.paywall_block = paywall_block
    app.state.trigger_lazy_load = trigger_lazy_load

    click.echo(f"Starting Shot Power Scraper API Server on {host}:{port}")
    click.echo(f"API documentation available at http://{host}:{port}/docs")

    # Show blocking options if enabled
    if ad_block or paywall_block:
        blocking_features = []
        if ad_block:
            blocking_features.append("ad blocking")
        if paywall_block:
            blocking_features.append("paywall bypass")
        click.echo(f"Blocking features enabled: {' + '.join(blocking_features)}")

    # Show trigger lazy load if enabled
    if trigger_lazy_load:
        click.echo("Lazy loading enabled by default for all requests")

    if browser_args:
        click.echo(f"Browser args: {list(browser_args)}")

    logger.info(f"Starting server on {host}:{port}")

    if workers > 1:
        click.echo(f"Running with {workers} worker processes")

    # Set environment variables for worker processes to read
    # This is necessary because workers > 1 causes each process to import the module fresh
    # TODO: Document SHOT_API_* environment variables as a first-class configuration method
    #       and consider making them the primary way to configure the server (more standard
    #       for containerized deployments, systemd services, etc.) rather than CLI flags.
    #       Should also validate/parse them more robustly and centralize the reading logic.
    if browser_args:
        os.environ.setdefault("SHOT_API_BROWSER_ARGS", ",".join(browser_args))
    if user_agent:
        os.environ.setdefault("SHOT_API_USER_AGENT", user_agent)
    os.environ.setdefault("SHOT_API_ENABLE_GPU", "1" if enable_gpu else "")
    os.environ.setdefault("SHOT_API_HEADFUL", "1" if headful else "")
    os.environ.setdefault("SHOT_API_REDUCED_MOTION", "1" if reduced_motion else "")
    os.environ.setdefault("SHOT_API_AD_BLOCK", "1" if ad_block else "")
    os.environ.setdefault("SHOT_API_PAYWALL_BLOCK", "1" if paywall_block else "")
    os.environ.setdefault("SHOT_API_TRIGGER_LAZY_LOAD", "1" if trigger_lazy_load else "")

    # Use import string when workers > 1 or reload is enabled
    if workers > 1 or reload:
        uvicorn.run(
            "api_server:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers
        )
    else:
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
            workers=workers
        )


if __name__ == "__main__":
    main()
