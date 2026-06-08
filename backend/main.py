"""
JARVIS Core — FastAPI Backend Server

Main entry point for the backend. Provides REST API + WebSocket for the Electron frontend.
Handles streaming LLM responses, tool execution, permissions, and logging.
"""

import asyncio
import json
import logging
import os
import uuid
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables
env_path = Path(__file__).parent.parent / ".env.example"
if (Path(__file__).parent.parent / ".env").exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from agent.ollama_client import check_ollama_status
from agent.planner import planner
from agent.memory import memory
from security.audit_log import audit_log
from security.permissions import permission_engine
from tools.system_info import get_system_info, get_summary

# ── Logging ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis.server")


# ── App Lifecycle ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("🚀 JARVIS Core backend starting...")
    await audit_log.initialize()
    session_id = str(uuid.uuid4())[:8]
    memory.set_session(session_id)
    planner.session_id = session_id
    logger.info(f"Session: {session_id}")

    # Check Ollama status
    status = await check_ollama_status()
    if not status["running"]:
        logger.warning(f"⚠️  {status['error']}")
    elif not status["model_available"]:
        logger.warning(f"⚠️  {status['error']}")
    else:
        logger.info("✅ Ollama connected and model ready.")

    yield

    logger.info("Shutting down JARVIS Core...")
    await audit_log.close()


# ── FastAPI App ────────────────────────────────────────────────────────

app = FastAPI(
    title="JARVIS Core",
    description="Local AI Desktop Assistant Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ───────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class TaskRequest(BaseModel):
    message: str
    session_id: str | None = None

class PermissionResponse(BaseModel):
    request_id: str
    approved: bool


# ── WebSocket Connection Manager ──────────────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections to frontend clients."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send a message to all connected clients."""
        msg_text = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_text)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


ws_manager = ConnectionManager()


# ── Set up planner's WS callback ──────────────────────────────────────

async def ws_broadcast(data: dict):
    """Callback for the planner to send events to frontend."""
    await ws_manager.broadcast(data)

planner.set_ws_callback(ws_broadcast)


# ── TTS Engine ─────────────────────────────────────────────────────────

_tts_task: asyncio.Task | None = None
_tts_stop = False


async def speak_text(text: str):
    """Speak text using configured TTS engine. Runs in background."""
    global _tts_stop
    _tts_stop = False

    engine = os.getenv("TTS_ENGINE", "edge-tts")

    # Split into sentences for interruptible TTS
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    for sentence in sentences:
        if _tts_stop:
            break

        await ws_manager.broadcast({"type": "tts_sentence_started", "text": sentence})

        try:
            if engine == "edge-tts":
                await _speak_edge_tts(sentence)
            else:
                await _speak_pyttsx3(sentence)
        except Exception as e:
            logger.error(f"TTS error: {e}")

        await ws_manager.broadcast({"type": "tts_sentence_done", "text": sentence})


async def _speak_edge_tts(text: str):
    """Speak using Microsoft Edge TTS (free, high quality)."""
    try:
        import edge_tts
        import tempfile
        import subprocess as _sp

        voice = os.getenv("TTS_VOICE", "en-US-GuyNeural")
        communicate = edge_tts.Communicate(text, voice)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        await communicate.save(tmp_path)

        # Play audio using ffplay or powershell Media.SoundPlayer
        if not _tts_stop:
            # Try ffplay first (handles mp3), fall back to powershell start
            try:
                proc = await asyncio.create_subprocess_exec(
                    "powershell", "-c",
                    f'Add-Type -AssemblyName PresentationCore; '
                    f'$p = New-Object System.Windows.Media.MediaPlayer; '
                    f'$p.Open([uri]"{tmp_path}"); $p.Play(); '
                    f'Start-Sleep -Milliseconds ([int]($p.NaturalDuration.TimeSpan.TotalMilliseconds + 500))',
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
            except Exception:
                # Last resort: open with default player
                pass

        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    except ImportError:
        logger.warning("edge-tts not installed, falling back to pyttsx3")
        await _speak_pyttsx3(text)


async def _speak_pyttsx3(text: str):
    """Speak using pyttsx3 (Windows SAPI)."""
    try:
        import pyttsx3

        def _speak_sync():
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.setProperty("volume", 0.9)
            engine.say(text)
            engine.runAndWait()
            engine.stop()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _speak_sync)
    except Exception as e:
        logger.error(f"pyttsx3 error: {e}")


