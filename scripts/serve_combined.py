#!/usr/bin/env python3
"""
Combined Static + API Server for Brewfile Analyzer
Serves both static files and API endpoints in a single server
Handles editing functionality with proper data persistence
"""
import json
import posixpath
import sys
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import Dict, Any, List, Optional
import argparse

import time

# Dynamic path setup
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from config import get_config  # noqa: E402

# Optional DuckDB backend
try:
    from scripts import db as dbmod
except Exception:
    dbmod = None


class CombinedHandler(SimpleHTTPRequestHandler):
    """Combined handler for static files and API endpoints"""

    def __init__(self, *args, **kwargs):
        self.config = get_config()
        self.db_con = None
        if dbmod is not None:
            try:
                self.db_con = dbmod.ensure_db(self.config)
            except Exception:
                self.db_con = None
        # Prefer serving from the output root (where docs/tools live) if index exists; fallback to project root
        static_base = self.config.output_root
        try:
            if not (self.config.output_dir / 'index.html').exists():
                static_base = self.config.root
        except Exception:
            static_base = self.config.root
        super().__init__(*args, directory=str(static_base), **kwargs)

    def end_headers(self):
        """Add CORS headers to all responses"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Handle GET requests - API or static files"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # API endpoints
        if path.startswith('/api/'):
            self.handle_api_get(path, parsed_path.query)
        elif path in ('', '/'):
            # Redirect root to tools interface
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/docs/tools/index.html")
            self.end_headers()
        else:
            # Static files - use parent implementation with security
            self.handle_static_file()

    def do_PATCH(self):
        """Handle PATCH requests for API"""
        parsed_path = urlparse(self.path)
        if parsed_path.path.startswith('/api/'):
            self.handle_api_patch(parsed_path.path)
        else:
            self.send_error(405, "Method Not Allowed")

    def do_POST(self):
        """Handle POST requests for API"""
        parsed_path = urlparse(self.path)
        if parsed_path.path.startswith('/api/'):
            self.handle_api_post(parsed_path.path)
        else:
            self.send_error(405, "Method Not Allowed")

    def handle_api_get(self, path: str, query: str):
        """Handle API GET requests"""
        try:
            if path == '/api/health':
                info = {
                    "ok": True,
                    "server": "Brewfile Analyzer Combined Server",
                    "root": str(self.config.root),
                    "db_mode": bool(getattr(self, 'db_con', None)),
                }
                if dbmod is not None and getattr(self, 'db_con', None):
                    try:
                        info["db_path"] = str(dbmod.get_db_path(self.config))
                    except Exception:
                        info["db_path"] = ""
                self.send_json_response(info)

            elif path == '/api/config':
                info = self.config.get_info()
                self.send_json_response(info)

            elif path == '/api/tools':
                self.handle_list_tools()

            elif path == '/api/tools/search':
                self.handle_search(query)
            elif path == '/api/tools/recent':
                self.handle_recent(query)
            elif path == '/api/tools/types':
                self.handle_types()
            elif path.startswith('/api/tools/'):
                tool_name = path.split('/')[-1]
                self.handle_get_tool(tool_name)
            elif path.startswith('/api/query'):
                self.handle_query(path, query)

            else:
                self.send_error(404, "API endpoint not found")

        except Exception as e:
            self.log_error(f"API GET error: {e}")
            self.send_error(500, f"Internal server error: {e}")

    def handle_api_patch(self, path: str):
        """Handle API PATCH requests for updating tools"""
        try:
            if path.startswith('/api/tools/'):
                # Extract tool name (URL decode it)
                tool_name = unquote(path.split('/')[-1])
                self.handle_update_tool(tool_name)
            else:
                self.send_error(404, "API endpoint not found")

        except Exception as e:
            self.log_error(f"API PATCH error: {e}")
            self.send_error(500, f"Internal server error: {e}")

    def handle_api_post(self, path: str):
        """Handle API POST requests"""
        try:
            if path == '/api/tools/batch-update':
                self.handle_batch_update()
            elif path == '/api/regenerate':
                self.handle_regenerate_data()
            else:
                self.send_error(404, "API endpoint not found")

        except Exception as e:
            self.log_error(f"API POST error: {e}")
            self.send_error(500, f"Internal server error: {e}")

    def handle_static_file(self):
        """Handle static file requests with security"""
        # Use the parent's translate_path but add our security
        path = self.translate_path_secure(self.path)

        if path is None:
            self.send_error(403, "Forbidden")
            return

        # Check if it's a directory and handle accordingly
        path_obj = Path(path)
        if path_obj.is_dir():
            # Look for index.html in directory
            index_path = path_obj / "index.html"
            if index_path.exists():
                self.path = str(index_path.relative_to(self.config.root))
                super().do_GET()
            else:
                self.send_error(403, "Directory listing disabled")
        else:
            # Serve the file normally
            super().do_GET()

    def translate_path_secure(self, path: str) -> Optional[str]:
        """Secure path translation to prevent directory traversal"""
        # Parse and normalize the path
        path = urlparse(path).path
        path = posixpath.normpath(unquote(path))

        # Remove leading slash and split into parts
        parts = [p for p in path.split('/') if p and p not in ('.', '..')]

        # Build path under project root
        resolved = self.config.root
        for part in parts:
            resolved = resolved / part

        # Resolve and check it's within project root
        try:
            real_path = resolved.resolve()
            real_root = self.config.root.resolve()

            # Check if the resolved path is within the project root
            try:
                real_path.relative_to(real_root)
                return str(real_path)
            except ValueError:
                return None  # Path escapes project root

        except Exception:
            return None

    def handle_list_tools(self):
        """Return list of all tools from JSON file"""
        try:
            # Prefer DB if available
            if self.db_con is not None:
                tools = dbmod.list_tools(self.db_con)
                self.send_json_response(tools)
                return

            if not self.config.json_file.exists():
                self.send_json_response({
                    "error": "No tools data found",
                    "message": "Run data generation first",
                    "suggestion": "python3 scripts/gen_tools_data.py"
                })
                return

            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)

            self.send_json_response(tools)

        except Exception as e:
            self.log_error(f"Error reading tools data: {e}")
            self.send_error(500, f"Error reading tools data: {e}")

    def handle_get_tool(self, tool_name: str):
        """Get a specific tool by name"""
        try:
            # Prefer DB if available
            if self.db_con is not None:
                tool = dbmod.fetch_tool(self.db_con, tool_name)
                if tool:
                    # Align keys to JSON snapshot shape
                    payload = {
                        'name': tool.get('name'),
                        'description': tool.get('description', ''),
                        'example': tool.get('example', ''),
                        'type': tool.get('type', ''),
                        'mas_id': tool.get('mas_id', ''),
                        'user_edited': tool.get('user_edited', False),
                        'last_edited': str(tool.get('last_edited') or '')
                    }
                    self.send_json_response(payload)
                    return
                self.send_error(404, "Tool not found")
                return

            if not self.config.json_file.exists():
                self.send_error(404, "Tools data not found")
                return

            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)

            tool = next((t for t in tools if t['name'] == tool_name), None)
            if tool:
                self.send_json_response(tool)
            else:
                self.send_error(404, "Tool not found")

        except Exception as e:
            self.log_error(f"Error getting tool {tool_name}: {e}")
            self.send_error(500, f"Error getting tool: {e}")

    def handle_update_tool(self, tool_name: str):
        """Update a specific tool's description and example"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No data provided")
                return

            body = self.rfile.read(content_length).decode('utf-8')
            try:
                updates = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON data")
                return

            # Validate updates
            valid_fields = {'description', 'example'}
            invalid_fields = set(updates.keys()) - valid_fields
            if invalid_fields:
                self.send_error(400, f"Invalid fields: {invalid_fields}")
                return

            # Prefer DB if available
            if self.db_con is not None:
                try:
                    updated = dbmod.update_tool_fields(self.db_con, tool_name, updates)
                except KeyError:
                    self.send_error(404, f"Tool '{tool_name}' not found")
                    return

                self.log_message(f"Updated tool (DB): {tool_name}")
                self.send_json_response({
                    "success": True,
                    "tool": {
                        'name': updated.get('name'),
                        'description': updated.get('description', ''),
                        'example': updated.get('example', ''),
                        'type': updated.get('type', ''),
                        'mas_id': updated.get('mas_id', ''),
                        'user_edited': True,
                        'last_edited': str(updated.get('last_edited') or '')
                    },
                    "message": f"Tool '{tool_name}' updated successfully"
                })
                return

            # Fallback: file-based update
            if not self.config.json_file.exists():
                self.send_error(404, "Tools data not found")
                return

            # Create backup before modification
            self.create_backup()

            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)

            # Find and update the tool
            tool_found = False
            updated_tool = None
            for tool in tools:
                if tool['name'] == tool_name:
                    tool_found = True

                    # Update fields
                    if 'description' in updates:
                        tool['description'] = updates['description']
                    if 'example' in updates:
                        tool['example'] = updates['example']

                    # Add metadata
                    tool['last_edited'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    tool['user_edited'] = True

                    updated_tool = tool
                    break

            if not tool_found:
                self.send_error(404, f"Tool '{tool_name}' not found")
                return

            # Save updated tools
            with open(self.config.json_file, 'w', encoding='utf-8') as f:
                json.dump(tools, f, indent=2, ensure_ascii=False)

            # CSV disabled (DuckDB-only mode)

            # Log the update
            self.log_message(f"Updated tool: {tool_name}")

            # Return the updated tool
            self.send_json_response({
                "success": True,
                "tool": updated_tool,
                "message": f"Tool '{tool_name}' updated successfully"
            })

        except Exception as e:
            self.log_error(f"Error updating tool {tool_name}: {e}")
            self.send_error(500, f"Error updating tool: {e}")

    def handle_search(self, query: str):
        """Search tools by q (name/description/example) and optional type.
        GET /api/tools/search?q=term[&type=brew|cask|mas|tap][&limit=200]
        """
        from urllib.parse import parse_qs
        params = parse_qs(query or "")
        q = (params.get('q', [''])[0] or '').strip().lower()
        type_filter = (params.get('type', [''])[0] or '').strip().lower()
        try:
            limit = int((params.get('limit', [''])[0] or '200'))
        except Exception:
            limit = 200
        limit = max(1, min(limit, 1000))

        if self.db_con is not None:
            try:
                like = f"%{q}%" if q else "%"
                if type_filter in {"brew", "cask", "mas", "tap"}:
                    sql = (
                        "SELECT name, description, example, type, mas_id, user_edited, "
                        "CAST(last_edited AS VARCHAR) AS last_edited "
                        "FROM tools WHERE type = ? AND (lower(name) LIKE ? "
                        "OR lower(description) LIKE ? OR lower(example) LIKE ? "
                        "OR lower(COALESCE(mas_id,'')) LIKE ?) "
                        "ORDER BY lower(name) LIMIT ?"
                    )
                    rows = self.db_con.execute(sql, [type_filter, like, like, like, like, limit]).fetchall()
                else:
                    sql = (
                        "SELECT name, description, example, type, mas_id, user_edited, "
                        "CAST(last_edited AS VARCHAR) AS last_edited "
                        "FROM tools WHERE (lower(name) LIKE ? OR lower(description) LIKE ? "
                        "OR lower(example) LIKE ? OR lower(COALESCE(mas_id,'')) LIKE ?) "
                        "ORDER BY lower(name) LIMIT ?"
                    )
                    rows = self.db_con.execute(sql, [like, like, like, like, limit]).fetchall()
                cols = [d[0] for d in self.db_con.description]
                data = [dict(zip(cols, r)) for r in rows]
                self.send_json_response(data)
                return
            except Exception as e:
                self.send_error(400, f"Search error: {e}")
                return

        # Fallback: file-based search
        if not self.config.json_file.exists():
            self.send_json_response([])
            return
        try:
            import json
            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)
            def norm(s):
                return (s or '').lower()
            def match(t):
                if type_filter and t.get('type') != type_filter:
                    return False
                if not q:
                    return True
                return (
                    q in norm(t.get('name')) or q in norm(t.get('description')) or q in norm(t.get('example')) or q in norm(t.get('mas_id'))
                )
            out = [t for t in tools if match(t)][:limit]
            self.send_json_response(out)
        except Exception as e:
            self.send_error(500, f"Search error: {e}")

    def handle_recent(self, query: str):
        """Return recently edited tools ordered by last_edited desc.
        GET /api/tools/recent[?limit=50]
        """
        from urllib.parse import parse_qs
        try:
            params = parse_qs(query or "")
            limit = int((params.get('limit', [''])[0] or '50'))
        except Exception:
            limit = 50
        limit = max(1, min(limit, 1000))

        if self.db_con is not None:
            try:
                sql = (
                    "SELECT name, description, example, type, mas_id, user_edited, "
                    "CAST(last_edited AS VARCHAR) AS last_edited "
                    "FROM tools WHERE last_edited IS NOT NULL "
                    "ORDER BY last_edited DESC LIMIT ?"
                )
                rows = self.db_con.execute(sql, [limit]).fetchall()
                cols = [d[0] for d in self.db_con.description]
                data = [dict(zip(cols, r)) for r in rows]
                self.send_json_response(data)
                return
            except Exception as e:
                self.send_error(500, f"Recent error: {e}")
                return

        # Fallback: file-based using JSON last_edited (if present)
        if not self.config.json_file.exists():
            self.send_json_response([])
            return
        try:
            import json
            from datetime import datetime
            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)
            def parse_dt(val):
                try:
                    return datetime.fromisoformat(val.replace(' ', 'T')) if val else None
                except Exception:
                    return None
            tools = [t for t in tools if parse_dt(t.get('last_edited'))]
            tools.sort(key=lambda t: parse_dt(t.get('last_edited')), reverse=True)
            self.send_json_response(tools[:limit])
        except Exception as e:
            self.send_error(500, f"Recent error: {e}")

    def handle_types(self):
        """Return counts by type."""
        if self.db_con is not None:
            try:
                rows = self.db_con.execute(
                    "SELECT type, COUNT(*) AS count FROM tools GROUP BY 1 ORDER BY 1"
                ).fetchall()
                result = {str(r[0] or ''): int(r[1]) for r in rows}
                self.send_json_response({"counts": result})
                return
            except Exception as e:
                self.send_error(500, f"Types error: {e}")
                return

        # Fallback: file-based
        if not self.config.json_file.exists():
            self.send_json_response({"counts": {}})
            return
        try:
            import json
            from collections import Counter
            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)
            counts = Counter(t.get('type') for t in tools)
            self.send_json_response({"counts": dict(counts)})
        except Exception as e:
            self.send_error(500, f"Types error: {e}")

    def handle_query(self, path: str, query: str):
        """Run read-only SQL queries against DuckDB: GET /api/query?sql=..."""
        from urllib.parse import parse_qs
        if self.db_con is None:
            self.send_error(503, "DuckDB is not available")
            return
        params = parse_qs(query or "")
        sql = (params.get('sql', [''])[0] or '').strip()
        if not sql:
            self.send_error(400, "Missing sql parameter")
            return
        # Enforce read-only simple SELECT queries
        if not sql.lower().lstrip().startswith('select'):
            self.send_error(400, "Only SELECT queries are allowed")
            return
        try:
            rows = self.db_con.execute(sql).fetchall()
            cols = [d[0] for d in self.db_con.description]
            data = [dict(zip(cols, r)) for r in rows]
            self.send_json_response({"rows": data, "columns": cols})
        except Exception as e:
            self.send_error(400, f"Query error: {e}")

    def handle_batch_update(self):
        """Handle batch updates of multiple tools"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No data provided")
                return

            body = self.rfile.read(content_length).decode('utf-8')
            try:
                batch_updates = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON data")
                return

            if not isinstance(batch_updates, list):
                self.send_error(400, "Expected array of updates")
                return

            # Prefer DB if available
            if self.db_con is not None:
                updated_count = 0
                errors = []
                for update in batch_updates:
                    try:
                        name = update.get('name')
                        if not name:
                            errors.append("Missing tool name in update")
                            continue
                        dbmod.update_tool_fields(self.db_con, name, update)
                        updated_count += 1
                    except KeyError:
                        errors.append(f"Tool '{update.get('name')}' not found")
                    except Exception as e:
                        errors.append(f"Error updating tool '{update.get('name')}': {e}")
                self.log_message(f"Batch updated {updated_count} tools (DB)")
                self.send_json_response({
                    "success": True,
                    "updated_count": updated_count,
                    "errors": errors,
                    "message": f"Batch update completed: {updated_count} tools updated"
                })
                return

            # Fallback: file-based batch update
            # Create backup before batch update
            self.create_backup()

            # Load current tools
            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                tools = json.load(f)

            updated_count = 0
            errors = []

            for update in batch_updates:
                try:
                    tool_name = update.get('name')
                    if not tool_name:
                        errors.append("Missing tool name in update")
                        continue

                    # Find tool
                    tool = next((t for t in tools if t['name'] == tool_name), None)
                    if not tool:
                        errors.append(f"Tool '{tool_name}' not found")
                        continue

                    # Apply updates
                    if 'description' in update:
                        tool['description'] = update['description']
                    if 'example' in update:
                        tool['example'] = update['example']

                    tool['last_edited'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    tool['user_edited'] = True
                    updated_count += 1

                except Exception as e:
                    errors.append(f"Error updating tool: {e}")

            # Save if any updates were made
            if updated_count > 0:
                with open(self.config.json_file, 'w', encoding='utf-8') as f:
                    json.dump(tools, f, indent=2, ensure_ascii=False)

                self.update_csv_file(tools)
                self.log_message(f"Batch updated {updated_count} tools")

            self.send_json_response({
                "success": True,
                "updated_count": updated_count,
                "errors": errors,
                "message": f"Batch update completed: {updated_count} tools updated"
            })

        except Exception as e:
            self.log_error(f"Batch update error: {e}")
            self.send_error(500, f"Batch update error: {e}")

    def handle_regenerate_data(self):
        """Trigger data regeneration"""
        try:
            # This would typically call the data generation script
            # For now, just return a success message
            self.send_json_response({
                "success": True,
                "message": "Data regeneration triggered",
                "suggestion": "Run: python3 scripts/gen_tools_data.py"
            })

        except Exception as e:
            self.log_error(f"Regeneration error: {e}")
            self.send_error(500, f"Regeneration error: {e}")

    # CSV export is disabled in DuckDB-only mode
    def update_csv_file(self, tools: List[Dict[str, Any]]):
        return

    def create_backup(self):
        """Create backup of current data files"""
        try:
            import shutil
            timestamp = time.strftime('%Y%m%d_%H%M%S')

            if self.config.json_file.exists():
                backup_json = self.config.json_file.parent / f"tools_backup_{timestamp}.json"
                shutil.copy2(self.config.json_file, backup_json)

            if self.config.csv_file.exists():
                backup_csv = self.config.csv_file.parent / f"tools_backup_{timestamp}.csv"
                shutil.copy2(self.config.csv_file, backup_csv)

        except Exception as e:
            self.log_error(f"Backup creation failed: {e}")

    def send_json_response(self, data: Any):
        """Send JSON response with proper headers"""
        try:
            json_data = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(json_data)))
            self.end_headers()
            self.wfile.write(json_data)

        except Exception as e:
            self.log_error(f"Error sending JSON response: {e}")
            self.send_error(500, "Error sending response")

    def log_error(self, format_str: str, *args):
        """Log error messages (compatible with BaseHTTPRequestHandler)"""
        try:
            message = (format_str % args) if args else str(format_str)
        except Exception:
            message = str(format_str)
        print(f"ERROR: {message}", file=sys.stderr)

    def log_message(self, format_str: str, *args):
        """Override to provide cleaner logging"""
        if args:
            message = format_str % args
        else:
            message = format_str

        # Don't log static file requests for common files
        if any(ext in message for ext in ['.css', '.js', '.png', '.ico', '.svg']):
            return

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {self.address_string()} - {message}")


def cleanup_old_backups(config, max_backups: int = 10):
    """Clean up old backup files"""
    try:
        backup_pattern = "tools_backup_*.json"
        backup_files = list(config.output_dir.glob(backup_pattern))

        if len(backup_files) > max_backups:
            # Sort by creation time and remove oldest
            backup_files.sort(key=lambda f: f.stat().st_mtime)
            for old_backup in backup_files[:-max_backups]:
                old_backup.unlink()
                # Also remove corresponding CSV backup
                csv_backup = old_backup.with_suffix('.csv')
                if csv_backup.exists():
                    csv_backup.unlink()

    except Exception as e:
        print(f"Warning: Failed to cleanup old backups: {e}")


def main():
    """Main server function"""
    parser = argparse.ArgumentParser(
        description="Brewfile Analyzer Combined Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This server provides both static file serving and API endpoints:

Static Files:
  - Serves files from project root with security restrictions
  - Automatic redirect from / to /docs/tools/index.html
  - No directory listing for security

API Endpoints:
  - GET /api/health - Server health check
  - GET /api/config - Configuration information
  - GET /api/tools - List all tools
  - GET /api/tools/<name> - Get specific tool
  - PATCH /api/tools/<name> - Update tool description/example
  - POST /api/tools/batch-update - Batch update multiple tools
  - POST /api/regenerate - Trigger data regeneration

Examples:
  %(prog)s                    # Start on default port 8000
  %(prog)s --port 9000        # Start on port 9000
  %(prog)s --host 0.0.0.0     # Allow external connections
        """
    )

    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8000,
        help='Port to listen on (default: 8000)'
    )

    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Reduce logging output'
    )

    args = parser.parse_args()

    # Get configuration
    config = get_config()

    # Clean up old backups
    cleanup_old_backups(config)

    # Create server
    server_address = (args.host, args.port)

    try:
        httpd = ThreadingHTTPServer(server_address, CombinedHandler)

        print("Brewfile Analyzer Combined Server")
        print("=" * 50)
        print(f"Project root: {config.root}")
        if dbmod is not None:
            try:
                db_path = dbmod.get_db_path(config)
                print(f"DB backend: DuckDB ✓ ({db_path})")
            except Exception:
                print("DB backend: DuckDB ✓ (path unavailable)")
        else:
            print("DB backend: DuckDB not installed")
        print(f"Server: http://{args.host}:{args.port}")
        print()
        print("Web Interface:")
        print(f"  http://{args.host}:{args.port}/docs/tools/")
        print()
        print("API Endpoints:")
        print(f"  http://{args.host}:{args.port}/api/health")
        print(f"  http://{args.host}:{args.port}/api/tools")
        print()
        if not args.quiet:
            print("Features:")
            print("  ✓ Static file serving with security")
            print("  ✓ Live editing with automatic backup")
            print("  ✓ CORS support for API access")
            print()

        print("Press Ctrl+C to stop the server")
        print("=" * 50)

        httpd.serve_forever()

    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
