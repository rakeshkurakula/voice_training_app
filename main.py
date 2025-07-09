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

async def voice_loop(cfg, db: CoachDB, ui: CoachWindow, user_id: int, session_id: int):
    logging.info("[voice_loop] Started voice_loop for user_id=%s, session_id=%s", user_id, session_id)
    history_cache = []
    voice_path = cfg["tts"].get("voice_path", "models/piper/en_US-amy-medium.onnx")
    
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
    
    async for hyp in transcribe_stream(cfg["stt"]["model_path"]):
        if not hyp.endswith("\n"):  # still streaming
            continue
        ref = hyp.strip()
        wav_tmp = "/tmp/utt.wav"  # recorded in audio_io
        s = compute_scores(ref, hyp, wav_tmp)
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
            loop = qasync.QEventLoop(app); asyncio.set_event_loop(loop)

            asyncio.ensure_future(
                voice_loop(cfg, db, window, user_id, session_id)
            )
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
