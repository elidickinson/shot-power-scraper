# Shot Scraper API Server

A FastAPI-based REST API server for the shot-power-scraper screenshot tool. This server provides HTTP endpoints for taking screenshots of web pages with various options.

## Features

- Simple REST API for taking screenshots
- Shared browser instance for better performance
- Support for all shot-power-scraper features:
  - Custom viewport sizes
  - Element selectors (CSS and JavaScript)
  - Full page screenshots
  - JavaScript execution
  - Wait conditions
  - JPEG quality settings
  - Cloudflare bypass
  - And more...

## Installation

```bash
# Install dependencies
pip install -r requirements-api.txt

# Or with uv
uv pip install -r requirements-api.txt
```

## Usage

### Starting the Server

```bash
# Basic usage
python api_server.py

# With environment variables
HOST=0.0.0.0 PORT=8080 VERBOSE=true python api_server.py

# With uvicorn directly
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

### Environment Variables

- `HOST`: Server host (default: `127.0.0.1`)
- `PORT`: Server port (default: `8000`)
- `RELOAD`: Enable auto-reload for development (default: `false`)
- `VERBOSE`: Enable verbose logging (default: `false`)
- `PRELOAD_BROWSER`: Pre-initialize browser on startup (default: `true`)

### API Endpoints

#### `GET /` - API Information
Returns basic API information and available endpoints.

#### `GET /health` - Health Check
Check if the server is running and healthy.

#### `POST /shot` - Take Screenshot
Take a screenshot with various options.

**Request Body:**
```json
{
  "url": "https://example.com",
  "width": 1280,
  "height": 720,
  "wait": 2000,
  "selector": "#main-content",
  "padding": 20,
  "quality": 80,
  "javascript": "document.body.style.backgroundColor = 'red';"
}
```

**Response:** Binary image data (PNG or JPEG)

### API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Examples

### Using curl

```bash
# Simple screenshot
curl -X POST http://localhost:8000/shot \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' \
  -o screenshot.png

# Full page screenshot with custom size
curl -X POST http://localhost:8000/shot \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "width": 1920,
    "height": 1080,
  }' \
  -o fullpage.png

# Screenshot of specific element
curl -X POST http://localhost:8000/shot \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "selector": "#header",
    "padding": 20
  }' \
  -o header.png
```

### Using Python

```python
import requests

# Take a screenshot
response = requests.post(
    "http://localhost:8000/shot",
    json={
        "url": "https://example.com",
        "width": 1280,
        "height": 720,
        "wait": 2000
    }
)

# Save the image
with open("screenshot.png", "wb") as f:
    f.write(response.content)
```

### Using the Example Client

```bash
# Run all examples
python api_client_example.py
```

## Performance Tips

1. **Browser Reuse**: The server maintains a shared browser instance for better performance. The first request may be slower as the browser initializes.

2. **Preload Browser**: Set `PRELOAD_BROWSER=true` to initialize the browser on server startup.

3. **Concurrent Requests**: The server uses async handlers but screenshots are processed sequentially to avoid browser conflicts.

4. **Memory Usage**: Long-running servers may accumulate memory. Restart periodically if needed.

## Deployment Notes

**Important**: This API server requires a full Chrome/Chromium browser installation on the host system. Docker deployment is not recommended due to the complexity of running headless Chrome in containers with all required dependencies.

### System Requirements

1. **Chrome/Chromium Browser**: The nodriver library will automatically download and manage Chrome if not present, but having Chrome pre-installed is recommended.

2. **System Dependencies**: On Linux, ensure these packages are installed:
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y \
       libglib2.0-0 \
       libnss3 \
       libnspr4 \
       libatk1.0-0 \
       libatk-bridge2.0-0 \
       libcups2 \
       libdrm2 \
       libxcomposite1 \
       libxdamage1 \
       libxfixes3 \
       libxrandr2 \
       libgbm1 \
       libxkbcommon0 \
       libpango-1.0-0 \
       libcairo2 \
       libasound2
   ```

### Production Deployment

For production use, deploy directly on a Linux server with systemd:

```bash
# 1. Install Chrome (if not already installed)
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'
sudo apt-get update
sudo apt-get install google-chrome-stable

# 2. Set up the application
sudo mkdir -p /opt/shot-power-scraper
sudo cp -r . /opt/shot-power-scraper/
cd /opt/shot-power-scraper

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-api.txt

# 4. Install systemd service
sudo cp shot-power-scraper-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shot-power-scraper-api
sudo systemctl start shot-power-scraper-api
```

## Error Handling

The API returns appropriate HTTP status codes:
- `200 OK`: Screenshot taken successfully
- `422 Unprocessable Entity`: Invalid request parameters
- `500 Internal Server Error`: Screenshot failed

Error responses include a detail message:
```json
{
  "detail": "Error message here"
}
```

## Security Considerations

1. **URL Validation**: The server accepts any URL. Consider adding validation or allowlists in production.

2. **Resource Limits**: Long-running pages or infinite scrolls can consume resources. Set appropriate timeouts.

3. **Authentication**: No authentication is included. Add authentication middleware for production use.

4. **Rate Limiting**: Consider adding rate limiting to prevent abuse.

## Troubleshooting

1. **"Cannot connect to API server"**: Ensure the server is running and the correct host/port are used.

2. **"Browser initialization failed"**: Check that Chrome/Chromium is installed and accessible.

3. **Cloudflare challenges**: The server includes Cloudflare bypass detection. Some sites may still block automated access.

4. **Memory issues**: Restart the server periodically or implement browser recycling for long-running instances.