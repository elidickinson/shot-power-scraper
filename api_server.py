#!/usr/bin/env python3
"""
Screenshot API Server

A FastAPI server that provides REST endpoints for taking screenshots using shot-scraper.

Usage:
    python api_server.py

Example API calls:
    # Simple screenshot
    curl -X POST http://localhost:8000/shot \
        -H "Content-Type: application/json" \
        -d '{"url": "https://example.com"}' \
        -o screenshot.png

    # Screenshot with options
    curl -X POST http://localhost:8000/shot \
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
    curl -X POST http://localhost:8000/shot \
        -H "Content-Type: application/json" \
        -d '{
            "url": "https://example.com",
            "selector": "#main-content",
            "padding": 20
        }' \
        -o screenshot.png
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import asyncio
import io
import os
import sys
from pathlib import Path

# Add parent directory to path to import shot_scraper
sys.path.insert(0, str(Path(__file__).parent))

from shot_scraper.browser import create_browser_context, Config
from shot_scraper.screenshot import take_shot
from shot_scraper.utils import url_or_file_path

app = FastAPI(title="Shot Scraper API", version="1.0.0")

# Global browser instance for reuse
browser_instance = None
browser_lock = asyncio.Lock()

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


async def get_browser():
    """Get or create a shared browser instance"""
    global browser_instance
    async with browser_lock:
        if browser_instance is None:
            Config.verbose = os.getenv("VERBOSE", "").lower() in ("true", "1", "yes")
            Config.silent = not Config.verbose
            browser_instance = await create_browser_context(
                browser="chromium",
                browser_args=[],
                timeout=60000,
            )
        return browser_instance


@app.on_event("startup")
async def startup_event():
    """Initialize browser on startup for faster first request"""
    if os.getenv("PRELOAD_BROWSER", "true").lower() in ("true", "1", "yes"):
        await get_browser()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up browser on shutdown"""
    global browser_instance
    if browser_instance:
        try:
            await browser_instance.stop()
        except:
            pass
        browser_instance = None


@app.get("/")
async def root():
    """API documentation"""
    return {
        "message": "Shot Scraper API Server",
        "endpoints": {
            "/shot": "POST - Take a screenshot",
            "/health": "GET - Health check"
        },
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/shot")
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


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")
    
    print(f"Starting Shot Scraper API Server on {host}:{port}")
    print(f"API documentation available at http://{host}:{port}/docs")
    print("\nEnvironment variables:")
    print(f"  HOST={host}")
    print(f"  PORT={port}")
    print(f"  RELOAD={reload}")
    print(f"  VERBOSE={os.getenv('VERBOSE', 'false')}")
    print(f"  PRELOAD_BROWSER={os.getenv('PRELOAD_BROWSER', 'true')}")
    
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload
    )