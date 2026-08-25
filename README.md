# ZENITH — Personal J.A.R.V.I.S. AI

A full-stack personal AI assistant: **cloud brain**, **laptop agent** with 265+ tools,
and a **Flutter phone app** with always-on "ZENITH" wake word, voice commands, and
native phone-tool execution.

## Architecture

```
┌──────────────────── RENDER.COM (free tier) ────────────────────┐
│  CLOUD BRAIN (FastAPI)                                          │
│  • Groq LLM routing (gpt-oss-120b)                              │
│  • Tool registry: PHONE / LAPTOP classes                        │
│  • Device presence + confirmation flow                          │
└──────────────▲─────────────────────────▲───────────────────────┘
               │ WebSocket               │ WebSocket (outbound)
┌──────────────┴───────────┐   ┌─────────┴─────────────────────┐
│ ANDROID APP (Flutter)    │   │ LAPTOP DAEMON                  │
│ • Porcupine wake word    │   │ • Executes 265+ Zenith tools   │
│ • Speech-to-text         │   │ • Auto-reconnect w/ backoff    │
│ • Native phone tools     │   │ • Heartbeat/status             │
│ • TTS voice replies      │   └────────────────────────────────┘
└──────────────────────────┘
```

## Signature Flow

Ask for anything laptop-based from your phone while away:

> You: "check my disk health"
> ZENITH: "Laptop based tool. 📊 Laptop is ONLINE. Should I perform it?"
> You: "yes"
> ZENITH: *(runs the real tool and returns results)*

If the laptop is asleep/offline, ZENITH says so honestly instead of faking it.

## Repo Layout

| Path | Purpose |
|---|---|
| `agent.py` | LiveKit voice agent, 265+ registered tools |
| `Tools/` | All tool modules (health, protocols, comms, media…) |
| `cloud/main.py` | Cloud Brain FastAPI service |
| `cloud/registry.py` | Phone/laptop tool classification |
| `cloud/laptop_client.py` | Laptop-side daemon |
| `mobile_app/` | Flutter app (wake word, mic, dashboard) |

## Deploy the Cloud Brain (Render)

1. Push this repo, then on [render.com](https://render.com): **New → Blueprint**
2. When prompted set:
   - `GROQ_API_KEY` — your Groq key
   - `BRIDGE_PIN` — any PIN pairing laptop/app to your brain
3. Note your URL: `https://<service>.onrender.com`

## Run the Laptop Daemon

```powershell
$env:ZENITH_CLOUD_URL = "wss://<service>.onrender.com/ws"
$env:BRIDGE_PIN = "<your PIN>"
python cloud/laptop_client.py
```

## Mobile App

```powershell
cd mobile_app
flutter pub get
flutter build apk --debug
# install build/app/outputs/flutter-apk/app-debug.apk
```
Set the cloud URL + PIN in the in-app Settings screen.

## Security

- **No secrets are committed.** All keys load from environment variables.
- The repo's `.gitignore` blocks `.env`, keystores, and credentials.
- Cloud ↔ devices trust is established via the shared `BRIDGE_PIN`.

## Status

Phases A–B (cloud brain + daemon) built and verified E2E.
Wake word, TTS replies, expanded phone tools: in progress.
