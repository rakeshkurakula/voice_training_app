# file: install_voicecoach.sh
#!/usr/bin/env bash
set -e

# 1. Homebrew audio + build deps
brew install portaudio ffmpeg espeak-ng cmake pkg-config duckdb

# 2. Python 3.12 env
brew install pyenv
pyenv install 3.12.2
pyenv virtualenv 3.12.2 voicecoach
export PYENV_VERSION=voicecoach

# 3. Pip packages
pip install --upgrade pip wheel setuptools
pip install pyside6 pyobjc torch==2.3.0 torchvision torchaudio librosa jiwer phonemizer openai google-generativeai pyyaml asyncio edge-tts httpx backoff tiktoken

# 4. Whisper.cpp (Metal + int8 model)
git clone --depth 1 https://github.com/ggml-org/whisper.cpp
cd whisper.cpp && make METAL=1 && \
  ./models/download-ggml-model.sh tiny.en.int8 && cd ..

# 5. Piper (pre‑built voice)
mkdir -p models/piper && cd models/piper
curl -L -o amy-medium.tar.gz https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/amy/medium/en_US-amy-medium.tar.gz
tar -xf amy-medium.tar.gz && cd ../..

echo "✅  Installation finished. Activate with:  pyenv activate voicecoach"
echo "📝  Don't forget to configure your API keys:"
echo "     cp .env.example .env"
echo "     # Edit .env with your OpenAI/Gemini API keys"
