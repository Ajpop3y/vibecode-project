"""
Configuration management for VibeCode.
"""
import yaml
from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Optional


# --- AI MODEL CONFIGURATION (ECR #005) ---

# Default fallback model (used when settings are empty)
DEFAULT_MODEL_ID = "gemini-flash-latest"

# Registry of "Known Good" models for the UI Dropdown
# Format: [(Display Name, API Model String), ...]
KNOWN_MODELS = [
    ("Gemini Flash Latest (Recommended)", "gemini-flash-latest"),
    ("Gemini 2.0 Flash (Preview)", "gemini-2.0-flash"),
    ("Gemini 2.0 Flash Lite", "gemini-2.0-flash-lite"),
    ("Gemini 1.5 Pro (Reasoning)", "gemini-1.5-pro"),
    ("Gemini 1.5 Flash", "gemini-1.5-flash"),
    ("Gemini 3 Pro (Preview)", "gemini-3-pro-preview"),
    ("Gemini 3 Flash (Preview)", "gemini-3-flash-preview"),
    # ("GPT-4o (OpenAI)", "gpt-4o"),
    # ("GPT-4o Mini (OpenAI)", "gpt-4o-mini"),
    # ("Claude 3.5 Sonnet (Anthropic)", "claude-3-5-sonnet-20241022"),
    # ("Llama 3.2 (Local/Ollama)", "llama3.2"),
]



CUSTOM_PROVIDER_PRESETS = {
    "NVIDIA": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model_hint": "meta/llama-3.1-70b-instruct",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model_hint": "openai/gpt-4o-mini",
    },
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model_hint": "llama3-70b-8192",
    },
    "Together": {
        "base_url": "https://api.together.xyz/v1",
        "model_hint": "meta-llama/Llama-3-70b-chat-hf",
    },
    "Local": {
        "base_url": "http://localhost:8000/v1",
        "model_hint": "local-model",
    },
}

def get_active_model_id(user_settings: Optional[Dict] = None) -> str:
    """
    Retrieves the active model ID, prioritizing:
    1. User Custom Input (for power users / experimental models)
    2. User Selection from dropdown
    3. System Default
    
    Args:
        user_settings: Dict with 'custom_model_string' and 'selected_model_key'
        
    Returns:
        Model ID string to pass to LLM provider
    """
    if user_settings is None:
        return DEFAULT_MODEL_ID
    
    # Priority 1: Custom string if present
    custom = user_settings.get("custom_model_string", "").strip()
    if custom:
        return custom
    
    # Priority 2: Selected from dropdown
    selected = user_settings.get("selected_model_key", "").strip()
    if selected and selected != "custom":
        return selected
    
    # Priority 3: Default fallback
    return DEFAULT_MODEL_ID


class OutputConfig(BaseModel):
    """Configuration for output file settings."""
    human_pdf: str = "snapshot_human.pdf"
    llm_pdf: str = "snapshot_llm.pdf"
    pygments_style: str = "monokai"


class ProjectConfig(BaseModel):
    """
    Main project configuration model.
    Validates and provides defaults for all .vibecode.yaml settings.
    """
    project_name: str = "Unnamed Project"
    files: List[str] = Field(default_factory=list)
    autodiscover_py: bool = False
    autodiscover_ext: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    # Extensions to include during Smart Scan
    included_extensions: List[str] = Field(default_factory=lambda: [
        '.py', '.md', '.yaml', '.yml', '.json', '.js', '.ts',
        '.jsx', '.tsx', '.cpp', '.c', '.h', '.hpp', '.cs',
        '.java', '.go', '.rs', '.rb', '.php', '.swift', '.kt',
        '.css', '.scss', '.sass', '.html', '.xml', '.sql',
        '.txt', '.toml', '.ini', '.cfg', '.sh', '.bat', '.ps1'
    ])
    output: OutputConfig = Field(default_factory=OutputConfig)
    version: float = 1.0


def load_config(config_path: str) -> ProjectConfig:
    """
    Loads and validates the .vibecode.yaml file.
    Uses yaml.safe_load() to prevent RCE.
    Pydantic provides automatic type coercion and clear error messages.
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            # Use safe_load() for security
            data = yaml.safe_load(f)
            
            # Handle empty file
            if data is None:
                data = {}
            
            # Pydantic validates and provides defaults
            return ProjectConfig.model_validate(data)

    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found at {config_path}")
    except yaml.YAMLError as exc:
        raise ValueError(f"Error parsing YAML file: {exc}")
    except ValidationError as e:
        # Pydantic provides detailed error messages
        errors = []
        for err in e.errors():
            loc = '.'.join(str(x) for x in err['loc'])
            msg = err['msg']
            errors.append(f"  - {loc}: {msg}")
        error_details = '\n'.join(errors)
        raise ValueError(f"Config validation failed:\n{error_details}")