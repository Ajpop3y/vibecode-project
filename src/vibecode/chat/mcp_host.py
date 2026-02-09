"""
MCPHost - Universal AI Socket for Vibecode.

Implements Model Context Protocol (MCP) client to connect Vibecode 
to external services (GitHub, Google Drive, Slack, etc.)

ECR #009: MCP Integration - Universal AI Socket Architecture
"""

import os
import re
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import AsyncExitStack

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class MCPHostError(Exception):
    """Raised when MCP host operations fail."""
    pass


class MCPHost:
    """
    The Universal AI Socket.
    
    Connects Vibecode to any MCP-compatible service defined in mcp_servers.json.
    Aggregates tools from all connected servers and provides unified access.
    
    Architecture:
        - Configuration-driven: Add servers via JSON, no code changes needed
        - Namespaced tools: github__create_issue, drive__read_file, etc.
        - Async-first: All operations are async for optimal performance
    
    Usage:
        host = MCPHost()
        await host.start()
        
        # Tools are available for LLM injection
        tools = host.available_tools
        
        # Execute a tool
        result = await host.call_tool("github__create_issue", {...})
        
        await host.shutdown()
    """
    
    # Default config location
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "mcp_servers.json"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the MCPHost.
        
        Args:
            config_path: Path to mcp_servers.json. Uses default if None.
        """
        if not MCP_AVAILABLE:
            logger.warning("MCP SDK not installed. Install with: pip install mcp")
            
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}
        self.available_tools: List[Dict[str, Any]] = []
        self._started = False
    
    def _expand_env_vars(self, value: Any) -> Any:
        """
        Expand ${VAR_NAME} patterns in configuration values.
        
        Args:
            value: String or dict/list to expand
            
        Returns:
            Value with environment variables expanded
        """
        if isinstance(value, str):
            # Match ${VAR_NAME} pattern
            pattern = r'\$\{([^}]+)\}'
            
            def replacer(match):
                var_name = match.group(1)
                return os.environ.get(var_name, "")
            
            return re.sub(pattern, replacer, value)
        
        elif isinstance(value, dict):
            return {k: self._expand_env_vars(v) for k, v in value.items()}
        
        elif isinstance(value, list):
            return [self._expand_env_vars(item) for item in value]
        
        return value
    
    async def start(self) -> None:
        """
        Bootstrap connections to all configured MCP servers.
        
        Reads mcp_servers.json and establishes connections to each server.
        Tools from all servers are aggregated into self.available_tools.
        """
        if not MCP_AVAILABLE:
            logger.warning("MCP SDK not available. Skipping MCP initialization.")
            return
            
        if self._started:
            logger.warning("MCPHost already started")
            return
        
        if not self.config_path.exists():
            logger.info(f"No MCP config at {self.config_path}. MCP disabled.")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid MCP config JSON: {e}")
            return
        
        servers = config.get('mcpServers', {})
        if not servers:
            logger.info("No MCP servers configured.")
            return
        
        logger.info(f"🔌 MCP: Connecting to {len(servers)} server(s)...")
        
        for name, server_conf in servers.items():
            await self._connect_server(name, server_conf)
        
        self._started = True
        logger.info(f"✅ MCP: Ready. {len(self.available_tools)} external tools available.")
    
    async def _connect_server(self, name: str, conf: dict) -> None:
        """
        Launch and connect to a single MCP server.
        
        Args:
            name: Server identifier (e.g., 'github', 'drive')
            conf: Server configuration from mcp_servers.json
        """
        try:
            # Skip if missing required fields
            if 'command' not in conf or 'args' not in conf:
                logger.warning(f"MCP: Server '{name}' missing command/args. Skipping.")
                return
            
            # 1. Prepare Server Parameters with env expansion
            server_env = os.environ.copy()
            if 'env' in conf:
                expanded_env = self._expand_env_vars(conf['env'])
                server_env.update(expanded_env)
            
            params = StdioServerParameters(
                command=conf['command'],
                args=conf['args'],
                env=server_env
            )
            
            # 2. Launch subprocess and connect
            read, write = await self.exit_stack.enter_async_context(
                stdio_client(params)
            )
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
            # 3. Initialize the session (MCP handshake)
            await session.initialize()
            self.sessions[name] = session
            
            # 4. Discover tools from this server
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                # Namespace tool names to avoid collisions
                namespaced_name = f"{name}__{tool.name}"
                
                tool_def = {
                    "name": namespaced_name,
                    "description": tool.description or f"Tool from {name}",
                    "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                    "server_name": name,
                    "original_name": tool.name
                }
                self.available_tools.append(tool_def)
            
            logger.info(f"  ✔ {name}: {len(tools_response.tools)} tools")
            
        except FileNotFoundError:
            logger.error(f"❌ MCP: Server '{name}' command not found: {conf.get('command')}")
        except Exception as e:
            logger.error(f"❌ MCP: Failed to connect to '{name}': {e}")
    
    async def call_tool(self, namespaced_tool_name: str, arguments: dict) -> Any:
        """
        Execute a tool on the appropriate remote server.
        
        Args:
            namespaced_tool_name: Tool name in format "server__tool" (e.g., "github__create_issue")
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result content
            
        Raises:
            MCPHostError: If tool name is invalid or server not connected
        """
        if "__" not in namespaced_tool_name:
            raise MCPHostError(f"Invalid tool name format: {namespaced_tool_name}. Expected 'server__tool'.")
        
        server_name, tool_name = namespaced_tool_name.split("__", 1)
        session = self.sessions.get(server_name)
        
        if not session:
            raise MCPHostError(f"Server '{server_name}' is not connected.")
        
        try:
            result = await session.call_tool(tool_name, arguments)
            content = result.content
            
            # Extension 5: RAG Auto-Ingest
            # If result contains substantial text content, auto-ingest into KnowledgeBase
            self._maybe_ingest_to_rag(namespaced_tool_name, content)
            
            return content
        except Exception as e:
            logger.error(f"MCP: Tool execution failed: {e}")
            raise MCPHostError(f"Tool '{namespaced_tool_name}' failed: {e}")
    
    def _maybe_ingest_to_rag(self, tool_name: str, content: Any) -> None:
        """
        Auto-ingest MCP tool results into RAG KnowledgeBase.
        
        Extension 5: RAG Auto-Ingest on MCP Change
        
        Args:
            tool_name: Namespaced tool name (source identifier)
            content: Tool result content
        """
        try:
            # Extract text from content (could be string, list of content blocks, etc.)
            text = self._extract_text_content(content)
            
            if not text or len(text) < 100:
                # Skip very short content
                return
            
            # Try to ingest into KnowledgeBase
            try:
                from .knowledge import KnowledgeBase
                
                kb = KnowledgeBase.get_instance()
                if kb:
                    # Create a virtual document from the MCP result
                    doc_id = f"mcp://{tool_name}"
                    kb.ingest_text(
                        text=text,
                        source=doc_id,
                        metadata={"source_type": "mcp_tool", "tool": tool_name}
                    )
                    logger.debug(f"RAG: Auto-ingested {len(text)} chars from {tool_name}")
            except ImportError:
                # KnowledgeBase not available, skip
                pass
            except Exception as e:
                logger.debug(f"RAG: Auto-ingest skipped: {e}")
                
        except Exception as e:
            # Never fail the tool call due to RAG issues
            logger.debug(f"RAG: Auto-ingest error (ignored): {e}")
    
    def _extract_text_content(self, content: Any) -> str:
        """
        Extract text from MCP content which may be various formats.
        
        Args:
            content: MCP tool result content
            
        Returns:
            Extracted text string
        """
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            # List of content blocks
            texts = []
            for block in content:
                if isinstance(block, str):
                    texts.append(block)
                elif hasattr(block, 'text'):
                    texts.append(block.text)
                elif isinstance(block, dict) and 'text' in block:
                    texts.append(block['text'])
            return "\n".join(texts)
        
        if hasattr(content, 'text'):
            return content.text
        
        if isinstance(content, dict) and 'text' in content:
            return content['text']
        
        return ""
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions formatted for LLM injection.
        
        Returns:
            List of tool definitions suitable for system prompt injection
        """
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
            for tool in self.available_tools
        ]
    
    def format_tools_for_prompt(self) -> str:
        """
        Format tools as a string for system prompt injection.
        
        Returns:
            Human-readable tool descriptions for LLM
        """
        if not self.available_tools:
            return ""
        
        lines = ["\n## Available External Tools (MCP)\n"]
        lines.append("You have access to the following external tools via MCP:\n")
        
        for tool in self.available_tools:
            lines.append(f"- **{tool['name']}**: {tool['description']}")
        
        lines.append("\nTo use a tool, respond with a function call in the format:")
        lines.append("```")
        lines.append('{"tool": "server__tool_name", "arguments": {...}}')
        lines.append("```")
        
        return "\n".join(lines)
    
    @property
    def is_connected(self) -> bool:
        """Check if any MCP servers are connected."""
        return len(self.sessions) > 0
    
    @property
    def connected_servers(self) -> List[str]:
        """Get list of connected server names."""
        return list(self.sessions.keys())
    
    async def shutdown(self) -> None:
        """
        Gracefully close all MCP server connections.
        """
        if self._started:
            logger.info("🔌 MCP: Shutting down...")
            await self.exit_stack.aclose()
            self.sessions.clear()
            self.available_tools.clear()
            self._started = False
            logger.info("✅ MCP: All connections closed.")


# Singleton instance for global access
_mcp_host: Optional[MCPHost] = None


def get_mcp_host() -> MCPHost:
    """
    Get or create the global MCPHost instance.
    
    Returns:
        The global MCPHost instance
    """
    global _mcp_host
    if _mcp_host is None:
        _mcp_host = MCPHost()
    return _mcp_host


async def init_mcp_host(config_path: Optional[str] = None) -> MCPHost:
    """
    Initialize and start the global MCPHost.
    
    Args:
        config_path: Optional path to mcp_servers.json
        
    Returns:
        The started MCPHost instance
    """
    global _mcp_host
    _mcp_host = MCPHost(config_path)
    await _mcp_host.start()
    return _mcp_host
