#!/usr/bin/env python3
"""
Simple tools API server using portable configuration
Serves JSON data with basic CORS support using only standard library
"""
import csv
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from pathlib import Path

# Dynamically detect the project root (parent of scripts directory)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_config


class ToolsAPIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.config = get_config()
        super().__init__(*args, **kwargs)

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/api/health':
            self.send_json_response({"ok": True, "root": str(self.config.root)})
        elif parsed_path.path == '/api/tools':
            self.handle_list_tools()
        elif parsed_path.path == '/api/config':
            self.handle_config_info()
        else:
            self.send_error(404, "Not Found")

    def do_PATCH(self):
        """Handle PATCH requests for updating tools"""
        parsed_path = urlparse(self.path)

        if parsed_path.path.startswith('/api/tools/'):
            tool_name = parsed_path.path.split('/')[-1]
            self.handle_update_tool(tool_name)
        else:
            self.send_error(404, "Not Found")

    def handle_config_info(self):
        """Return configuration information"""
        info = self.config.get_info()
        self.send_json_response(info)

    def handle_list_tools(self):
        """Return list of all tools"""
        try:
            if self.config.json_file.exists():
                with open(self.config.json_file, 'r', encoding='utf-8') as f:
                    tools = json.load(f)
                self.send_json_response(tools)
            else:
                self.send_json_response({
                    "error": "No tools data found",
                    "message": "Run 'python3 scripts/gen_tools_data.py' first",
                    "json_file": str(self.config.json_file)
                })
        except Exception as e:
            self.send_error(500, f"Error reading tools data: {e}")

    def handle_update_tool(self, tool_name):
        """Update a specific tool"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length).decode('utf-8')
                updates = json.loads(body)
            else:
                updates = {}

            # Load current tools
            if self.config.json_file.exists():
                with open(self.config.json_file, 'r', encoding='utf-8') as f:
                    tools = json.load(f)
            else:
                tools = []

            # Find and update the tool
            tool_found = False
            for tool in tools:
                if tool['name'] == tool_name:
                    tool_found = True
                    if 'description' in updates:
                        tool['description'] = updates['description']
                    if 'example' in updates:
                        tool['example'] = updates['example']
                    break

            if not tool_found:
                self.send_error(404, "Tool not found")
                return

            # Save updated tools
            with open(self.config.json_file, 'w', encoding='utf-8') as f:
                json.dump(tools, f, indent=2)

            # Update CSV as well
            self.update_csv(tools)

            # Return updated tool
            updated_tool = next(tool for tool in tools if tool['name'] == tool_name)
            self.send_json_response(updated_tool)

        except Exception as e:
            self.send_error(500, f"Error updating tool: {e}")

    def update_csv(self, tools):
        """Update the CSV file with current tools data"""
        try:
            with open(self.config.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['name', 'description', 'example', 'type', 'mas_id'])
                for tool in tools:
                    writer.writerow([
                        tool.get('name', ''),
                        tool.get('description', ''),
                        tool.get('example', ''),
                        tool.get('type', ''),
                        tool.get('mas_id', '')
                    ])
        except Exception as e:
            print(f"Warning: Failed to update CSV: {e}")

    def send_json_response(self, data):
        """Send JSON response with CORS headers"""
        json_data = json.dumps(data).encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(json_data)))
        self.end_headers()
        self.wfile.write(json_data)

    def log_message(self, format, *args):
        """Override to provide cleaner logging"""
        message = format % args
        print(f"{self.address_string()} - {message}")


def main():
    """Run the API server"""
    config = get_config()
    server = None

    try:
        port = 5050
        server = HTTPServer(('127.0.0.1', port), ToolsAPIHandler)

        print("Brewfile Analyzer API Server")
        print(f"Root: {config.root}")
        print(f"Starting server on http://127.0.0.1:{port}")
        print("Endpoints:")
        print("  GET /api/health - Health check")
        print("  GET /api/config - Configuration info")
        print("  GET /api/tools - List all tools")
        print("  PATCH /api/tools/<name> - Update a tool")
        print("\nPress Ctrl+C to stop")

        server.serve_forever()

    except KeyboardInterrupt:
        print("\nShutting down server...")
        if server:
            server.server_close()
    except Exception as e:
        print(f"Error starting server: {e}")
        if server:
            server.server_close()
        sys.exit(1)


if __name__ == "__main__":
    main()
