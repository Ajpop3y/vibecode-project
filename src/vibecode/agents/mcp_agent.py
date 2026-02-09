"""
MCPAgent - Specialized AI Agent for External Tool Interaction.
Focuses on retrieving data, listing files, and preparing content for the project.
"""
import logging
from ..chat.engine import ChatEngine
from ..chat.mcp_host import get_mcp_host

logger = logging.getLogger(__name__)

MCP_SYSTEM_PROMPT = """You are the **MCP Tool Expert**.
Your goal is to help the user access external data using the available tools (Google Drive, GitHub, etc.).

### Instructions:
1. **Use Tools Freely**: You are designed to use tools. Don't be shy.
2. **Be Concise**: When listing files, just list them.
3. **Data Retrieval**: When the user asks to "read" or "get" a file, use the appropriate tool.
4. **No Code Generation**: Do not write Python code unless asked to creating a script. Focus on **Data Fetching**.

### Tool Usage:
- To list files: `drive__list_files`, `github__list_repos`
- To read content: `drive__read_file`, `github__get_file`
- To search: `drive__search`, `github__search`

If you find a file the user wants, display its content clearly so they can save it.
"""

class MCPAgent(ChatEngine):
    """
    Specialized ChatEngine for MCP interactions.
    """
    
    def __init__(self):
        # Initialize with no PDF context initially (or empty)
        # We don't strictly need the project source code to fetch external data
        super().__init__(pdf_path="") 
        
        # Override system prompt
        self.system_prompt_override = MCP_SYSTEM_PROMPT
        
    def get_system_prompt(self, context: str = "") -> str:
        """Override to return the tool-focused prompt."""
        # We process tools in the base class, so just return the core prompt + tool definitions
        base = self.system_prompt_override
        
        # Add available tools to prompt (if not handled by base class provider logic)
        # The base ChatEngine._init_provider usually handles tool binding if using function calling API.
        # But for prompts, we might need to append descriptions if the model is non-native.
        
        return base

    def send_message(self, user_query: str, temperature: float = 0.0) -> str:
        """
        Send message with low temperature for deterministic tool use.
        """
        # Ensure MCP host is ready
        if not self.mcp_host:
            self._init_mcp()
            
        return super().send_message(user_query, temperature=temperature)
