"""Integration tests for VoiceCoach database and analytics."""
import pytest
import pytest_asyncio
import asyncio
import tempfile
import pathlib
from db import CoachDB
from progress import kpi_dataframe, sparkline_data, moving_average, month_over_month
from planner import accuracy_to_cefr, generate_plan

@pytest_asyncio.fixture
async def test_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = CoachDB(db_path)
    await db.init()
    yield db
    
    # Cleanup
    pathlib.Path(db_path).unlink(missing_ok=True)

@pytest.mark.asyncio
async def test_user_session_flow(test_db):
    """Test complete user -> session -> utterance -> metrics flow."""
    # Create user
    user_id = await test_db.create_user("test_user")
    assert user_id > 0
    
    # Create session
    session_id = await test_db.create_session(user_id)
    assert session_id > 0
    
    # Save utterance and metrics
    utterance_id = await test_db.save_utterance(session_id, "hello world", "hello world", "/tmp/test.wav")
    assert utterance_id > 0
    
    await test_db.save_metrics(utterance_id, {
        "wer": 0.0,
        "pace_wpm": 120.0,
        "phoneme_acc": 0.85,
        "syllable_var": 0.1,
        "overall_score": 0.8
    })
    
    # Fetch history
    history = await test_db.fetch_history(user_id)
    assert len(history) == 1
    assert history[0]["reference"] == "hello world"
    assert history[0]["phoneme_acc"] == 0.85

@pytest.mark.asyncio
async def test_plan_generation(test_db):
    """Test plan generation and storage."""
    user_id = await test_db.create_user("test_user")
    
    # Generate plan
    plan = generate_plan(0.75, weeks=2)
    plan_id = await test_db.save_plan(user_id, 0.75, plan)
    assert plan_id > 0
    
    # Save plan steps
    for step in plan["steps"]:
        await test_db.save_plan_step(plan_id, step["step_num"], step["description"])
    
    # Fetch plans
    plans = await test_db.fetch_plans(user_id)
    assert len(plans) == 1
    assert plans[0]["baseline_acc"] == 0.75

def test_cefr_mapping():
    """Test CEFR level mapping based on accuracy."""
    assert accuracy_to_cefr(0.5) == "A1"
    assert accuracy_to_cefr(0.7) == "B1"
    assert accuracy_to_cefr(0.8) == "B2"
    assert accuracy_to_cefr(0.9) == "C1"
    assert accuracy_to_cefr(0.95) == "C2"

def test_progress_analytics():
    """Test progress analytics functions."""
    # Mock history data with all required keys
    history = [
        {"timestamp": "2024-01-01T10:00:00", "phoneme_acc": 0.7, "wer": 0.1, "pace_wpm": 110, "syllable_var": 0.1, "overall_score": 0.7},
        {"timestamp": "2024-01-02T10:00:00", "phoneme_acc": 0.8, "wer": 0.05, "pace_wpm": 120, "syllable_var": 0.09, "overall_score": 0.8},
        {"timestamp": "2024-01-03T10:00:00", "phoneme_acc": 0.85, "wer": 0.03, "pace_wpm": 130, "syllable_var": 0.08, "overall_score": 0.85},
    ]
    
    df = kpi_dataframe(history)
    assert not df.empty
    assert len(df) == 3
    
    # Test sparkline data
    acc_sparkline = sparkline_data(df, kpi="phoneme_acc", window=3)
    assert len(acc_sparkline) == 3
    assert acc_sparkline[-1] == 0.85
    
    # Test moving average
    ma = moving_average(df, kpi="phoneme_acc", window=2)
    assert len(ma) == 3

if __name__ == "__main__":
    import sys; import pytest; sys.exit(pytest.main([__file__])) 