# voice_training_app
voice and articulation training app

## Configuration

### API Keys Setup

This application supports both OpenAI and Google Gemini for LLM-powered features. To configure your API keys:

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your API keys:**
   ```bash
   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_ORG_ID=your_openai_org_id_here  # Optional
   
   # Google Gemini Configuration  
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. **Configure the provider in `config.yaml`:**
   ```yaml
   llm:
     provider: "openai"  # or "gemini"
     model: "gpt-4o"     # or "gemini-1.5-pro-latest"
   ```

### Getting API Keys

- **OpenAI**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Google Gemini**: Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

### Application  flow
┌────────────────────────────────────────────────────────────┐
│                       main.py (Async Orchestrator)        │
└───────────────▲───────────────────────────────▲────────────┘
                │                               │
   mic frames   │                               │   TTS wav
                │                               │
┌───────────────┴──────────────┐   text/plan ┌──┴────────────────┐
│       audio_io.py            │────────────►│  ui.py (Coach)    │
│  • PortAudio stream          │             │  • PyObjC/PySide  │
│  • VAD & 30 ms framing       │             │  • Live WPM gauge │
│  • Whisper.cpp worker pool   │             │  • Feedback view  │
│  • Piper/Coqui TTS daemon    │◄────────────│  • Menu‑bar icon  │
└───────────────┬──────────────┘    events    └──┬───────────────┘
                │                               │
         transcript JSON                        │
                │                               │
┌───────────────▼──────────────┐   scores   ┌───▼────────────────┐
│    assessment.py             │──────────►│ planner.py         │
│  • Phonemizer phoneme diff   │            │  • 4‑week plan     │
│  • JiWER WER + pace metrics  │            │  • spaced‑rep algo │
└──────────────────────────────┘            └────────────────────┘
                        ▲
                        │ prompt+rubric
                        │
            ┌───────────┴────────────┐
            │  prompt_engine.py      │
            │  • GPT‑4o / Gemini     │
            │  • Retry & cost guard  │
            └────────────────────────┘
