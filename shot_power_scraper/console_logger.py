"""Console logging functionality for shot-scraper using nodriver CDP"""
import click
import nodriver as uc
from typing import List, Dict, Any


class ConsoleLogger:
    """Captures and logs console messages from the browser using CDP"""
    
    def __init__(self, silent: bool = False):
        self.silent = silent
        self.logs: List[Dict[str, Any]] = []
        
    async def setup(self, page):
        """Setup console logging for the given page"""
        # Enable the Runtime domain to receive console events
        await page.send(uc.cdp.runtime.enable())
        
        # Add handler for console API calls
        page.add_handler(uc.cdp.runtime.ConsoleAPICalled, self._handle_console_message)
        
    def _handle_console_message(self, event):
        """Handle console messages from the browser"""
        # Handle both event object and dict formats
        if isinstance(event, dict):
            log_type = event.get('type', 'log')
            args = event.get('args', [])
            timestamp = event.get('timestamp')
        else:
            log_type = getattr(event, 'type', 'log')
            args = getattr(event, 'args', [])
            timestamp = getattr(event, 'timestamp', None)
        
        # Format the message from the arguments
        message_parts = []
        for arg in args:
            message_parts.append(self._format_remote_object(arg))
        
        message = " ".join(message_parts) if message_parts else "[empty message]"
        
        # Store the log
        self.logs.append({
            "type": log_type,
            "message": message,
            "timestamp": timestamp
        })
        
        # Output to stderr unless silent
        if not self.silent:
            formatted_message = self._format_console_output(log_type, message)
            click.echo(formatted_message, err=True)
    
    def _format_remote_object(self, obj) -> str:
        """Format a CDP RemoteObject into a readable string"""
        # Handle both object and dict formats
        if isinstance(obj, dict):
            obj_type = obj.get('type', 'unknown')
            obj_value = obj.get('value')
            obj_description = obj.get('description')
            obj_subtype = obj.get('subtype')
            obj_class_name = obj.get('className')
        else:
            obj_type = getattr(obj, 'type', 'unknown')
            obj_value = getattr(obj, 'value', None)
            obj_description = getattr(obj, 'description', None)
            obj_subtype = getattr(obj, 'subtype', None)
            obj_class_name = getattr(obj, 'class_name', None)
        
        if obj_type == "string":
            return str(obj_value) if obj_value is not None else ""
        elif obj_type == "number":
            return str(obj_value) if obj_value is not None else "0"
        elif obj_type == "boolean":
            return str(obj_value) if obj_value is not None else "false"
        elif obj_type == "undefined":
            return "undefined"
        elif obj_value is not None:
            return str(obj_value)
        elif obj_description:
            return obj_description
        elif obj_type == "object":
            if obj_subtype == "null":
                return "null"
            elif obj_subtype == "array":
                if obj_description and '(' in obj_description:
                    return f"[Array({obj_description.split('(')[1].split(')')[0]})]"
                return "[Array]"
            else:
                return f"[Object {obj_class_name or obj_type}]"
        else:
            return f"[{obj_type}]"
    
    def _format_console_output(self, log_type: str, message: str) -> str:
        """Format console output with appropriate prefix and styling"""
        prefix_map = {
            "log": "CONSOLE.LOG:",
            "info": "CONSOLE.INFO:",
            "warning": "CONSOLE.WARN:",
            "error": "CONSOLE.ERROR:",
            "debug": "CONSOLE.DEBUG:",
            "dir": "CONSOLE.DIR:",
            "trace": "CONSOLE.TRACE:"
        }
        
        prefix = prefix_map.get(log_type, f"CONSOLE.{log_type.upper()}:")
        
        # Add color coding for different message types
        if log_type == "error":
            return click.style(f"{prefix} {message}", fg="red")
        elif log_type == "warning":
            return click.style(f"{prefix} {message}", fg="yellow")
        elif log_type == "debug":
            return click.style(f"{prefix} {message}", fg="cyan")
        else:
            return f"{prefix} {message}"
    
    def get_logs(self) -> List[Dict[str, Any]]:
        """Get all captured logs"""
        return self.logs