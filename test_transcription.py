#!/usr/bin/env python3
"""Test script to verify transcription functionality"""

import asyncio
import logging
import time
logging.basicConfig(level=logging.INFO)

async def test_transcribe_stream():
    """Test the transcribe_stream function"""
    from audio_io import transcribe_stream
    
    model_path = "whisper.cpp/models/ggml-tiny.en.bin"
    print(f"🎤 Testing transcription with model: {model_path}")
    print("🗣️  Please speak into your microphone for 10 seconds...")
    print("💡 Say something like: 'Hello, this is a test of the voice training app'")
    
    start_time = time.time()
    transcription_count = 0
    
    try:
        async for transcript in transcribe_stream(model_path):
            transcription_count += 1
            elapsed = time.time() - start_time
            
            print(f"📝 [{elapsed:.1f}s] Transcript #{transcription_count}: {transcript}")
            
            # Stop after 10 seconds for testing
            if elapsed > 10:
                print("⏱️  10 seconds elapsed, stopping test")
                break
                
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return False
    
    if transcription_count > 0:
        print(f"✅ Successfully received {transcription_count} transcriptions")
        return True
    else:
        print("❌ No transcriptions received")
        return False

async def test_whisper_with_sample():
    """Test Whisper with a simple audio sample"""
    from audio_io import WhisperWorker, MicStreamer
    import tempfile
    import os
    
    print("🎤 Recording 3 seconds of audio for transcription test...")
    
    # Record 3 seconds of audio
    mic = MicStreamer(frame_ms=100)
    mic.start()
    
    audio_data = b""
    start_time = time.time()
    
    while time.time() - start_time < 3.0:
        try:
            data = mic.q.get(timeout=0.5)
            audio_data += data
        except:
            pass
    
    mic.stop()
    
    if len(audio_data) == 0:
        print("❌ No audio data recorded")
        return False
    
    print(f"✅ Recorded {len(audio_data)} bytes of audio")
    
    # Test transcription
    worker = WhisperWorker("whisper.cpp/models/ggml-tiny.en.bin")
    
    try:
        transcript = worker.transcribe(audio_data)
        if transcript:
            print(f"📝 Transcription: '{transcript}'")
            return True
        else:
            print("❌ No transcription returned")
            return False
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 VoiceCoach Transcription Test")
    print("=" * 50)
    
    # Test 1: Simple transcription with recorded audio
    print("\n🔬 Test 1: Record and transcribe 3 seconds of audio")
    try:
        success1 = asyncio.run(test_whisper_with_sample())
    except Exception as e:
        print(f"❌ Test 1 crashed: {e}")
        success1 = False
    
    # Test 2: Streaming transcription (if user wants to test it)
    print(f"\n🔬 Test 2: Streaming transcription")
    print("⚠️  This test will listen for 10 seconds. Press Ctrl+C to skip.")
    
    try:
        import time
        time.sleep(2)  # Give user time to read
        success2 = asyncio.run(test_transcribe_stream())
    except KeyboardInterrupt:
        print("⏭️  Streaming test skipped by user")
        success2 = None
    except Exception as e:
        print(f"❌ Test 2 crashed: {e}")
        success2 = False
    
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print(f"  {'✅ PASS' if success1 else '❌ FAIL'} Simple transcription")
    if success2 is not None:
        print(f"  {'✅ PASS' if success2 else '❌ FAIL'} Streaming transcription")
    else:
        print(f"  ⏭️ SKIP Streaming transcription")
    
    if success1:
        print("\n🎉 Core transcription is working!")
        if success2:
            print("🎉 Streaming transcription is also working!")
    else:
        print("\n⚠️  Transcription issues detected. Check:")
        print("- Microphone permissions")
        print("- Whisper model file exists")
        print("- Speaking clearly and loudly enough")
