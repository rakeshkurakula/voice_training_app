#!/usr/bin/env python3
"""Test script to verify audio functionality"""

import logging
logging.basicConfig(level=logging.INFO)

def test_pyaudio():
    """Test if PyAudio can access the microphone"""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        
        print("✅ PyAudio imported successfully")
        print(f"📊 Available audio devices: {p.get_device_count()}")
        
        # List input devices
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                print(f"🎤 Input device {i}: {device_info['name']}")
        
        # Try to open default input device
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        print("✅ Successfully opened microphone stream")
        stream.close()
        p.terminate()
        return True
        
    except Exception as e:
        print(f"❌ PyAudio error: {e}")
        return False

def test_whisper_cli():
    """Test if Whisper CLI is accessible"""
    import subprocess
    import os
    
    whisper_path = "./whisper.cpp/build/bin/whisper-cli"
    if not os.path.exists(whisper_path):
        print(f"❌ Whisper CLI not found at: {whisper_path}")
        return False
    
    try:
        result = subprocess.run([whisper_path, "--help"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Whisper CLI is accessible")
            return True
        else:
            print(f"❌ Whisper CLI error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Whisper CLI test failed: {e}")
        return False

def test_microphone_access():
    """Test microphone access with a simple recording"""
    try:
        from audio_io import MicStreamer
        import time
        
        print("🎤 Testing microphone access...")
        mic = MicStreamer(frame_ms=100)  # 100ms frames
        mic.start()
        
        # Record for 1 second
        start_time = time.time()
        frames_collected = 0
        
        while time.time() - start_time < 1.0:
            try:
                data = mic.q.get(timeout=0.5)
                frames_collected += 1
                if frames_collected == 1:
                    print(f"✅ First audio frame received: {len(data)} bytes")
            except:
                pass
        
        mic.stop()
        
        if frames_collected > 0:
            print(f"✅ Collected {frames_collected} audio frames in 1 second")
            return True
        else:
            print("❌ No audio frames received")
            return False
            
    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 VoiceCoach Audio System Test")
    print("=" * 50)
    
    tests = [
        ("PyAudio", test_pyaudio),
        ("Whisper CLI", test_whisper_cli),
        ("Microphone Access", test_microphone_access)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔬 Testing {test_name}...")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! Audio system should work correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        print("\nPossible solutions:")
        print("- Grant microphone permissions in System Preferences")
        print("- Install PyAudio: pip install pyaudio")
        print("- Build Whisper.cpp: cd whisper.cpp && make")
