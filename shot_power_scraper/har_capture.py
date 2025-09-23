"""HAR (HTTP Archive) file generation using Chrome DevTools Protocol"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import nodriver as uc


class HARCollector:
    """Collects network events and generates HAR files using CDP"""
    
    def __init__(self, include_response_bodies: bool = True):
        self.include_response_bodies = include_response_bodies
        self.requests = {}  # requestId -> request data
        self.responses = {}  # requestId -> response data
        self.timings = {}  # requestId -> timing data
        self.response_bodies = {}  # requestId -> response body content
        self.pending_body_requests = set()  # requestIds that finished loading and need body fetching
        self.start_time = None
        self.page_ref = "page_0"
        self.page_title = ""
        self.page_url = ""
        self.page = None  # Store page reference for getResponseBody calls
        
    async def setup(self, page):
        """Set up CDP event handlers for network monitoring"""
        self.page = page  # Store page reference for response body fetching
        
        # Enable network domain with increased buffer sizes for response body capture
        if self.include_response_bodies:
            await page.send(uc.cdp.network.enable(max_total_buffer_size=10485760, max_resource_buffer_size=5242880))
        else:
            await page.send(uc.cdp.network.enable())
        
        # Set up event handlers
        page.add_handler(uc.cdp.network.RequestWillBeSent, self._on_request_will_be_sent)
        page.add_handler(uc.cdp.network.ResponseReceived, self._on_response_received)
        page.add_handler(uc.cdp.network.LoadingFinished, self._on_loading_finished)
        page.add_handler(uc.cdp.network.LoadingFailed, self._on_loading_failed)
    
    def start_recording(self):
        """Start recording network activity"""
        self.start_time = time.time()
        self.requests.clear()
        self.responses.clear()
        self.timings.clear()
        self.response_bodies.clear()
        self.pending_body_requests.clear()
    
    async def stop_recording(self, page) -> Dict[str, Any]:
        """Stop recording and generate HAR data"""
        # Fetch response bodies for all pending requests
        if self.include_response_bodies and self.pending_body_requests:
            for request_id in self.pending_body_requests:
                try:
                    response_body_result = await page.send(uc.cdp.network.get_response_body(request_id=request_id))
                    self.response_bodies[request_id] = {
                        'body': response_body_result.body,
                        'base64Encoded': response_body_result.base64_encoded
                    }
                except Exception as e:
                    # Some responses may not have bodies or may be cached/failed, which is normal
                    # Continue with other requests
                    pass
        
        # Get page info
        self.page_title = await page.evaluate("document.title")
        self.page_url = page.url
        
        return self.to_har_format()
    
    def _on_request_will_be_sent(self, event):
        """Handle Network.requestWillBeSent event"""
        request_id = event.request_id
        request = event.request
        
        # Store request data
        self.requests[request_id] = {
            'requestId': request_id,
            'url': request.url,
            'method': request.method,
            'headers': request.headers,
            'postData': getattr(request, 'post_data', None),
            'timestamp': event.timestamp,
            'wallTime': event.wall_time,
            'initiator': event.initiator,
            'redirectResponse': getattr(event, 'redirect_response', None),
            'resourceType': getattr(event, 'type', 'Other')  # Track resource type for XHR identification
        }
        
        # Initialize timing data
        self.timings[request_id] = {
            'requestTime': event.timestamp,
            'startTime': time.time()
        }
    
    def _on_response_received(self, event):
        """Handle Network.responseReceived event"""
        request_id = event.request_id
        response = event.response
        
        # Store response data
        self.responses[request_id] = {
            'requestId': request_id,
            'url': response.url,
            'status': response.status,
            'statusText': response.status_text,
            'headers': response.headers,
            'mimeType': response.mime_type,
            'timestamp': event.timestamp,
            'remoteIPAddress': getattr(response, 'remote_ip_address', ''),
            'fromDiskCache': getattr(response, 'from_disk_cache', False),
            'fromServiceWorker': getattr(response, 'from_service_worker', False),
            'encodedDataLength': getattr(response, 'encoded_data_length', 0),
            'timing': getattr(response, 'timing', None)
        }
    
    def _on_loading_finished(self, event):
        """Handle Network.loadingFinished event"""
        request_id = event.request_id
        
        if request_id in self.timings:
            self.timings[request_id]['loadingFinished'] = event.timestamp
            self.timings[request_id]['encodedDataLength'] = event.encoded_data_length
            
        # Mark for response body fetching if requested and we have a response
        if self.include_response_bodies and request_id in self.responses:
            self.pending_body_requests.add(request_id)
    
    def _on_loading_failed(self, event):
        """Handle Network.loadingFailed event"""
        request_id = event.request_id
        
        if request_id in self.timings:
            self.timings[request_id]['loadingFailed'] = event.timestamp
            self.timings[request_id]['errorText'] = event.error_text
    
    def to_har_format(self) -> Dict[str, Any]:
        """Convert collected network data to HAR format"""
        entries = []
        
        for request_id in self.requests:
            if request_id not in self.responses:
                continue  # Skip requests without responses
                
            request_data = self.requests[request_id]
            response_data = self.responses[request_id]
            timing_data = self.timings.get(request_id, {})
            
            # Calculate timing
            start_time = timing_data.get('requestTime', self.start_time)
            started_date_time = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat()
            
            # Calculate total time
            total_time = 0
            if 'loadingFinished' in timing_data:
                total_time = (timing_data['loadingFinished'] - timing_data['requestTime']) * 1000
            elif 'loadingFailed' in timing_data:
                total_time = (timing_data['loadingFailed'] - timing_data['requestTime']) * 1000
            
            # Build request object
            har_request = {
                'method': request_data['method'],
                'url': request_data['url'],
                'httpVersion': 'HTTP/1.1',  # Default, could be extracted from response
                'headers': self._format_headers(request_data['headers']),
                'queryString': self._extract_query_string(request_data['url']),
                'cookies': [],  # TODO: Extract cookies from headers
                'headersSize': -1,
                'bodySize': len(request_data.get('postData', '')) if request_data.get('postData') else 0
            }
            
            # Add POST data if present
            if request_data.get('postData'):
                har_request['postData'] = {
                    'mimeType': 'application/x-www-form-urlencoded',  # Default
                    'text': request_data['postData']
                }
            
            # Build response object with actual body content if available
            response_body_info = self.response_bodies.get(request_id, {})
            response_text = response_body_info.get('body', '')
            is_base64 = response_body_info.get('base64Encoded', False)
            
            har_response = {
                'status': response_data['status'],
                'statusText': response_data['statusText'],
                'httpVersion': 'HTTP/1.1',  # Default
                'headers': self._format_headers(response_data['headers']),
                'cookies': [],  # TODO: Extract cookies from headers
                'content': {
                    'size': response_data.get('encodedDataLength', 0),
                    'mimeType': response_data['mimeType'],
                    'text': response_text,
                    'encoding': 'base64' if is_base64 else None
                },
                'redirectURL': '',
                'headersSize': -1,
                'bodySize': response_data.get('encodedDataLength', 0)
            }
            
            # Build timing object
            har_timings = {
                'blocked': -1,
                'dns': -1, 
                'connect': -1,
                'send': -1,
                'wait': -1,
                'receive': -1,
                'ssl': -1
            }
            
            # Extract timing from CDP timing data if available
            if 'timing' in response_data and response_data['timing']:
                timing = response_data['timing']
                request_time = timing_data.get('requestTime', 0)
                
                # Convert CDP timings to HAR format (all in milliseconds)
                if hasattr(timing, 'dns_start') and timing.dns_start >= 0:
                    har_timings['dns'] = timing.dns_end - timing.dns_start if timing.dns_end >= 0 else -1
                if hasattr(timing, 'connect_start') and timing.connect_start >= 0:
                    har_timings['connect'] = timing.connect_end - timing.connect_start if timing.connect_end >= 0 else -1
                if hasattr(timing, 'send_start') and timing.send_start >= 0:
                    har_timings['send'] = timing.send_end - timing.send_start if timing.send_end >= 0 else -1
                if hasattr(timing, 'receive_headers_end') and timing.receive_headers_end >= 0:
                    har_timings['wait'] = timing.receive_headers_end - timing.send_end if timing.send_end >= 0 else -1
            
            # Build HAR entry
            entry = {
                'pageref': self.page_ref,
                'startedDateTime': started_date_time,
                'time': total_time,
                'request': har_request,
                'response': har_response,
                'cache': {},
                'timings': har_timings,
                'serverIPAddress': response_data.get('remoteIPAddress', ''),
                'connection': str(hash(request_id)),  # Unique connection identifier
                '_resourceType': request_data.get('resourceType', 'Other')  # Add resource type for debugging (non-standard HAR field)
            }
            
            entries.append(entry)
        
        # Build page info
        page_info = {
            'startedDateTime': datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat() if self.start_time else datetime.now(timezone.utc).isoformat(),
            'id': self.page_ref,
            'title': self.page_title,
            'pageTimings': {
                'onContentLoad': -1,
                'onLoad': -1
            }
        }
        
        # Build final HAR structure
        har_data = {
            'log': {
                'version': '1.2',
                'creator': {
                    'name': 'shot-power-scraper',
                    'version': '1.0'  # TODO: Get actual version
                },
                'browser': {
                    'name': 'Chrome',
                    'version': 'Unknown'  # TODO: Get actual browser version
                },
                'pages': [page_info],
                'entries': entries
            }
        }
        
        return har_data
    
    def _format_headers(self, headers_dict: Dict[str, str]) -> List[Dict[str, str]]:
        """Convert headers dict to HAR format array"""
        return [{'name': name, 'value': value} for name, value in headers_dict.items()]
    
    def _extract_query_string(self, url: str) -> List[Dict[str, str]]:
        """Extract query string parameters from URL"""
        from urllib.parse import urlparse, parse_qs
        
        parsed = urlparse(url)
        if not parsed.query:
            return []
        
        query_params = parse_qs(parsed.query)
        result = []
        for name, values in query_params.items():
            for value in values:
                result.append({'name': name, 'value': value})
        
        return result


async def capture_har(page, include_response_bodies: bool = True) -> Dict[str, Any]:
    """
    Capture HAR data for a page that has already been navigated to.
    
    Args:
        page: nodriver page object
        include_response_bodies: Whether to include response body content
        
    Returns:
        Dict containing HAR data in standard format
    """
    collector = HARCollector(include_response_bodies=include_response_bodies)
    await collector.setup(page)
    collector.start_recording()
    
    # Allow some time for any remaining network activity to complete
    import asyncio
    await asyncio.sleep(1)
    
    return await collector.stop_recording(page)