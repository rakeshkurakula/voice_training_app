import asyncio, yaml, json, pathlib
from audio_io import transcribe_stream, play_tts
from assessment import compute_scores
from planner import generate_plan, accuracy_to_cefr
from db import CoachDB
from progress import kpi_dataframe, sparkline_data, moving_average, month_over_month
from prompt_engine import PromptEngine
import datetime as dt
import logging

# Try to import GUI components
try:
    from ui import CoachWindow, qasync, QtWidgets
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    # Console UI fallback
    class ConsoleUI:
        def log_message(self, msg):
            print(f"[LOG] {msg}")
            logging.info(f"[ConsoleUI] {msg}")
        def live_metrics(self, wpm, acc):
            print(f"[METRICS] WPM: {wpm}, Accuracy: {acc:.1%}")
        def update_summary(self, cefr, score, streak):
            print(f"[SUMMARY] CEFR: {cefr}, Score: {score:.1%}, Streak: {streak}")
        def update_plan_steps(self, steps, play_callback_factory=None):
            print(f"[PLAN] {len(steps)} training steps loaded")
            for i, step in enumerate(steps[:3]):  # Show first 3 steps
                print(f"  Step {step.get('step_num', i+1)}: {step.get('description', 'No description')}")
        def history_update(self, analytics):
            print(f"[ANALYTICS] MA: {analytics.get('ma', 'N/A')}, MoM: {analytics.get('mom', 'N/A')}")

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
    """Handle session start event from UI"""
    logging.info("[SESSION] Training session started")

async def handle_session_end(db: CoachDB, user_id: int, latest_accuracy: float, cfg):
    """Handle session end event from UI"""
    logging.info(f"[SESSION] Training session ended with accuracy: {latest_accuracy}")
    # Generate final plan based on session performance
    plan = generate_plan(latest_accuracy, weeks=cfg["plan"]["weeks"])
    await db.save_plan(user_id, latest_accuracy, plan)

async def voice_loop(cfg, db: CoachDB, ui, user_id: int, session_id: int):
    logging.info("[voice_loop] Started voice_loop for user_id=%s, session_id=%s", user_id, session_id)
    history_cache = []
    voice_path = cfg["tts"].get("voice_path", "models/piper/en_US-amy-medium.onnx")
    latest_accuracy = 0.85  # Set a default accuracy for initial plan generation
    session_active = True
    
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

    # Generate initial training plan and UI update
    try:
        initial_plan = generate_plan(latest_accuracy, weeks=cfg["plan"]["weeks"])
        plan_id = await db.save_plan(user_id, latest_accuracy, initial_plan)
        for step in initial_plan["steps"]:
            await db.save_plan_step(plan_id, step["step_num"], step["description"])

        # Update UI with initial data
        cefr = accuracy_to_cefr(latest_accuracy)
        hist = await db.fetch_history(user_id, limit=100)
        streak = compute_streak(hist)
        ui.update_summary(cefr, latest_accuracy, streak)
        
        # Show current week's steps
        week = 1
        week_steps = [step for step in initial_plan["steps"] if step["week"] == week]
        ui.update_plan_steps(week_steps, play_callback_factory=lambda step: make_play_callback(step, voice_path))
        
        ui.log_message("✅ Initial training plan loaded successfully")
    except Exception as e:
        ui.log_message(f"⚠️ Failed to generate initial plan: {e}")
        logging.error(f"Initial plan generation failed: {e}")
    
    async for hyp in transcribe_stream(cfg["stt"]["model_path"]):
        if not hyp.endswith("\n"):  # still streaming
            continue
        ref = hyp.strip()
        wav_tmp = "/tmp/utt.wav"  # recorded in audio_io
        s = compute_scores(ref, hyp, wav_tmp)
        latest_accuracy = s.phoneme_acc
        
        # Save utterance and metrics
        utterance_id = await db.save_utterance(session_id, ref, hyp, wav_tmp)
        await db.save_metrics(utterance_id, s.__dict__)
        ui.live_metrics(s.pace_wpm, s.phoneme_acc)

        # Generate and store plan based on latest accuracy
        plan = generate_plan(s.phoneme_acc, weeks=cfg["plan"]["weeks"])
        plan_id = await db.save_plan(user_id, s.phoneme_acc, plan)
        for step in plan["steps"]:
            await db.save_plan_step(plan_id, step["step_num"], step["description"])

        # --- UI: Update summary and plan steps ---
        cefr = accuracy_to_cefr(s.phoneme_acc)
        last_score = s.phoneme_acc
        hist = await db.fetch_history(user_id, limit=100)
        streak = compute_streak(hist)
        ui.update_summary(cefr, last_score, streak)
        # Show only current week's steps
        week = 1  # For now, always show week 1; can be dynamic
        week_steps = [step for step in plan["steps"] if step["week"] == week]
        ui.update_plan_steps(week_steps, play_callback_factory=lambda step: make_play_callback(step, voice_path))

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

        # In real implementation, this would be triggered by UI events
        if not session_active:  # This would be set by UI signal
            await handle_session_end(db, user_id, latest_accuracy, cfg)
            break

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