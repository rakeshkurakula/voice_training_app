import asyncio, yaml, json, pathlib
from audio_io import transcribe_stream, play_tts
from assessment import compute_scores
from planner import generate_plan, accuracy_to_cefr
from db import CoachDB
from progress import kpi_dataframe, sparkline_data, moving_average, month_over_month

GUI_AVAILABLE = True
try:
    from ui import CoachWindow, qasync, QtWidgets
except ImportError as e:  # pragma: no cover - only runs without PySide6
    print(
        "⚠️ GUI could not be initialized: " + str(e)
    )
    print(
        "Install PySide6 via 'pip install pyside6' and ensure Qt/libEGL packages are installed.\n"
        "On Ubuntu you can run: sudo apt-get install libegl1"
    )
    GUI_AVAILABLE = False

class ConsoleUI:
    """Fallback interface printing updates to the terminal."""
    def log_message(self, message: str):
        print(message)

    def live_metrics(self, pace, acc):
        print(f"Live Metrics - WPM: {pace:.1f}, Acc: {acc:.1%}")

    def history_update(self, analytics: dict):
        print("History update:", analytics)

    def update_summary(self, cefr: str, last_score: float, streak: int):
        print(
            f"Summary - Level: {cefr}, Last Score: {last_score:.1%}, Streak: {streak}"
        )

    def update_plan_steps(self, steps: list, play_callback_factory=None):
        print("Plan Steps:")
        for step in steps:
            print(f"  {step.get('step_num', 0)}. {step.get('description', '')}")

from prompt_engine import PromptEngine
import datetime as dt
import logging

def compute_streak(history):
    # Simple streak: count consecutive days with assessments up to today
    if not history:
        return 0
    dates = sorted({h.get("timestamp", "")[:10] for h in history if h.get("timestamp")})
    if not dates:
        return 0
    streak = 0
    today = dt.date.today()
    for i in range(len(dates)-1, -1, -1):
        d = dt.date.fromisoformat(dates[i])
        if (today - d).days == streak:
            streak += 1
        else:
            break
    return streak

def make_play_callback(step, voice_path):
    def callback():
        asyncio.create_task(play_tts(step.get("description", ""), voice_path=voice_path))
    return callback

def handle_session_start():
    """Handler for session start signal"""
    logging.info("Session started")
    print("Session started")

def handle_session_end(db, user_id, latest_accuracy, cfg):
    """Handler for session end signal - now regenerates plan based on latest accuracy"""
    logging.info(f"Session ended for user {user_id} with accuracy {latest_accuracy}")
    print(f"Session ended for user {user_id} with accuracy {latest_accuracy}")
    
    # Generate new plan based on latest_accuracy from the session
    if latest_accuracy > 0:
        try:
            plan = generate_plan(latest_accuracy, weeks=cfg["plan"]["weeks"])
            # Save the new plan to database
            asyncio.create_task(_save_session_end_plan(db, user_id, latest_accuracy, plan))
        except Exception as e:
            logging.error(f"Error generating plan at session end: {e}")
            print(f"Error generating plan at session end: {e}")

async def _save_session_end_plan(db, user_id, accuracy, plan):
    """Helper to save plan generated at session end"""
    try:
        plan_id = await db.save_plan(user_id, accuracy, plan)
        for step in plan["steps"]:
            await db.save_plan_step(plan_id, step["step_num"], step["description"])
        logging.info(f"New plan saved with ID: {plan_id}")
    except Exception as e:
        logging.error(f"Error saving session end plan: {e}")

async def persist_step_completion(db, current_plan_id, step_num, completed, ui):
    """Async function to persist step completion and refresh progress"""
    try:
        await db.update_plan_step_completion(current_plan_id, step_num, completed)
        # Refresh progress display
        ui.log_message(f"Step {step_num} completion updated: {completed}")
    except Exception as e:
        ui.log_message(f"Error updating step completion: {e}")
        logging.error(f"Error updating step completion: {e}")

async def load_existing_plan(db, user_id):
    """Load the most recent plan for the user from database"""
    try:
        # Get the most recent plan for the user
        plan = await db.fetch_latest_plan(user_id)
        if plan:
            plan_id = plan.get('id')
            steps = await db.get_plan_steps(plan_id)
            return plan_id, steps
        return None, []
    except Exception as e:
        logging.error(f"Error loading existing plan: {e}")
        return None, []

