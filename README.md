# Voice Training App

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/) [![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/) [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Overview

Voice Training App is a real-time voice and articulation training application that provides instant feedback on pronunciation, pace, and speech clarity using AI-powered assessment. The application combines advanced speech recognition with personalized coaching to help users improve their speaking skills through structured practice sessions.

## Features

- **Real-time Speech Recognition**: Live transcription using Whisper.cpp
- **Instant Feedback**: Phoneme-level accuracy scoring and pace analysis
- **AI-Powered Coaching**: Personalized training plans using GPT-4 or Gemini
- **Progress Tracking**: Visual analytics and streak monitoring
- **Text-to-Speech**: Audio playback of training exercises
- **Cross-platform UI**: Native macOS interface with PySide6
- **Multiple Practice Modes**: Free practice and guided training sessions
- **Session Analytics**: Real-time WPM and accuracy metrics

## Quick Start

### Using dev.sh (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd voice_training_app

# Make dev manager executable and start both services
chmod +x dev.sh
./dev.sh start
```

The `dev.sh` manager will:
1. Start the backend (FastAPI at http://localhost:8000)
2. Start the frontend (Vite/React at http://localhost:3000)
3. Write logs to `logs/backend.log` and `logs/frontend.log`

### Manual Quick Start

```bash
# Backend
source venv/bin/activate
cd backend && python main.py

# Frontend (in a new terminal)
cd frontend && npm run dev
```

## Installation

### Prerequisites

- **macOS** (tested on macOS 14+)
- **Python 3.12+**
- **Homebrew** (for audio dependencies)
- **API Keys**: OpenAI or Google Gemini for LLM features

### macOS Installation

#### Automated Installation

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

#### Manual Installation

1. Install system dependencies:
```bash
brew install portaudio ffmpeg espeak-ng cmake pkg-config duckdb
```

2. Set up Python environment:
```bash
brew install pyenv
pyenv install 3.12.2
pyenv virtualenv 3.12.2 voicecoach
export PYENV_VERSION=voicecoach
```

3. Install Python packages:
```bash
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

4. Download AI models:
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

### Linux Installation

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install portaudio19-dev ffmpeg espeak-ng cmake pkg-config

# Install Python 3.12+
sudo apt-get install python3.12 python3.12-venv python3-pip

# Create virtual environment
python3.12 -m venv voicecoach
source voicecoach/bin/activate

# Install Python packages
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# Download AI models (same as macOS)
# Follow steps 4 from macOS manual installation
```

## Configuration

### Environment Variables (.env)

1. Create environment file:
```bash
cp .env.example .env
```

2. Edit .env with your API keys:
```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ORG_ID=your_openai_org_id_here  # Optional

# Google Gemini Configuration
GEMINI_API_KEY=your_gemini_api_key_here
```

### Application Settings (config.yaml)

```yaml
llm:
  provider: "openai"  # or "gemini"
  model: "gpt-4o"  # or "gemini-1.5-pro-latest"

audio:
  frame_rate: 16000
  vad_threshold: 0.6

stt:
  model_path: "whisper.cpp/models/ggml-tiny.en.int8.bin"

tts:
  engine: "piper"  # or "coqui"
  voice_path: "models/piper/en_US-amy-medium.onnx"

ui:
  theme: "auto"  # auto, dark, light
```

### Getting API Keys

- **OpenAI**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Google Gemini**: Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

## Usage

### GUI Application

```bash
# Activate environment
pyenv activate voicecoach

# Launch GUI
python main.py
```

### CLI Commands

```bash
# Run quick assessment
python -m voice_training_app.cli assess --duration 30

# Start practice session
python -m voice_training_app.cli practice --mode guided

# View progress stats
python -m voice_training_app.cli stats --days 7
```

## Dev Manager Usage (dev.sh)

Convenient commands for managing backend and frontend:

```bash
# Start both services
./dev.sh start

# Stop both services
./dev.sh stop

# Restart both
./dev.sh restart

# Show status (ports/PIDs)
./dev.sh status

# Tail logs (Ctrl+C to exit)
./dev.sh logs

# Backend only
./dev.sh start:be
./dev.sh stop:be

# Frontend only
./dev.sh start:fe
./dev.sh stop:fe
```

### Practice Modes

#### Free Practice Mode
- Continuous speech recognition with real-time feedback
- Live WPM and accuracy scoring
- No time limits or structured exercises
- Best for warm-up and general assessment

#### Guided Training Mode
- AI-generated 4-week training plans
- Phoneme-specific drills based on assessment
- Progress tracking with streak monitoring
- Personalized difficulty adjustment

### Session Flow

1. **Audio Calibration**: System tests microphone input levels
2. **Warm-up Assessment**: 30-second free speech sample for baseline
3. **Mode Selection**: Choose between free practice or guided training
4. **Active Training**: Real-time transcription with immediate feedback
5. **Session Summary**: Performance analytics and recommendations
6. **Progress Sync**: Results saved with trend analysis

## Development

### Setup Development Environment

```bash
# Clone and setup
git clone <repository-url>
cd voice_training_app
pyenv activate voicecoach

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Project Structure

```
voice_training_app/
├── main.py                 # Application entry point
├── src/
│   ├── audio_io.py        # Audio processing and I/O
│   ├── ui.py              # GUI interface
│   ├── assessment.py      # Speech analysis
│   ├── planner.py         # Training plan generation
│   └── prompt_engine.py   # LLM integration
├── config.yaml            # Application configuration
├── requirements.txt       # Python dependencies
├── tests/                 # Test suite
└── docs/                  # Documentation
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run tests (`python -m pytest`)
6. Commit changes (`git commit -m 'Add amazing feature'`)
7. Push to branch (`git push origin feature/amazing-feature`)
8. Submit a pull request

## Testing

### Run Test Suite

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src/

# Run specific test module
python -m pytest tests/test_assessment.py
```

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **Audio Tests**: Microphone and speaker functionality
- **UI Tests**: Interface interaction testing

## Troubleshooting

### Common Issues

#### Audio Problems

```bash
# Issue: Audio not working
# Solution: Install PortAudio and check permissions
brew install portaudio
# Check microphone permissions in System Preferences
```

#### Model Issues

```bash
# Issue: Whisper model not found
# Solution: Re-download models
cd whisper.cpp
./models/download-ggml-model.sh tiny.en.int8
```

#### API Errors

```bash
# Issue: API authentication failed
# Solution: Check API keys
cat .env  # Verify keys are set correctly
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

#### Environment Issues

```bash
# Issue: Python environment problems
# Solution: Reset virtual environment
pyenv virtualenv-delete voicecoach
pyenv virtualenv 3.12.2 voicecoach
pyenv activate voicecoach
pip install -r requirements.txt
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py

# Check logs
tail -f logs/app.log
```

### Performance Issues

- **High CPU Usage**: Reduce audio frame rate in config.yaml
- **Slow Recognition**: Switch to smaller Whisper model
- **Memory Issues**: Restart application periodically

### Getting Help

1. Check application logs in `logs/app.log`
2. Review configuration in `config.yaml`
3. Verify all dependencies are installed
4. Create an issue on GitHub with:
   - Error messages
   - System information
   - Steps to reproduce

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
**Made with ❤️ for better communication**
