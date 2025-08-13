# Voice Training App
A real-time voice and articulation training application that provides instant feedback on pronunciation, pace, and speech clarity using AI-powered assessment.

## 🚀 Features
- **Real-time Speech Recognition**: Live transcription using Whisper.cpp
- **Instant Feedback**: Phoneme-level accuracy scoring and pace analysis
- **AI-Powered Coaching**: Personalized training plans using GPT-4 or Gemini
- **Progress Tracking**: Visual analytics and streak monitoring
- **Text-to-Speech**: Audio playback of training exercises
- **Cross-platform UI**: Native macOS interface with PySide6

## 📋 Prerequisites
- **macOS** (tested on macOS 14+)
- **Python 3.12+**
- **Homebrew** (for audio dependencies)
- **API Keys**: OpenAI or Google Gemini for LLM features

## 🛠️ Installation

### Quick Install (macOS)
```bash
# Clone the repository
git clone <repository-url>
cd voice_training_app

# Run the automated installer
chmod +x install_voicecoach.sh
./install_voicecoach.sh

# Activate the virtual environment
pyenv activate voicecoach
```

### Manual Installation
1. **Install system dependencies:**
   ```bash
   brew install portaudio ffmpeg espeak-ng cmake pkg-config duckdb
   ```

2. **Set up Python environment:**
   ```bash
   brew install pyenv
   pyenv install 3.12.2
   pyenv virtualenv 3.12.2 voicecoach
   export PYENV_VERSION=voicecoach
   ```

3. **Install Python packages:**
   ```bash
   pip install --upgrade pip wheel setuptools
   pip install -r requirements.txt
   ```

4. **Download AI models:**
   ```bash
   # Whisper.cpp for speech recognition
   git clone --depth 1 https://github.com/ggml-org/whisper.cpp
   cd whisper.cpp && make METAL=1 && \
     ./models/download-ggml-model.sh tiny.en.int8 && cd ..
   
   # Piper TTS voice
   mkdir -p models/piper && cd models/piper
   curl -L -o amy-medium.tar.gz https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/amy/medium/en_US-amy-medium.tar.gz
   tar -xf amy-medium.tar.gz && cd ../..
   ```

## ⚙️ Configuration

### API Keys Setup
This application supports both OpenAI and Google Gemini for LLM-powered features:

1. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your API keys:**
   ```bash
   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_ORG_ID=your_openai_org_id_here  # Optional
   
   # Google Gemini Configuration  
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. **Configure the provider in config.yaml:**
   ```yaml
   llm:
     provider: "openai" # or "gemini"
     model: "gpt-4o" # or "gemini-1.5-pro-latest"
   ```

### Getting API Keys
- • OpenAI: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- • Google Gemini: Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

## 🎯 Usage

### Starting the Application
```bash
# Activate the virtual environment
pyenv activate voicecoach

# Run the application
python main.py
```

## 🎪 Practice modes and session flow

The voice training app provides structured practice sessions with three core modes:

### Free Practice Mode
- Continuous speech recognition with real-time feedback
- Live WPM (words per minute) and accuracy scoring
- No time limits or structured exercises
- Best for warm-up and general assessment

### Guided Training Mode
- AI-generated 4-week training plans with daily exercises
- Phoneme-specific drills based on assessment results
- Progress tracking with streak monitoring
- Personalized difficulty adjustment based on performance

### Session Flow
1. **Audio calibration**: System tests microphone input levels
2. **Warm-up assessment**: 30-second free speech sample for baseline metrics
3. **Mode selection**: Choose between free practice or guided training
4. **Active training**: Real-time transcription with immediate phoneme and pace feedback
5. **Session summary**: Performance analytics and improvement recommendations
6. **Progress sync**: Results saved to local database with trend analysis

### How It Works
1. Speech Input: The app continuously listens to your microphone
2. Real-time Transcription: Whisper.cpp transcribes your speech in real-time
3. Assessment: Your pronunciation is analyzed for:
   ◦ Phoneme accuracy
   ◦ Word Error Rate (WER)
   ◦ Speaking pace (WPM)
4. AI Feedback: GPT-4/Gemini generates personalized training plans
5. Progress Tracking: Visual analytics show your improvement over time

### Training Features
• Live Metrics: Real-time WPM and accuracy display
• Personalized Plans: AI-generated 4-week training programs
• Audio Playback: Listen to training exercises with TTS
• Progress Analytics: Sparklines and trend analysis
• Streak Tracking: Daily practice motivation

## 🏗️ Architecture

```
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
```

## 📊 Configuration Options
The config.yaml file allows customization of:
• LLM Provider: Switch between OpenAI and Gemini
• Audio Settings: Frame rate, VAD threshold
• STT Model: Whisper.cpp model selection
• TTS Engine: Piper or Coqui TTS
• UI Theme: System auto-dark/light
• Database: SQLite with DuckDB analytics

## 🧪 Testing
Run the test suite:
```bash
python -m pytest tests/
```

## 📝 Logging
Application logs are stored in logs/app.log with detailed function call tracking for debugging.

## 🤝 Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Troubleshooting

### Common Issues
Audio not working:
• Ensure PortAudio is installed: `brew install portaudio`
• Check microphone permissions in System Preferences

Whisper model not found:
• Run the model download script in whisper.cpp/
• Verify the model path in config.yaml

API errors:
• Check your API keys in .env
• Verify internet connectivity
• Ensure sufficient API credits

UI not launching:
• Activate the virtual environment: `pyenv activate voicecoach`
• Install PySide6: `pip install pyside6`

### Getting Help
• Check the logs in logs/app.log
• Review the configuration in config.yaml
• Ensure all dependencies are installed correctly