def stop_tts():
    """Stop current TTS playback."""
    global _tts_stop, _tts_task
    _tts_stop = True
    if _tts_task and not _tts_task.done():
        _tts_task.cancel()


# ── REST Endpoints ─────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    ollama = await check_ollama_status()
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "ollama": ollama,
        "ws_clients": len(ws_manager.active_connections),
    }


@app.get("/sysinfo")
async def sys_info():
    """Get system information."""
    return get_system_info()


@app.post("/chat")
async def chat(request: ChatRequest):
    """Handle a chat message (non-streaming, use WS for streaming)."""
    try:
        response = await planner.handle_message(request.message)

        # Start TTS in background
        global _tts_task
        _tts_task = asyncio.create_task(speak_text(response))

        return {"response": response, "session_id": planner.session_id}
    except Exception as e:
        logger.error(f"Chat error: {traceback.format_exc()}")
        return {"error": str(e)}


@app.post("/task")
async def task(request: TaskRequest):
    """Handle a task request."""
    try:
        response = await planner.handle_message(request.message)

        global _tts_task
        _tts_task = asyncio.create_task(speak_text(response))

        return {"response": response, "session_id": planner.session_id}
    except Exception as e:
        logger.error(f"Task error: {traceback.format_exc()}")
        return {"error": str(e)}


@app.post("/interrupt")
async def interrupt():
    """Interrupt the current operation."""
    planner.interrupt()
    stop_tts()
    permission_engine.deny_all()

    await ws_manager.broadcast({
        "type": "interrupted",
        "message": "Stopped.",
    })

    await audit_log.log_action(planner.session_id, "interrupt", "user_interrupt", status="completed")
    return {"status": "interrupted", "message": "Stopped."}


@app.post("/permission/approve")
async def permission_approve(request: PermissionResponse):
    """Approve a pending permission request."""
    success = permission_engine.resolve(request.request_id, approved=True)
    if success:
        await audit_log.log_permission(
            planner.session_id, request.request_id,
            "approved", "confirm", "User approved"
        )
    return {"success": success}


@app.post("/permission/deny")
async def permission_deny(request: PermissionResponse):
    """Deny a pending permission request."""
    success = permission_engine.resolve(request.request_id, approved=False)
    if success:
        await audit_log.log_permission(
            planner.session_id, request.request_id,
            "denied", "confirm", "User denied"
        )
    return {"success": success}


@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get recent logs."""
    logs = await audit_log.get_logs(limit=limit)
    return {"logs": logs}


# ── WebSocket Endpoint ─────────────────────────────────────────────────

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time communication.
    
    Receives messages from frontend:
      { "type": "chat", "message": "..." }
      { "type": "task", "message": "..." }
      { "type": "interrupt" }
      { "type": "permission_response", "request_id": "...", "approved": true/false }
    
    Sends events to frontend:
      transcription_partial, transcription_final, llm_token,
      tts_sentence_started, tts_sentence_done,
      tool_started, tool_progress, tool_done,
      permission_required, interrupted, error, final
    """
    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "chat" or msg_type == "task":
                    message = msg.get("message", "").strip()
                    if message:
                        # Process in background so we can keep receiving messages
                        asyncio.create_task(_handle_ws_message(message))

                elif msg_type == "interrupt":
                    planner.interrupt()
                    stop_tts()
                    permission_engine.deny_all()
                    await ws_manager.broadcast({"type": "interrupted", "message": "Stopped."})

                elif msg_type == "permission_response":
                    req_id = msg.get("request_id", "")
                    approved = msg.get("approved", False)
                    permission_engine.resolve(req_id, approved)

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


async def _handle_ws_message(message: str):
    """Handle a message received via WebSocket."""
    try:
        await ws_manager.broadcast({"type": "thinking", "message": "Processing..."})
        response = await planner.handle_message(message)

        # Start TTS
        global _tts_task
        _tts_task = asyncio.create_task(speak_text(response))

    except Exception as e:
        logger.error(f"WS message handling error: {traceback.format_exc()}")
        await ws_manager.broadcast({"type": "error", "message": str(e)})


# ── Entry Point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
