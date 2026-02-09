"""
ChatEngine - Orchestration layer for VibeChat.
Integrates PDF ingestion, LLM providers, and conversation memory.
"""

import re
import logging
import difflib
from typing import List, Dict, Optional
from .ingest import parse_pdf, PDFContext
from .models import get_provider, BaseLLMProvider, SYSTEM_PROMPT_TEMPLATE
from .memory import ChatMemory
from .mcp_host import get_mcp_host, MCPHost
from ..settings import get_settings
from ..config import get_active_model_id

logger = logging.getLogger(__name__)


# --- PERSONA SYSTEM ---
# The specific personas that VibeChat can adopt
PERSONA_PROMPTS = {
    "General Assistant": """You are VibeChat, an expert AI developer.
- Be helpful, concise, and accurate.
- Balance high-level advice with code implementation.
""",
    
    "The Architect": """You are The Architect.
- Focus on **High-Level Structure**, **Design Patterns**, and **Scalability**.
- Do not write implementation details unless asked.
- Analyze the File Tree to suggest folder restructuring or module decoupling.
- Criticize circular dependencies and monolithic files.
""",
    
    "The Debugger": """You are The Debugger.
- Focus strictly on **Logic Errors**, **Race Conditions**, and **Edge Cases**.
- When a stack trace is provided, hunt the error down relentlessly.
- Be terse. Do not lecture. Fix the bug.
- Use the 'Active Stack Trace' context to pinpoint line numbers.
""",
    
    "The Doc Writer": """You are The Doc Writer.
- Your job is to write **Docstrings**, **READMEs**, and **Technical Specs**.
- Do not change logic. Only add comments and documentation.
- Use Google Style Python Docstrings.
- If asked, generate a `README.md` that describes the entire project architecture based on the file tree.
"""
}


