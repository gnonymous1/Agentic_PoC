
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.llm import get_llm

class TestCortexLLM(unittest.TestCase):

    @patch('cortex.llm.get_settings')
    @patch('cortex.llm.ChatGoogleGenerativeAI')
    def test_google_provider(self, mock_google, mock_get_settings):
        # Setup settings
        mock_settings = MagicMock()
        mock_settings.llm.provider = "google"
        mock_settings.llm.model_name = "gemini-pro"
        mock_settings.llm.api_key = "google-key"
        mock_get_settings.return_value = mock_settings

        # Call get_llm
        get_llm(role="test", temperature=0.5)

        # Verify
        mock_google.assert_called_once_with(
            model="gemini-pro",
            temperature=0.5,
            google_api_key="google-key"
        )

    @patch('cortex.llm.get_settings')
    @patch('cortex.llm.ChatGroq')
    def test_groq_provider(self, mock_groq, mock_get_settings):
        # Setup settings
        mock_settings = MagicMock()
        mock_settings.llm.provider = "groq"
        mock_settings.llm.model_name = "llama3-70b"
        mock_settings.llm.api_key = "groq-key"
        mock_settings.llm.max_tokens = 1000
        mock_get_settings.return_value = mock_settings

        # Call get_llm
        get_llm(role="test", temperature=0.7)

        # Verify
        mock_groq.assert_called_once_with(
            model_name="llama3-70b",
            temperature=0.7,
            groq_api_key="groq-key",
            max_tokens=1000
        )

    @patch('cortex.llm.get_settings')
    @patch('cortex.llm.ChatOpenAI')
    def test_openrouter_provider(self, mock_openai, mock_get_settings):
        # Setup settings
        mock_settings = MagicMock()
        mock_settings.llm.provider = "openrouter"
        mock_settings.llm.model_name = "anthropic/claude-3-opus"
        mock_settings.llm.api_key = "default-key"
        mock_settings.llm.openrouter_api_key = "openrouter-key"
        mock_settings.llm.base_url = None # Should use default
        mock_settings.llm.max_tokens = 2000
        mock_get_settings.return_value = mock_settings

        # Call get_llm
        get_llm(role="test", temperature=0.1)

        # Verify
        mock_openai.assert_called_once_with(
            model="anthropic/claude-3-opus",
            temperature=0.1,
            api_key="openrouter-key",
            base_url="https://openrouter.ai/api/v1",
            max_tokens=2000
        )

    @patch('cortex.llm.get_settings')
    @patch('cortex.llm.ChatOpenAI')
    def test_ollama_provider(self, mock_openai, mock_get_settings):
        # Setup settings
        mock_settings = MagicMock()
        mock_settings.llm.provider = "ollama"
        mock_settings.llm.model_name = "llama3"
        mock_settings.llm.api_key = "ollama-key" # Usually ignored or dummy
        mock_settings.llm.base_url = None # Should use default
        mock_settings.llm.max_tokens = 4096
        mock_get_settings.return_value = mock_settings

        # Call get_llm
        get_llm(role="test", temperature=0.0)

        # Verify
        mock_openai.assert_called_once_with(
            model="llama3",
            temperature=0.0,
            api_key="ollama-key",
            base_url="http://localhost:11434/v1",
            max_tokens=4096
        )

    @patch('cortex.llm.get_settings')
    @patch('cortex.llm.ChatOpenAI')
    def test_lm_studio_provider(self, mock_openai, mock_get_settings):
        # Setup settings
        mock_settings = MagicMock()
        mock_settings.llm.provider = "lm_studio"
        mock_settings.llm.model_name = "local-model"
        mock_settings.llm.api_key = "lm-key"
        mock_settings.llm.base_url = "http://custom-host:1234/v1" # Custom base_url
        mock_settings.llm.max_tokens = 512
        mock_get_settings.return_value = mock_settings

        # Call get_llm
        get_llm(role="test", temperature=0.5)

        # Verify
        mock_openai.assert_called_once_with(
            model="local-model",
            temperature=0.5,
            api_key="lm-key",
            base_url="http://custom-host:1234/v1",
            max_tokens=512
        )

if __name__ == '__main__':
    unittest.main()
