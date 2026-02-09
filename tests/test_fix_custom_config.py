
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from vibecode.ai import select_relevant_files

class TestCustomConfig(unittest.TestCase):
    

    def setUp(self):
        self.mock_settings_patcher = patch('vibecode.settings.get_settings')
        self.mock_get_settings = self.mock_settings_patcher.start()

        self.mock_settings = MagicMock()
        self.mock_get_settings.return_value = self.mock_settings
        
        self.mock_openai_patcher = patch('openai.OpenAI')
        self.mock_openai = self.mock_openai_patcher.start()
        
        # Default mock behavior
        self.mock_client = MagicMock()
        self.mock_openai.return_value = self.mock_client
        self.mock_client.chat.completions.create.return_value.choices[0].message.content = '["file1.py"]'

    def tearDown(self):
        self.mock_settings_patcher.stop()
        self.mock_openai_patcher.stop()

    def test_custom_provider_with_base_url(self):
        """Test custom provider with valid base URL passes it to OpenAI client."""
        self.mock_settings.chat_provider = 'custom'
        self.mock_settings.custom_base_url = 'https://my-custom.ai/v1'
        self.mock_settings.get_api_key.return_value = 'sk-custom'
        
        select_relevant_files(['file1.py'], 'intent')
        
        # Verify OpenAI init arguments
        self.mock_openai.assert_called_with(api_key='sk-custom', base_url='https://my-custom.ai/v1')

    def test_custom_provider_missing_base_url(self):
        """Test custom provider without base URL raises ValueError."""
        self.mock_settings.chat_provider = 'custom'
        self.mock_settings.custom_base_url = ''
        self.mock_settings.get_api_key.return_value = 'sk-custom'
        
        with self.assertRaisesRegex(ValueError, "Custom provider requires a Base URL"):
            select_relevant_files(['file1.py'], 'intent')

    def test_openai_provider_ignores_base_url(self):
        """Test openai provider forces base_url to None even if setting exists."""
        self.mock_settings.chat_provider = 'openai'
        self.mock_settings.custom_base_url = 'https://malicious.site/v1' # Should be ignored
        self.mock_settings.get_api_key.return_value = 'sk-openai'
        
        select_relevant_files(['file1.py'], 'intent')
        
        # Verify OpenAI init arguments - base_url MUST be None
        self.mock_openai.assert_called_with(api_key='sk-openai', base_url=None)

if __name__ == '__main__':
    unittest.main()