async def voice_loop(cfg, db: CoachDB, ui: CoachWindow, user_id: int, session_id: int):
    logging.info("[voice_loop] Started voice_loop for user_id=%s, session_id=%s", user_id, session_id)
    history_cache = []
    voice_path = cfg["tts"].get("voice_path", "models/piper/en_US-amy-medium.onnx")
    
    # Nonlocal variable to track latest accuracy across utterances
    latest_accuracy = 0.0
    
    # Load existing plan at startup instead of generating new one
    current_plan_id, existing_steps = await load_existing_plan(db, user_id)
    
    # Initialize PromptEngine with configuration
    try:
        prompt_engine = PromptEngine(config_path="config.yaml")
        if prompt_engine.provider == "openai" and prompt_engine.openai_org_id:
            ui.log_message(f"✅ LLM: OpenAI (org: {prompt_engine.openai_org_id}) initialized successfully")
        else:
            ui.log_message("✅ LLM initialized successfully")
    except Exception as e:
        ui.log_message(f"⚠️ LLM initialization failed: {e}")
        prompt_engine = None
    
    # Connect step_toggled signal to persist function
    if hasattr(ui, 'step_toggled'):
        def on_step_toggled(step_num, completed):
            if current_plan_id:
                asyncio.create_task(persist_step_completion(db, current_plan_id, step_num, completed, ui))
        ui.step_toggled.connect(on_step_toggled)
    
    # Update UI with existing plan steps if available
    if existing_steps:
        # Show only current week's steps
        week = 1  # For now, always show week 1; can be dynamic
        week_steps = [step for step in existing_steps if step.get("week", 1) == week]
        ui.update_plan_steps(week_steps, play_callback_factory=lambda step: make_play_callback(step, voice_path))
        ui.log_message(f"Loaded existing plan with {len(existing_steps)} steps")
    
    async for hyp in transcribe_stream(cfg["stt"]["model_path"]):
        if not hyp.endswith("\n"):  # still streaming
            continue
        ref = hyp.strip()
        wav_tmp = "/tmp/utt.wav"  # recorded in audio_io
        s = compute_scores(ref, hyp, wav_tmp)
        
        # Update latest_accuracy with each utterance
        latest_accuracy = s.phoneme_acc
        
        # Save utterance and metrics
        utterance_id = await db.save_utterance(session_id, ref, hyp, wav_tmp)
        await db.save_metrics(utterance_id, s.__dict__)
        ui.live_metrics(s.pace_wpm, s.phoneme_acc)
        
        # --- UI: Update summary ---
        cefr = accuracy_to_cefr(s.phoneme_acc)
        last_score = s.phoneme_acc
        hist = await db.fetch_history(user_id, limit=100)
        streak = compute_streak(hist)
        ui.update_summary(cefr, last_score, streak)
        
        # refresh history sparklines every autosave_interval
        history_cache.append(s.__dict__)
        if len(history_cache) % 10 == 0:
            df = kpi_dataframe(hist)
            analytics = {
                "acc": sparkline_data(df, kpi="phoneme_acc", window=10),
                "wer": sparkline_data(df, kpi="wer", window=10),
                "ma": (moving_average(df, kpi="phoneme_acc", window=7)[-1] if not df.empty else None),
                "mom": month_over_month(df, kpi="phoneme_acc") if not df.empty else None,
            }
            ui.history_update(analytics)
    
    # Return latest_accuracy for session end handler
    return latest_accuracy

async def main():
    cfg = yaml.safe_load(open("config.yaml"))
    db = CoachDB(cfg["database"]["path"]); await db.init()
    # Create or get user (for demo, single user 'default')
    user_id = await db.create_user("default")
    session_id = await db.create_session(user_id)
    
    if GUI_AVAILABLE:
        try:
            app = QtWidgets.QApplication([])
            window = CoachWindow(); window.show()
            
            # Maintain latest_accuracy as shared variable
            latest_accuracy = 0.0
            
            # Connect UI signals to handlers
            if hasattr(window, 'session_start'):
                window.session_start.connect(handle_session_start)
            if hasattr(window, 'session_end'):
                # Pass latest_accuracy to session end handler
                window.session_end.connect(lambda: handle_session_end(db, user_id, latest_accuracy, cfg))
            
            loop = qasync.QEventLoop(app); asyncio.set_event_loop(loop)
            
            # Run voice loop and capture latest_accuracy
            async def run_voice_loop():
                nonlocal latest_accuracy
                latest_accuracy = await voice_loop(cfg, db, window, user_id, session_id)
            
            asyncio.ensure_future(run_voice_loop())
            with loop:
                loop.run_forever()
            return
        except Exception as e:  # pragma: no cover - depends on system Qt
            print("⚠️ Qt GUI failed to start:", e)
            print(
                "Install system Qt libraries (e.g. libEGL) or run in CLI mode."
            )
    
    ui = ConsoleUI()
    await voice_loop(cfg, db, ui, user_id, session_id)

if __name__ == "__main__":
    asyncio.run(main())
