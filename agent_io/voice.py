import speech_recognition as sr
import pyttsx3
from gtts import gTTS
import os
import time
import threading

class VoiceOutput:
    def __init__(self, engine="pyttsx3"):
        self.engine_type = engine
        if engine == "pyttsx3":
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 160)
            self.engine.setProperty('volume', 1.0)
    
    def speak(self, text):
        print(f"[VoiceOutput] Speaking: {text}")
        if self.engine_type == "pyttsx3":
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            # gTTS implementation (online)
            tts = gTTS(text=text, lang='en')
            filename = "temp_speech.mp3"
            tts.save(filename)
            os.system(f"start {filename}")
            time.sleep(len(text) / 10) # Rough estimate wait

class VoiceInput:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
    def listen(self, timeout=5):
        """Listen for a single command"""
        print("[VoiceInput] Listening...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            try:
                audio = self.recognizer.listen(source, timeout=timeout)
                print("[VoiceInput] Processing audio...")
                text = self.recognizer.recognize_google(audio)
                print(f"[VoiceInput] Heard: {text}")
                return text
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                print("[VoiceInput] Could not understand audio")
                return None
            except sr.RequestError as e:
                print(f"[VoiceInput] Service error: {e}")
                return None

# Simple test if run directly
if __name__ == "__main__":
    vo = VoiceOutput()
    vi = VoiceInput()
    
    vo.speak("Voice system initialized. Say something.")
    text = vi.listen()
    if text:
        vo.speak(f"You said: {text}")