class ChatEngine:
    """
    Unified orchestration layer for VibeChat.
    Manages context loading, conversation history, and LLM interactions.
    """
    
    def __init__(self, pdf_path: str, provider_name: str = None, api_key: Optional[str] = None):
        """
        Initialize the ChatEngine.
        
        Args:
            pdf_path: Path to the Vibecode LLM PDF snapshot
            provider_name: LLM provider ('google', 'openai', 'anthropic', 'ollama'). 
                          If None, loads from UserSettings.
            api_key: Optional API key. If None, tries to load from settings or env.
        """
        self.pdf_path = pdf_path
        self.context: Optional[PDFContext] = None
        self.memory: Optional[ChatMemory] = None
        self.provider: Optional[BaseLLMProvider] = None
        self.reference_context: Optional[PDFContext] = None  # Time Travel comparison
        self.current_persona: str = "General Assistant"  # Persona system
        self.mcp_host: Optional[MCPHost] = None  # MCP Universal Socket
        
        # Initialize components
        self._provider_override = provider_name
        self._api_key_override = api_key
        self._current_provider_name = None
        
        self._load_context()
        self._init_provider()
        self._init_mcp()
    
    def _load_context(self):
        """Load the PDF context using ingest module."""
        logger.info("Initializing ChatEngine...")
        
        if not self.pdf_path:
            logger.info("No PDF path provided. Initializing with empty context.")
            # Create a dummy context for MCPAgent
            self.context = PDFContext(files={}, total_tokens=0, tree="", total_chars=0)
            self.memory = ChatMemory(context="", max_tokens=128000)
            return

        self.context = parse_pdf(self.pdf_path)
        
        # Initialize memory with loaded context
        context_str = self._format_context_for_injection()
        self.memory = ChatMemory(
            context=context_str,
            max_tokens=128000  # Default, can be updated via settings
        )
        
        logger.info(f"ChatEngine ready: {len(self.context.files)} files loaded")
    
    def _init_provider(self):
        """Initialize or re-initialize the LLM provider."""
        try:
            from ..settings import get_settings
            settings = get_settings()
            
            # Use overrides if present, else settings
            name = self._provider_override or settings.chat_provider
            key = self._api_key_override or settings.get_api_key(name)
            
            # Base URL (only for custom/openai/ollama typically, but passed generally)
            base_url = getattr(settings, 'custom_base_url', None)
            if not base_url:
                base_url = None
            
            # Only re-init if changed
            if name != self._current_provider_name or self.provider is None:
                self.provider = get_provider(name, key, base_url=base_url)
                self._current_provider_name = name
                logger.info(f"Initialized provider: {name}")
                
        except Exception as e:
            logger.warning(f"Could not load provider: {e}")
            self.provider = None
            logger.info("ChatEngine running in mock mode (no LLM provider)")
    
    def _init_mcp(self):
        """Initialize MCP Host - DISABLED FOR DEMO"""
        # Temporary disable for stability
        logger.info("MCP disabled for demo submission")
        self.mcp_host = None
        return
        
        # Original code below (commented out)
        # try:
        #     self.mcp_host = get_mcp_host()
        #     
        #     # MCP is async, but we need sync init for ChatEngine
        #     # Just get the host reference, actual connection happens on demand
        #     if self.mcp_host.available_tools:
        #         logger.info(f"MCP: {len(self.mcp_host.available_tools)} external tools available")
        #     else:
        #         logger.debug("MCP: No external tools configured")
        # except Exception as e:
        #     logger.debug(f"MCP initialization skipped: {e}")
        #     self.mcp_host = None
    
    def _format_context_for_injection(self) -> str:
        """
        Format the codebase context for injection into system prompt.
        
        Returns:
            Formatted string with tree + file contents
        """
        context_parts = []
        
        # Add project tree
        context_parts.append(f"PROJECT TREE:\n{self.context.tree}\n")
        
        # Add file contents
        for path, content in self.context.files.items():
            context_parts.append(f"\n=== FILE: {path} ===\n{content}")
        
        return "\n".join(context_parts)
    
    def detect_stack_trace(self, text: str) -> List[str]:
        """
        Robustly scan text for Python stack traces.
        Handles Absolute/Relative path mismatches and OS separators.
        
        Args:
            text: User message that may contain a stack trace
            
        Returns:
            List of matched file paths from our context
        """
        if not self.context:
            return []
        
        # Regex for Python Tracebacks: File "...", line ...
        pattern = r'File "(.*?)", line \d+'
        matches = re.findall(pattern, text)
        
        detected_files = []
        context_paths = list(self.context.files.keys())
        
        for raw_path in matches:
            # Normalize slashes (Windows -> Unix)
            clean_path = raw_path.replace('\\', '/')
            
            # 1. Try Exact Match
            if clean_path in context_paths:
                if clean_path not in detected_files:
                    detected_files.append(clean_path)
                continue
            
            # 2. Try Suffix Match (handles absolute vs relative paths)
            found = False
            for ctx_path in context_paths:
                if clean_path.endswith(ctx_path):
                    # Check boundary to avoid partial filename matches
                    boundary_index = len(clean_path) - len(ctx_path)
                    if boundary_index == 0 or clean_path[boundary_index - 1] == '/':
                        if ctx_path not in detected_files:
                            detected_files.append(ctx_path)
                        found = True
                        break
            
            if found:
                continue
            
            # 3. Try Filename Match (fallback)
            filename = clean_path.split('/')[-1]
            for ctx_path in context_paths:
                if ctx_path.endswith(f"/{filename}") or ctx_path == filename:
                    if ctx_path not in detected_files:
                        detected_files.append(ctx_path)
                    break
        
        if detected_files:
            logger.info(f"Stack trace detected: {len(detected_files)} files identified")
        
        return detected_files
    
    def load_reference(self, reference_pdf_path: str) -> bool:
        """
        Load a reference PDF for Time Travel comparison.
        
        Args:
            reference_pdf_path: Path to the snapshot PDF to compare against
            
        Returns:
            True if successfully loaded, False otherwise
        """
        try:
            self.reference_context = parse_pdf(reference_pdf_path)
            logger.info(f"Time Travel: Loaded reference with {len(self.reference_context.files)} files")
            return True
        except Exception as e:
            logger.error(f"Failed to load reference PDF: {e}")
            self.reference_context = None
            return False
    
    def get_file_diff(self, filename: str) -> str:
        """
        Compute the Unified Diff for a specific file between current and reference.
        
        Args:
            filename: Path to the file to diff
            
        Returns:
            Unified diff string, or empty if no changes
        """
        if not self.reference_context:
            return ""
        
        current_content = self.context.files.get(filename, "")
        reference_content = self.reference_context.files.get(filename, "")
        
        # If identical or missing in reference
        if current_content == reference_content:
            return ""
        
        if not reference_content:
            return f"(New File: {filename})"
        
        if not current_content:
            return f"(Deleted File: {filename})"
        
        # Generate Unified Diff
        diff = difflib.unified_diff(
            reference_content.splitlines(),
            current_content.splitlines(),
            fromfile=f"SNAPSHOT/{filename}",
            tofile=f"CURRENT/{filename}",
            lineterm=""
        )
        return "\n".join(list(diff))
    
    def set_persona(self, persona_name: str):
        """Switch the active persona for AI responses."""
        if persona_name in PERSONA_PROMPTS:
            self.current_persona = persona_name
            logger.info(f"Persona switched to: {persona_name}")
        else:
            logger.warning(f"Unknown persona: {persona_name}")
    
    def get_system_prompt(self, context: str = "") -> str:
        """Get the combined system prompt for the current persona."""
        persona_instructions = PERSONA_PROMPTS.get(
            self.current_persona, 
            PERSONA_PROMPTS["General Assistant"]
        )
        
        # Base prompt: persona + system template
        base_prompt = f"{persona_instructions}\n\n{SYSTEM_PROMPT_TEMPLATE}"
        
        # Inject Context explicitly
        if context:
            base_prompt += f"\n\n{context}"
        
        # Inject MCP tools if available
        if self.mcp_host and self.mcp_host.available_tools:
            mcp_tools_prompt = self.mcp_host.format_tools_for_prompt()
            base_prompt = f"{base_prompt}\n{mcp_tools_prompt}"
        
        return base_prompt
    
    def select_relevant_context(self, user_query: str, max_tokens: int = 100000) -> str:
        """
        Intelligently build context to fit within token limits.
        
        Strategy:
        1. ALWAYS include File Tree (high value, low cost)
        2. PRIORITIZE: Stack trace files (if crash detected)
        3. SCORE remaining files by relevance to query
        4. INJECT: Time Travel diffs (if reference loaded)
        5. PACK context until token limit reached
        
        Args:
            user_query: The user's question
            max_tokens: Maximum context tokens to use
            
        Returns:
            Optimized context string
        """
        if not self.context:
            self.refresh_context()
        
        # 1. Start with the tree
        final_context = f"PROJECT ARCHITECTURE:\n{self.context.tree}\n\n"
        current_tokens = len(final_context) // 4
        included_paths = set()
        
        # --- TIME TRAVEL HEADER ---
        if self.reference_context:
            final_context += "!!! TIME TRAVEL MODE ACTIVE !!!\n"
            final_context += "You are analyzing REGRESSIONS. Focus on the DIFFS below.\n\n"
            current_tokens += 20
        
        # --- STACK TRACE PRIORITY INJECTION ---
        priority_files = self.detect_stack_trace(user_query)
        
        # Extract line numbers from traceback
        trace_data = re.findall(r'File "(.*?)", line (\d+)', user_query)
        crash_map = {}
        for path, line in trace_data:
            filename = path.replace('\\', '/').split('/')[-1]
            crash_map[filename] = line
        
        if priority_files:
            logger.info(f"Active Stack Trace: Priority loading {len(priority_files)} files")
            final_context += "--- ACTIVE DEBUGGING CONTEXT (PRIORITY) ---\n"
            final_context += "!!! THE USER IS DEBUGGING A CRASH !!!\n\n"
            
            for path in priority_files:
                content = self.context.files.get(path, "")
                filename = path.split('/')[-1]
                
                # Inject crash line hint if available
                if filename in crash_map:
                    line_num = crash_map[filename]
                    final_context += f"!!! CRASH DETECTED IN {path} AT LINE {line_num} !!!\n"
                
                final_context += f"=== FILE: {path} ===\n{content}\n\n"
                current_tokens += len(content) // 4 + 20
                included_paths.add(path)
        
        # 2. Score remaining files by relevance
        scored_files = []
        query_terms = set(user_query.lower().split())
        
        for path, content in self.context.files.items():
            if path in included_paths:
                continue  # Skip already-included priority files
            
            score = 0
            
            # Boost if filename explicitly mentioned
            if path.lower() in user_query.lower():
                score += 50
            elif path.split('/')[-1].lower() in user_query.lower():
                score += 30
            
            # Boost based on content relevance
            for term in query_terms:
                if len(term) > 3 and term in content.lower():
                    score += 1
            
            scored_files.append((score, path, content))
        
        # 3. Sort by relevance
        scored_files.sort(key=lambda x: x[0], reverse=True)
        
        # 4. Pack context within limits (with Time Travel diffs)
        for score, path, content in scored_files:
            file_tokens = len(content) // 4
            header_tokens = 20
            
            # Check for diff if in Time Travel mode
            diff_text = ""
            if self.reference_context:
                diff_text = self.get_file_diff(path)
                if diff_text:
                    file_tokens += len(diff_text) // 4 + 10
            
            if current_tokens + file_tokens + header_tokens < max_tokens:
                # Inject diff if available
                if diff_text:
                    final_context += f"=== DIFF DETECTED: {path} ===\n{diff_text}\n\n"
                
                final_context += f"=== FILE: {path} ===\n{content}\n\n"
                current_tokens += (file_tokens + header_tokens)
                included_paths.add(path)
            
            if current_tokens >= max_tokens:
                break
        
        logger.info(f"Context Pruning: Selected {len(included_paths)}/{len(self.context.files)} files")
        return final_context
    
    def refresh_context(self):
        """
        Reload the PDF context.
        Useful for "snapshot time travel" feature (comparing different versions).
        """
        logger.info("Refreshing context from PDF...")
        self._load_context()
    
    def send_message(self, user_query: str, temperature: float = 0.7) -> str:
        """
        Send a message to the LLM and get a response.
        
        Args:
            user_query: User's question/request
            temperature: Model temperature (0-1)
            
        Returns:
            LLM response with [[REF: path]] citations
        """
        if self.provider is None:
            # Try to init again
            self._init_provider()
        
        if self.provider is None:
            logger.warning("No LLM provider available. Using mock response.")
            return self.mock_chat_response(user_query)
        
        # Reload provider settings in case they changed
        self._init_provider()
        
        # Add user message to memory
        self.memory.add_message('user', user_query)
        
        # Check if trimming is needed
        if self.memory.needs_trimming():
            logger.warning("Context window full. Trimming old messages...")
            self.memory.trim_if_needed()
        
        # Get messages for LLM
        messages = self.memory.get_messages()
        
        # Build Context
        # Reserve some tokens for history/response. 
        # Using 60% of max tokens for context is a safe heuristic.
        safe_context_limit = int(self.memory.max_tokens * 0.6)
        context = self.select_relevant_context(user_query, max_tokens=safe_context_limit)
        
        # Send to LLM
        try:
            settings = get_settings()
            model_id = get_active_model_id(settings.get_model_settings())
            
            response = self.provider.send_message(
                messages=messages,
                system_prompt=self.get_system_prompt(context),
                temperature=temperature,
                model_id=model_id
            )
            
            # Add response to memory
            self.memory.add_message('assistant', response)
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"Error: Failed to get LLM response. {str(e)}"
    
    def stream_message(self, user_query: str, temperature: float = 0.7):
        """
        Stream a message response from the LLM.
        
        Args:
            user_query: User's question/request
            temperature: Model temperature (0-1)
            
        Yields:
            Response chunks as they arrive
        """
        if self.provider is None:
            # Try to init again
            self._init_provider()
            
        if self.provider is None:
            logger.warning("No LLM provider available for streaming.")
            yield self.mock_chat_response(user_query)
            return

        # Reload provider settings in case they changed
        self._init_provider()
        
        # Add user message to memory
        self.memory.add_message('user', user_query)
        
        # Check if trimming is needed
        if self.memory.needs_trimming():
            logger.warning("Context window full. Trimming old messages...")
            self.memory.trim_if_needed()
        
        # Get messages for LLM
        messages = self.memory.get_messages()
        
        # Build Context
        safe_context_limit = int(self.memory.max_tokens * 0.6)
        context = self.select_relevant_context(user_query, max_tokens=safe_context_limit)
        
        # Stream from LLM
        full_response = ""
        try:
            settings = get_settings()
            model_id = get_active_model_id(settings.get_model_settings())
            
            for chunk in self.provider.stream_message(
                messages=messages,
                system_prompt=self.get_system_prompt(context),
                temperature=temperature,
                model_id=model_id
            ):
                full_response += chunk
                yield chunk
            
            # Add complete response to memory
            if full_response:
                self.memory.add_message('assistant', full_response)
            
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            yield f"\\nError: {str(e)}"
    
    def mock_chat_response(self, user_query: str) -> str:
        """
        Generate a mock response for testing without API keys.
        Simulates citation protocol and context awareness.
        
        Args:
            user_query: User's question
            
        Returns:
            Mock response with [[REF: path]] citations
        """
        # Find files mentioned in the query
        mentioned_files = []
        for path in self.context.files.keys():
            # Check if file path or basename is in query
            basename = path.split('/')[-1]
            if path.lower() in user_query.lower() or basename.lower() in user_query.lower():
                mentioned_files.append(path)
        
        # Build mock response
        response_parts = [
            f"[MOCK MODE] I analyzed your project with {len(self.context.files)} files.",
            f"Estimated context: ~{self.context.total_tokens:,} tokens.\\n"
        ]
        
        if mentioned_files:
            response_parts.append("Based on your query, here's what I found:\\n")
            for file_path in mentioned_files[:3]:  # Limit to 3 files
                response_parts.append(f"- The logic is in `{file_path}` [[REF: {file_path}]]")
        else:
            # Show a few sample files
            sample_files = list(self.context.files.keys())[:3]
            response_parts.append("Here are some key files in your project:\\n")
            for file_path in sample_files:
                response_parts.append(f"- `{file_path}` [[REF: {file_path}]]")
        
        response = "\\n".join(response_parts)
        
        # Update memory
        self.memory.add_message('user', user_query)
        self.memory.add_message('assistant', response)
        
        return response
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the current chat session.
        
        Returns:
            Dictionary with context info, memory stats, etc.
        """
        return {
            'pdf_path': self.pdf_path,
            'files_loaded': len(self.context.files),
            'provider': self.provider.__class__.__name__ if self.provider else 'Mock',
            'memory': self.memory.get_stats(),
        }
    
    def clear_history(self):
        """Clear conversation history while keeping context."""
        logger.info("Clearing conversation history")
        self.memory.clear()
