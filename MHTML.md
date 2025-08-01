# MHTML Archive Web Server

A simple web server for viewing MHTML archive files through HTTP, preserving the original browsing experience as faithfully as possible.

## About MHTML

MHTML (MIME HTML) is a web archive format that packages a complete web page—including HTML, CSS, JavaScript, images, and other resources—into a single file using MIME multipart encoding. Originally developed by Microsoft and standardized in RFC 2557, MHTML archives capture web pages at a specific point in time, making them useful for preservation, offline viewing, and documentation.

## Motivation

Web pages are ephemeral by nature—they change, disappear, or break over time. MHTML archives preserve the complete state of a web page, but viewing them presents challenges:

- **Native browser support is limited**: Some browsers can open MHTML files directly, but with restrictions
- **Resource isolation**: Archived resources often can't reference each other properly
- **External dependencies**: Pages may still attempt to load external resources that no longer exist
- **JavaScript limitations**: Dynamic content may not work due to security restrictions

Our goal is to serve MHTML archives through a local web server, recreating the original browsing experience as accurately as possible while maintaining complete isolation from external resources.

## Creating MHTML Archives

MHTML files can be created using the `shot-power-scraper` tool:

```bash
# Create an MHTML archive of a web page
shot-power-scraper mhtml 'https://example.com' -o example.mhtml

# Include additional options for better capture
shot-power-scraper mhtml 'https://example.com' -o example.mhtml \
    --wait 3000 \
    --trigger-lazy-load \
    --ad-block

# Batch creation from YAML configuration
shot-power-scraper multi config.yaml
```

The `mhtml` command captures the complete page state including all loaded resources, CSS, JavaScript, images, and fonts into a single portable file. Options like `--trigger-lazy-load` help ensure more complete captures by scrolling to load lazy-loaded content.

## How It Works

This implementation parses MHTML files and serves their contents through HTTP endpoints:

1. **MHTML Parsing**: Uses boundary-based parsing to extract all resources from the archive
2. **URL Rewriting**: Comprehensively rewrites URLs in HTML, CSS, and JavaScript to point to local server paths
3. **Service Worker**: Blocks external requests and provides intelligent URL mapping for missing resources
4. **Content Security Policy**: Browser-level blocking of external resource loading
5. **Resource Serving**: Serves individual resources (images, CSS, JS, fonts) with proper content types

### Architecture

- **Server**: FastAPI-based HTTP server with dynamic route generation
- **Parser**: Boundary-based MHTML parsing inspired by existing tools like MHTMLExtractor
- **URL Rewriting**: Multi-stage rewriting for different content types (HTML, CSS, JS, JSON)
- **Browser Integration**: Service worker + CSP for comprehensive external resource blocking

## Features

**What We Do Well:**
- Comprehensive URL rewriting across all content types
- Intelligent handling of relative vs absolute URLs in CSS
- Srcset processing for responsive images
- Service worker-based request interception with fuzzy URL matching
- Automatic removal of preloading attributes that would bypass blocking
- Support for multiple archives with navigable index
- Preservation of inline styles and scripts

**Current Limitations:**
- **Archive completeness**: Can only serve what was actually saved in the MHTML
- **Browser differences**: Archives saved in one browser may reference resources not available when viewed in another
- **Dynamic content**: JavaScript that depends on timing, external APIs, or browser-specific features may not work
- **Modern web features**: Service workers, WebAssembly, and other advanced features in the original page are not preserved
- **Font loading**: Complex font fallback chains may not work if all variants aren't archived

## Known Issues

The biggest limitation is the **archive boundary problem**: MHTML files only contain the resources that were actually loaded and saved during the original capture. This creates several scenarios where faithful reproduction is impossible:

- **Responsive images**: A page may reference multiple image sizes in `srcset`, but only one was loaded and saved
- **Browser-specific resources**: Different browsers may request different file formats (WebP vs PNG, WOFF2 vs WOFF fonts)
- **Conditional loading**: Resources loaded based on screen size, user interaction, or JavaScript may be missing
- **Lazy loading**: Content that wasn't visible during the save may not be in the archive

While we attempt to handle these cases gracefully (fuzzy URL matching, srcset simplification), the fundamental limitation is that we can't serve what wasn't captured.

## Acknowledgments

This implementation builds on established MHTML parsing techniques and draws inspiration from:
- RFC 2557 (MHTML specification)
- Various open-source MHTML parsing libraries
- Modern web server patterns and service worker techniques

The approach prioritizes practical functionality over theoretical completeness, accepting that perfect reproduction of archived web pages is inherently limited by what was originally captured.