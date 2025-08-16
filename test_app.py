#!/usr/bin/env python3
"""
Simple test script to verify the voice training app works without GUI.
"""
import asyncio
import sys
import time
import tempfile
import wave
import numpy as np
from main import ConsoleUI, CoachDB
import yaml

async def test_app():
    """Test the application without GUI."""
    print("🧪 Testing Voice Training App...")
    
    # Load config
    try:
        with open("config.yaml", "r") as f:
            cfg = yaml.safe_load(f)
        print("✅ Config loaded successfully")
    except Exception as e:
        print(f"❌ Config error: {e}")
        return
    
    # Test database
    try:
        db = CoachDB(cfg["database"]["path"])
        await db.init()
        print("✅ Database initialized")
        
        # Create test user and session
        user_id = await db.create_user("test_user")
        session_id = await db.create_session(user_id)
        print(f"✅ Created user {user_id} and session {session_id}")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return
    
    # Test UI (console mode)
    try:
        ui = ConsoleUI()
        ui.log_message("Test message")
        ui.live_metrics(120.5, 0.85)
        ui.update_summary("B2", 0.85, 5)
        print("✅ Console UI working")
    except Exception as e:
        print(f"❌ UI error: {e}")
        return
    
    # Test assessment with a temporary WAV file
    try:
        from assessment import compute_scores
        
        # Create a temporary WAV file for testing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            wav_path = tmp_wav.name
            
        # Create a simple WAV file (1 second of silence)
        with wave.open(wav_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)
            # Generate 1 second of silence
            silence = np.zeros(16000, dtype=np.int16)
            wf.writeframes(silence.tobytes())
        
        scores = compute_scores("hello world", "hello world", wav_path)
        print(f"✅ Assessment working: WER={scores.wer}, Pace={scores.pace_wpm}, Acc={scores.phoneme_acc}")
        
        # Clean up
        import os
        os.unlink(wav_path)
        
    except Exception as e:
        print(f"❌ Assessment error: {e}")
        return
    
    # Test planner
    try:
        from planner import generate_plan, accuracy_to_cefr
        plan = generate_plan(0.85, weeks=2)
        cefr = accuracy_to_cefr(0.85)
        print(f"✅ Planner working: CEFR={cefr}, Plan steps={len(plan['steps'])}")
    except Exception as e:
        print(f"❌ Planner error: {e}")
        return
    
    # Test progress analytics
    try:
        from progress import kpi_dataframe, sparkline_data, moving_average
        test_history = [
            {"timestamp": "2024-01-01T10:00:00", "phoneme_acc": 0.8, "wer": 0.1, "pace_wpm": 120},
            {"timestamp": "2024-01-02T10:00:00", "phoneme_acc": 0.85, "wer": 0.05, "pace_wpm": 125},
        ]
        df = kpi_dataframe(test_history)
        sparkline = sparkline_data(df, kpi="phoneme_acc", window=2)
        ma = moving_average(df, kpi="phoneme_acc", window=2)
        print(f"✅ Analytics working: Sparkline={len(sparkline)}, MA={len(ma)}")
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        return
    
    print("\n🎉 All tests passed! The application is working correctly.")
    print("\n📋 Summary:")
    print("  ✅ Configuration loading")
    print("  ✅ Database operations")
    print("  ✅ Console UI")
    print("  ✅ Speech assessment")
    print("  ✅ Plan generation")
    print("  ✅ Progress analytics")
    print("\n🚀 The app is ready to use!")

if __name__ == "__main__":
    asyncio.run(test_app()) 