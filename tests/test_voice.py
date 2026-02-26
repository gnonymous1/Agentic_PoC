import sys
import os
from unittest.mock import MagicMock, patch
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock external libs BEFORE importing agent_io.voice
sys.modules['speech_recognition'] = MagicMock()
sys.modules['pyttsx3'] = MagicMock()
sys.modules['gtts'] = MagicMock()

from agent_io.voice import VoiceInput, VoiceOutput

class TestVoiceSystem(unittest.TestCase):
    def test_voice_output(self):
        print("\n>>> Testing Voice Output")
        vo = VoiceOutput(engine="pyttsx3")
        vo.speak("Hello Agent")
        # Verify engine.say was called
        vo.engine.say.assert_called_with("Hello Agent")
        vo.engine.runAndWait.assert_called_once()
        print("Voice Output: Verified (Mocked)")

    def test_voice_input(self):
        print("\n>>> Testing Voice Input")
        # We manually injected MagicMock into sys.modules['speech_recognition']
        # So we can just configure that mock directly
        import speech_recognition as sr
        
        mock_recognizer = MagicMock()
        sr.Recognizer.return_value = mock_recognizer
        sr.Microphone.return_value = MagicMock()
        
        # Mock successful recognition
        mock_recognizer.listen.return_value = "audio_data"
        mock_recognizer.recognize_google.return_value = "Test Command"
        
        vi = VoiceInput()
        text = vi.listen(timeout=1)
        
        print(f"Recognized Text: {text}")
        assert text == "Test Command"
        print("Voice Input: Verified (Mocked)")

if __name__ == "__main__":
    unittest.main()
