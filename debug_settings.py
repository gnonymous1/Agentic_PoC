from config.settings import get_settings
import os

print("--- ENV VARS ---")
print(f"LLM_API_KEY in env: {os.environ.get('LLM_API_KEY')}")
print(f"LLM_PROVIDER in env: {os.environ.get('LLM_PROVIDER')}")

print("\n--- LOADED SETTINGS ---")
try:
    settings = get_settings()
    print(f"Provider: {settings.llm.provider}")
    print(f"API Key (Generic): '{settings.llm.api_key}'")
    print(f"API Key (OpenRouter): '{settings.llm.openrouter_api_key}'")
    print(f"Base URL: '{settings.llm.base_url}'")
except Exception as e:
    print(f"Error loading settings: {e}")
