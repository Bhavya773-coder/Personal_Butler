import asyncio
import logging
import speech_recognition as sr

logger = logging.getLogger("jarvis.stt")

class SpeechRecognizerManager:
    def __init__(self, ws_broadcast_callback):
        self.ws_broadcast = ws_broadcast_callback
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.stop_listening_fn = None
        self.is_listening = False
        self.loop = None

    def start(self):
        if self.is_listening:
            return
        
        self.is_listening = True
        self.loop = asyncio.get_running_loop()
        
        try:
            # Open microphone briefly to adjust for ambient noise
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except Exception as e:
            logger.error(f"Error adjusting for ambient noise: {e}")

        # Start listening in background thread
        try:
            self.stop_listening_fn = self.recognizer.listen_in_background(
                self.microphone,
                self._audio_callback,
                phrase_time_limit=10
            )
            logger.info("Backend speech recognition listening in background...")
        except Exception as e:
            logger.error(f"Failed to start listening: {e}")
            self.is_listening = False
            asyncio.run_coroutine_threadsafe(
                self.ws_broadcast({"type": "stt_error", "message": f"Microphone error: {str(e)}"}),
                self.loop
            )

    def stop(self):
        if not self.is_listening:
            return
        
        self.is_listening = False
        if self.stop_listening_fn:
            try:
                self.stop_listening_fn(wait_for_stop=False)
            except Exception:
                pass
            self.stop_listening_fn = None
        logger.info("Backend speech recognition stopped")

    def _audio_callback(self, recognizer, audio):
        if not self.is_listening:
            return
        
        logger.info("Audio captured, sending for transcription...")
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._async_transcribe(audio), self.loop)

    async def _async_transcribe(self, audio):
        try:
            # Transcribe via Google's free Speech Web API in a threadpool to prevent blocking the event loop
            text = await asyncio.to_thread(self.recognizer.recognize_google, audio)
            text = text.strip()
            if text and self.is_listening:
                logger.info(f"Speech transcription final: '{text}'")
                await self.ws_broadcast({
                    "type": "transcription_final",
                    "text": text
                })
        except sr.UnknownValueError:
            logger.info("Speech recognition could not understand audio")
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            await self.ws_broadcast({
                "type": "stt_error",
                "message": "Speech recognition network/API error"
            })
        except Exception as e:
            logger.error(f"Error in transcription: {e}")
            await self.ws_broadcast({
                "type": "stt_error",
                "message": f"Transcription error: {str(e)}"
            })
