"""
User Settings - Global preferences for Vibecode GUI.
Stored at ~/.vibecode/settings.json
"""
import os
import json
from pathlib import Path
from typing import Optional

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    print("Warning: keyring not installed. API keys will not be securely stored.")


class UserSettings:
    """
    Manages global user preferences.
    Persisted to ~/.vibecode/settings.json
    """
    
    DEFAULTS = {
        'theme': 'dark',  # 'dark' or 'light'
        'recent_limit': 5,
        'recent_projects': [],  # List of paths, most recent first
        'window_geometry': None,  # Save window size/position
        'chat_provider': 'google',  # Default LLM provider for VibeChat
        'chat_temperature': 0.7,  # Default temperature for chat
        'chat_max_tokens': 128000,  # Default max context tokens
        'selected_model_key': '',  # Model selected from dropdown (ECR #005)
        'custom_model_string': '',  # Custom model ID override (ECR #005)
    }
    
    def __init__(self):
        self.config_dir = Path.home() / '.vibecode'
        self.settings_path = self.config_dir / 'settings.json'
        self.data = self.DEFAULTS.copy()
        self._ensure_config_dir()
        self.load()
    
    def _ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load(self):
        if not self.settings_path.exists():
            return
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                self.data.update(loaded)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load settings: {e}")
    
    def save(self):
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    # --- Theme ---
    @property
    def theme(self) -> str:
        return self.data.get('theme', 'dark')
    
    @theme.setter
    def theme(self, value: str):
        self.data['theme'] = value
        self.save()
    
    # --- Recent Projects ---
    def add_recent_project(self, path: str):
        """Add a project to recent list (most recent first)."""
        path = os.path.normpath(os.path.abspath(path))
        recent = self.data.get('recent_projects', [])
        
        # Remove if exists (to move to front)
        if path in recent:
            recent.remove(path)
        
        # Add to front
        recent.insert(0, path)
        
        # Enforce limit
        limit = self.data.get('recent_limit', 5)
        self.data['recent_projects'] = recent[:limit]
        self.save()
    
    def get_recent_projects(self) -> list:
        """Get recent project paths."""
        return self.data.get('recent_projects', [])
    
    def clear_recent(self):
        """Clear recent projects list."""
        self.data['recent_projects'] = []
        self.save()
    
    # --- Window Geometry ---
    def save_geometry(self, x: int, y: int, width: int, height: int):
        self.data['window_geometry'] = {'x': x, 'y': y, 'w': width, 'h': height}
        self.save()
    
    def get_geometry(self) -> Optional[dict]:
        return self.data.get('window_geometry')
    
    # --- Chat Settings ---
    @property
    def chat_provider(self) -> str:
        """Get the default chat provider."""
        return self.data.get('chat_provider', 'google')
    
    @chat_provider.setter
    def chat_provider(self, value: str):
        """Set the default chat provider."""
        valid_providers = ['google', 'openai', 'anthropic', 'ollama', 'custom']
        if value.lower() not in valid_providers:
            raise ValueError(f"Invalid provider. Must be one of: {valid_providers}")
        self.data['chat_provider'] = value.lower()
        self.save()
    
    @property
    def chat_temperature(self) -> float:
        """Get the default chat temperature."""
        return self.data.get('chat_temperature', 0.7)
    
    @chat_temperature.setter
    def chat_temperature(self, value: float):
        """Set the default chat temperature."""
        self.data['chat_temperature'] = max(0.0, min(1.0, value))
        self.save()
    
    @property
    def chat_max_tokens(self) -> int:
        """Get the default max tokens for chat context."""
        return self.data.get('chat_max_tokens', 128000)
    
    @chat_max_tokens.setter
    def chat_max_tokens(self, value: int):
        """Set the default max tokens for chat context."""
        self.data['chat_max_tokens'] = max(1000, value)
        self.save()
    
    @property
    def custom_base_url(self) -> str:
        """Get the custom base URL for API endpoints."""
        return self.data.get('custom_base_url', '')
    
    @custom_base_url.setter
    def custom_base_url(self, value: str):
        """Set the custom base URL for API endpoints."""
        self.data['custom_base_url'] = value
        self.save()
    
    # --- Model Selection (ECR #005) ---
    @property
    def selected_model_key(self) -> str:
        """Get the currently selected model key from dropdown."""
        return self.data.get('selected_model_key', '')
    
    @selected_model_key.setter
    def selected_model_key(self, value: str):
        """Set the selected model key."""
        self.data['selected_model_key'] = value
        self.save()
    
    @property
    def custom_model_string(self) -> str:
        """Get the custom model string override."""
        return self.data.get('custom_model_string', '')
    
    @custom_model_string.setter
    def custom_model_string(self, value: str):
        """Set the custom model string override."""
        self.data['custom_model_string'] = value
        self.save()


    
    def get_model_settings(self) -> dict:
        """Get model settings dict for config.get_active_model_id()."""
        return {
            'selected_model_key': self.selected_model_key,
            'custom_model_string': self.custom_model_string,
            'custom_base_url': self.custom_base_url,
        }
    
    # --- API Key Management (Secure Storage via Keyring) ---
    def set_api_key(self, provider: str, api_key: str) -> bool:
        """
        Securely store an API key for a provider using keyring.
        
        Args:
            provider: Provider name (e.g., 'google', 'openai', 'anthropic')
            api_key: The API key to store
            
        Returns:
            True if successful, False otherwise
        """
        if not KEYRING_AVAILABLE:
            print("Warning: keyring not available. Install with: pip install keyring")
            return False
        
        try:
            service_name = f"vibecode_chat_{provider.lower()}"
            keyring.set_password(service_name, "api_key", api_key)
            return True
        except Exception as e:
            print(f"Error storing API key: {e}")
            return False
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Retrieve API key for a provider from keyring.
        
        Args:
            provider: Provider name (e.g., 'google', 'openai', 'anthropic')
            
        Returns:
            API key if found, None otherwise
        """
        if not KEYRING_AVAILABLE:
            return None
        
        try:
            service_name = f"vibecode_chat_{provider.lower()}"
            return keyring.get_password(service_name, "api_key")
        except Exception as e:
            print(f"Error retrieving API key: {e}")
            return None
    
    def delete_api_key(self, provider: str) -> bool:
        """
        Delete stored API key for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            True if successful, False otherwise
        """
        if not KEYRING_AVAILABLE:
            return False
        
        try:
            service_name = f"vibecode_chat_{provider.lower()}"
            keyring.delete_password(service_name, "api_key")
            return True
        except keyring.errors.PasswordDeleteError:
            # Key doesn't exist, that's fine
            return True
        except Exception as e:
            print(f"Error deleting API key: {e}")
            return False


# Singleton
_settings: Optional[UserSettings] = None

def get_settings() -> UserSettings:
    global _settings
    if _settings is None:
        _settings = UserSettings()
    return _settings
