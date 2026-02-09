"""
MCP Server Mode - Expose Vibecode as an MCP Server.

Extension 6: Allows external AI agents (Claude Desktop, Cursor, etc.) 
to use Vibecode's PDF snapshotting and RAG capabilities as tools.

Usage:
    vibecode serve --port 8080
    
Or as a subprocess:
    python -m vibecode.mcp_server
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from mcp.server.fastmcp import FastMCP
    MCP_SERVER_AVAILABLE = True
except ImportError:
    MCP_SERVER_AVAILABLE = False
    FastMCP = None

from .engine import ProjectEngine
from .discovery import discover_files

logger = logging.getLogger(__name__)


def create_mcp_server(project_root: Optional[str] = None):
    """
    Create and configure a Vibecode MCP server.
    
    Args:
        project_root: Root directory for project operations
        
    Returns:
        Configured FastMCP server instance
    """
    if not MCP_SERVER_AVAILABLE:
        raise ImportError(
            "MCP Server not available. Install with: pip install mcp[server]"
        )
    
    # Initialize FastMCP server
    mcp = FastMCP("vibecode-server")
    
    # Default to current directory
    root = Path(project_root) if project_root else Path.cwd()
    
    # --- Tool Definitions ---
    
    @mcp.tool()
    def snapshot_codebase(
        path: str = ".",
        output_type: str = "llm",
        output_name: str = "snapshot"
    ) -> str:
        """
        Generate a PDF snapshot of the codebase.
        
        Args:
            path: Path to the project root or .vibecode.yaml config
            output_type: Output type - 'llm' for machine-readable, 'human' for human-readable
            output_name: Base name for the output file (without extension)
            
        Returns:
            Path to the generated PDF snapshot
        """
        try:
            project_path = Path(path).resolve()
            
            # Find config
            config_path = project_path / ".vibecode.yaml"
            if not config_path.exists():
                return f"Error: No .vibecode.yaml found at {config_path}"
            
            # Create engine
            engine = ProjectEngine(str(config_path))
            
            # Render
            output_path = str(project_path / f"{output_name}_{output_type}.pdf")
            engine.render(output_type, output_path)
            
            return f"Snapshot created: {output_path}"
            
        except Exception as e:
            return f"Error creating snapshot: {e}"
    
    @mcp.tool()
    def search_files(
        query: str,
        path: str = ".",
        extensions: list = None
    ) -> str:
        """
        Search for files in the project matching a query.
        
        Args:
            query: Search query (filename pattern or text to search)
            path: Path to search within
            extensions: List of file extensions to include (e.g., ['.py', '.js'])
            
        Returns:
            List of matching file paths
        """
        try:
            project_path = Path(path).resolve()
            
            if extensions is None:
                extensions = ['.py', '.js', '.ts', '.md', '.txt', '.json', '.yaml']
            
            # Find matching files
            matches = []
            for ext in extensions:
                for file_path in project_path.rglob(f"*{ext}"):
                    if query.lower() in file_path.name.lower():
                        matches.append(str(file_path.relative_to(project_path)))
            
            if not matches:
                return f"No files found matching '{query}'"
            
            return json.dumps(matches, indent=2)
            
        except Exception as e:
            return f"Error searching files: {e}"
    
    @mcp.tool()
    def read_file(file_path: str) -> str:
        """
        Read the contents of a file.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            File contents as a string
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return f"Error: File not found: {file_path}"
            
            if path.stat().st_size > 1024 * 1024:  # 1MB limit
                return f"Error: File too large (max 1MB)"
            
            return path.read_text(encoding='utf-8')
            
        except Exception as e:
            return f"Error reading file: {e}"
    
    @mcp.tool()
    def list_files(
        path: str = ".",
        max_depth: int = 3
    ) -> str:
        """
        List files in a directory tree.
        
        Args:
            path: Root path to list
            max_depth: Maximum depth to traverse
            
        Returns:
            JSON list of file and directory names
        """
        try:
            root_path = Path(path).resolve()
            
            if not root_path.exists():
                return f"Error: Path not found: {path}"
            
            files = []
            dirs = []
            
            for item in sorted(root_path.iterdir()):
                if item.name.startswith('.'):
                    continue
                if item.is_file():
                    files.append(item.name)
                elif item.is_dir():
                    dirs.append(f"{item.name}/")
            
            result = {
                "path": str(root_path),
                "directories": dirs[:50],  # Limit
                "files": files[:100]
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error listing files: {e}"
    
    @mcp.tool()
    def get_project_summary(path: str = ".") -> str:
        """
        Get a summary of the project structure and statistics.
        
        Args:
            path: Path to the project root
            
        Returns:
            JSON summary of the project
        """
        try:
            project_path = Path(path).resolve()
            
            # Count files by extension
            ext_counts: Dict[str, int] = {}
            total_lines = 0
            
            for file_path in project_path.rglob("*"):
                if file_path.is_file() and not any(
                    p.startswith('.') for p in file_path.parts
                ):
                    ext = file_path.suffix or "(no extension)"
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1
                    
                    # Count lines for text files
                    try:
                        if file_path.suffix in ['.py', '.js', '.ts', '.md', '.txt']:
                            total_lines += len(file_path.read_text(encoding='utf-8').splitlines())
                    except:
                        pass
            
            summary = {
                "project_path": str(project_path),
                "files_by_extension": dict(sorted(ext_counts.items(), key=lambda x: -x[1])[:20]),
                "total_files": sum(ext_counts.values()),
                "estimated_lines": total_lines
            }
            
            return json.dumps(summary, indent=2)
            
        except Exception as e:
            return f"Error getting summary: {e}"
    
    return mcp


def run_server(port: int = 8080, project_root: Optional[str] = None):
    """
    Run the Vibecode MCP server.
    
    Args:
        port: Port to run on
        project_root: Root directory for project operations
    """
    mcp = create_mcp_server(project_root)
    
    logger.info(f"🚀 Starting Vibecode MCP Server on port {port}")
    logger.info("Available tools: snapshot_codebase, search_files, read_file, list_files, get_project_summary")
    
    # Run the server
    mcp.run()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vibecode MCP Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run on")
    parser.add_argument("--project", type=str, default=None, help="Project root directory")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    run_server(port=args.port, project_root=args.project)
