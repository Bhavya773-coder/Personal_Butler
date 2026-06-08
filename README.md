# JARVIS Core

A local-first Windows desktop AI assistant that can voice/text chat, browse the web, control your PC, and execute tasks — all running locally with no cloud dependencies.

## Features

- **Voice & Text Input** — Speak or type commands
- **Live Transcription** — See your words as you speak
- **Local LLM** — Powered by Ollama (llama3.2) running on your machine
- **Streaming Responses** — Watch the response generate in real-time
- **Text-to-Speech** — Jarvis speaks responses back to you
- **Browser Automation** — Search the web, open URLs, read pages via Playwright
- **PC Control** — Open apps, manage files, get system info
- **Interruption** — Stop Jarvis anytime with a button or Ctrl+Space
- **Permission System** — Dangerous actions require your explicit approval
- **Audit Logging** — Every action is logged to SQLite

## Prerequisites

1. **Python 3.11+** — [python.org](https://www.python.org/downloads/)
2. **Node.js 18+** — [nodejs.org](https://nodejs.org/)
3. **Ollama** — [ollama.com](https://ollama.com/)

## Quick Start

### 1. Install Ollama and pull the model

```bash
# Install Ollama from https://ollama.com
# Then pull the default model:
ollama pull llama3.2
```

### 2. Install Backend

```bash
cd scripts
install_backend.bat
```

This creates a Python virtual environment, installs all dependencies, and sets up Playwright.

### 3. Install Frontend

```bash
cd scripts
install_frontend.bat
```

### 4. Start Development

```bash
cd scripts
start_dev.bat
```

This starts:
- FastAPI backend on `http://localhost:8000`
- Electron + React frontend on `http://localhost:5173`

## Architecture

```
┌─────────────────────────────────────────────┐
│              Electron Desktop App           │
│  ┌──────────┐ ┌───────────┐ ┌───────────┐  │
│  │ Jarvis   │ │ Transcript│ │ Command   │  │
│  │   HUD    │ │   Panel   │ │   Input   │  │
│  └──────────┘ └───────────┘ └───────────┘  │
│         WebSocket (ws://localhost:8000)      │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              FastAPI Backend                │
│  ┌─────────────────────────────────────┐    │
│  │ Agent (Router → Planner → Tools)    │    │
│  ├─────────────────────────────────────┤    │
│  │ Tools: Browser │ FS │ PC │ SysInfo  │    │
│  ├─────────────────────────────────────┤    │
│  │ Security: Permissions │ Audit Log   │    │
│  └─────────────────────────────────────┘    │
│         │                 │                 │
│    Ollama API       Playwright Browser      │
│  (localhost:11434)    (Chromium)             │
└─────────────────────────────────────────────┘
```

## Project Structure

```
jarvis-core/
├── app/                          # Electron + React frontend
│   ├── electron/                 # Electron main & preload
│   ├── src/
│   │   ├── components/           # React UI components
│   │   ├── services/             # WebSocket, API, Audio
│   │   ├── App.tsx               # Main application
│   │   └── styles.css            # Futuristic dark theme
│   └── package.json
├── backend/                      # Python FastAPI backend
│   ├── agent/                    # LLM, routing, planning, memory
│   ├── tools/                    # Browser, filesystem, PC, system
│   ├── security/                 # Permissions, audit logging
│   ├── data/                     # SQLite database
│   └── main.py                   # FastAPI server
├── scripts/                      # Installation & startup scripts
│   ├── install_backend.bat
│   ├── install_frontend.bat
│   └── start_dev.bat
├── .env.example                  # Configuration template
└── README.md
```

## Configuration

Copy `.env.example` to `.env` and customize:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
BACKEND_PORT=8000
TTS_ENGINE=edge-tts
TTS_VOICE=en-US-GuyNeural
```

## MVP Commands

These commands work out of the box:

| Command | What it does |
|---------|-------------|
| "Open Chrome" | Launches Chromium browser |
| "Search Chrome for electric excavators in India" | Web search with results |
| "What is my CPU and RAM usage?" | Shows system stats |
| "Create a folder on Desktop called Jarvis Test" | Creates folder (with permission) |
| "Search my Downloads folder for PDF files" | Finds matching files |
| "Open Notepad" | Launches Notepad |
| "Stop" / Ctrl+Space | Interrupts current operation |
| Any chat message | Responds via Ollama LLM |

## Security Model

| Level | Actions | Behavior |
|-------|---------|----------|
| **SAFE** | System info, open apps, web search, read files | Executes immediately |
| **CONFIRM** | Create/copy/move files, screenshots, typing | Asks for permission |
| **DANGEROUS** | Delete files, shell commands, payments | Requires explicit approval with warning |

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Ollama is not running" | Start Ollama: `ollama serve` |
| "Model missing" | Pull the model: `ollama pull llama3.2` |
| "Microphone blocked" | Enable microphone in browser/system settings |
| "Browser automation failed" | Run: `playwright install chromium` |
| Backend won't start | Check Python venv: `backend\venv\Scripts\activate` |

## Tech Stack

- **Frontend**: Electron + React + TypeScript + Vite
- **Backend**: Python FastAPI + WebSockets
- **LLM**: Ollama (local)
- **Browser**: Playwright (Chromium)
- **TTS**: edge-tts / pyttsx3
- **STT**: Web Speech API
- **Database**: SQLite (aiosqlite)
- **PC Control**: pyautogui, psutil, pathlib

## License

MIT
