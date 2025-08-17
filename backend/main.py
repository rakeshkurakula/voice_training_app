"""
FastAPI Backend for VoiceCoach
Provides REST API and WebSocket endpoints for voice training
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import json
import logging
import tempfile
import os
import base64
import subprocess
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
import uvicorn
from faster_whisper import WhisperModel
import wave
import time

try:
    from openai import OpenAI  # openai>=1.0
    _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
except Exception:
    _openai_client = None

# Import existing modules
import sys
sys.path.append('..')
from db import CoachDB
from assessment import compute_scores
from planner import generate_plan, accuracy_to_cefr
from progress import kpi_dataframe, sparkline_data, moving_average, month_over_month
from prompt_engine import PromptEngine
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="VoiceCoach API",
    description="Voice training and pronunciation assessment API",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
db: Optional[CoachDB] = None
config: dict = {}
prompt_engine: Optional[PromptEngine] = None
fw_model: Optional[WhisperModel] = None

# Pydantic models
class UserCreate(BaseModel):
    username: str

class SessionStart(BaseModel):
    user_id: int

class TrainingPlanRequest(BaseModel):
    user_id: int
    accuracy: float
    weeks: int = 4

class AudioAssessment(BaseModel):
    reference_text: str
    hypothesis_text: str
    audio_path: str

class WSMessage(BaseModel):
    type: str
    data: dict

class ASRResp(BaseModel):
    text: str
    duration_sec: float

class WERReq(BaseModel):
    reference: str
    hypothesis: str
class WERResp(BaseModel):
    wer: float

# --------- LLM models (request schemas) ---------
class Constraints(BaseModel):
    banned_words: list[str] | None = None

class GenReq(BaseModel):
    skill: str
    cefr: str
    topic: str | None = None
    count: int = 3
    constraints: Constraints | None = None

class CritiqueReq(BaseModel):
    transcript: str
    metrics: dict
    cefr: str
    skill: str

class FollowReq(BaseModel):
    topic: str
    cefr: str
    count: int = 5

# Connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()

# Per-connection audio buffering context
_ws_context: dict = {}

def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent

def _whisper_cli_path() -> str:
    # Resolve whisper.cpp cli relative to repo root
    p = _repo_root() / "whisper.cpp" / "build" / "bin" / "whisper-cli"
    return str(p)

def _model_path_abs() -> str:
    mp = str(config.get("stt", {}).get("model_path", ""))
    mp_path = Path(mp)
    if not mp_path.is_absolute():
        mp_path = _repo_root() / mp_path
    return str(mp_path)

async def _ensure_ctx(websocket: WebSocket):
    if websocket not in _ws_context:
        tmp_dir = tempfile.mkdtemp(prefix="vc_ws_")
        seg_dir = os.path.join(tmp_dir, "segs")
        os.makedirs(seg_dir, exist_ok=True)
        _ws_context[websocket] = {
            "tmp_dir": tmp_dir,
            "seg_dir": seg_dir,
            "seg_idx": 0,
            "transcribing": False,
            "full_text": "",
            "pcm_raw_path": os.path.join(tmp_dir, "raw.pcm"),
        }

async def _cleanup_ctx(websocket: WebSocket):
    ctx = _ws_context.pop(websocket, None)
    if not ctx:
        return
    try:
        tmp_dir = ctx.get("tmp_dir")
        if tmp_dir and os.path.isdir(tmp_dir):
            for root, _, files in os.walk(tmp_dir, topdown=False):
                for f in files:
                    try:
                        os.unlink(os.path.join(root, f))
                    except Exception:
                        pass
                try:
                    os.rmdir(root)
                except Exception:
                    pass
    except Exception:
        pass

def _write_wav_from_pcm(raw_path: str, wav_path: str, sample_rate: int = 16000) -> None:
    data = b""
    with open(raw_path, "rb") as f:
        data = f.read()
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(data)

async def _transcribe_segment(websocket: WebSocket, seg_path: str):
    ctx = _ws_context.get(websocket)
    if not ctx:
        return
    if ctx.get("transcribing"):
        return
    ctx["transcribing"] = True
    try:
        # Convert this segment to wav (16k mono)
        tmp_dir = ctx["tmp_dir"]
        wav_path = os.path.join(tmp_dir, "seg.wav")
        try:
            _ffmpeg_convert_to_wav(seg_path, wav_path)
        except Exception as e:
            logger.warning(f"ffmpeg convert failed: {e}")
            await manager.send_personal_message({
                "type": "transcription",
                "data": {"text": "[Transcriber error: ffmpeg missing or failed]", "confidence": 0.0}
            }, websocket)
            return

        # Transcribe this wav using faster-whisper
        try:
            text = _transcribe_wav(wav_path)
        except Exception as e:
            logger.warning(f"segment STT failed: {e}")
            text = ""
        if text:
            # accumulate
            if ctx["full_text"]:
                ctx["full_text"] += " " + text
            else:
                ctx["full_text"] = text
            await manager.send_personal_message({
                "type": "transcription",
                "data": {"text": ctx["full_text"], "confidence": 0.7, "partial": True}
            }, websocket)
    finally:
        ctx["transcribing"] = False

@app.on_event("startup")
async def startup_event():
    """Initialize database and configuration on startup"""
    global db, config, prompt_engine, fw_model
    
    # Load configuration
    config = yaml.safe_load(open("../config.yaml"))
    logger.info("Configuration loaded")
    
    # Initialize database
    db = CoachDB(config["database"]["path"])
    await db.init()
    logger.info("Database initialized")
    
    # Initialize LLM
    try:
        prompt_engine = PromptEngine(config_path="../config.yaml")
        logger.info("LLM engine initialized")
    except Exception as e:
        logger.warning(f"LLM initialization failed: {e}")
    
    # Initialize Faster-Whisper (CPU, int8 for portability)
    try:
        model_hint = str(config.get("stt", {}).get("model_path", "tiny.en")).strip()
        # If a path to ggml is given, fallback to a small model name
        if model_hint.endswith(".bin"):
            model_hint = "tiny.en"
        fw_model = WhisperModel(model_hint, device="cpu", compute_type="int8")
        logger.info("Faster-Whisper model initialized: %s", model_hint)
    except Exception as e:
        logger.warning(f"Faster-Whisper init failed: {e}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "VoiceCoach API is running", "version": "2.0.0"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": db is not None,
        "llm": prompt_engine is not None,
        "stt_ready": fw_model is not None,
        "config_loaded": bool(config)
    }

# User Management
@app.post("/users/")
async def create_user(user: UserCreate):
    """Create a new user"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    user_id = await db.create_user(user.username)
    return {"user_id": user_id, "username": user.username}

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get user information and history"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Get user history for analytics
    history = await db.fetch_history(user_id, limit=100)
    
    # Calculate streak  
    def compute_streak(history):
        if not history:
            return 0
        dates = sorted({h.get("timestamp", "")[:10] for h in history if h.get("timestamp")})
        if not dates:
            return 0
        import datetime as dt
        streak = 0
        today = dt.date.today()
        for i in range(len(dates)-1, -1, -1):
            d = dt.date.fromisoformat(dates[i])
            if (today - d).days == streak:
                streak += 1
            else:
                break
        return streak
    
    streak = compute_streak(history)
    
    # Calculate analytics
    df = kpi_dataframe(history)
    analytics = {
        "accuracy": sparkline_data(df, kpi="phoneme_acc", window=10) if not df.empty else [],
        "wer": sparkline_data(df, kpi="wer", window=10) if not df.empty else [],
        "moving_average": moving_average(df, kpi="phoneme_acc", window=7)[-1] if not df.empty else None,
        "month_over_month": month_over_month(df, kpi="phoneme_acc") if not df.empty else None,
    }
    
    latest_score = history[0].get("phoneme_acc", 0.85) if history else 0.85
    cefr_level = accuracy_to_cefr(latest_score)
    
    return {
        "user_id": user_id,
        "username": f"user_{user_id}",  # Add username field
        "streak": streak,
        "latest_score": latest_score,
        "cefr_level": cefr_level,
        "analytics": analytics,
        "history_count": len(history)
    }

# Session Management
@app.post("/sessions/")
async def create_session(session_data: SessionStart):
    """Create a new training session"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    session_id = await db.create_session(session_data.user_id)
    logger.info(f"Created session {session_id} for user {session_data.user_id}")
    
    return {"session_id": session_id, "user_id": session_data.user_id}

# Training Plans
@app.post("/training-plans/")
async def create_training_plan(plan_request: TrainingPlanRequest):
    """Generate a new training plan"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        plan = generate_plan(plan_request.accuracy, weeks=plan_request.weeks)
        plan_id = await db.save_plan(plan_request.user_id, plan_request.accuracy, plan)
        
        # Save individual steps
        for step in plan["steps"]:
            await db.save_plan_step(plan_id, step["step_num"], step["description"])
        
        logger.info(f"Generated training plan {plan_id} for user {plan_request.user_id}")
        return {"plan_id": plan_id, "plan": plan}
        
    except Exception as e:
        logger.error(f"Training plan generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")

@app.get("/training-plans/{user_id}")
async def get_latest_training_plan(user_id: int):
    """Get the latest training plan for a user"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # For now, generate a default plan - in production you'd fetch from DB
    try:
        latest_accuracy = 0.85  # Default or fetch from user's latest session
        plan = generate_plan(latest_accuracy, weeks=4)
        
        # Filter to current week (for demo, show week 1)
        current_week = 1
        week_steps = [step for step in plan["steps"] if step["week"] == current_week]
        
        # Add step metadata for UI compatibility
        enhanced_week_steps = []
        for i, step in enumerate(week_steps, 1):
            enhanced_step = {
                "step_num": i,
                "week": current_week,
                "description": step["description"],
                "difficulty": step.get("difficulty", "Medium"),
                "focus_area": step.get("focus_area", "Pronunciation"),
                "completed": False
            }
            enhanced_week_steps.append(enhanced_step)
        
        return {
            "plan": plan,
            "current_week": current_week,
            "week_steps": enhanced_week_steps,
            "total_weeks": 4
        }
    except Exception as e:
        logger.error(f"Failed to get training plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get training plan: {str(e)}")

# Audio Processing via Faster-Whisper
def _ffmpeg_convert_to_wav(src_path: str, dst_wav: str) -> None:
    cmd = ["ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ar", "16000", dst_wav]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or b"").decode("utf-8", errors="ignore")[:400])

def _transcribe_wav(wav_path: str) -> str:
    global fw_model
    if fw_model is None:
        raise RuntimeError("STT model not initialized")
    segments, _info = fw_model.transcribe(
        wav_path,
        language="en",
        vad_filter=False,
        beam_size=1,
        temperature=0.0,
    )
    text_parts: list[str] = []
    for seg in segments:
        if getattr(seg, "text", ""):
            text_parts.append(seg.text.strip())
    return " ".join(text_parts).strip()

@app.post("/audio/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """Accepts audio (webm/wav/mp3/etc.), converts to wav and transcribes with Faster-Whisper."""
    try:
        with tempfile.TemporaryDirectory(prefix="vc_up_") as td:
            src_suffix = ".webm" if audio_file.filename and audio_file.filename.endswith(".webm") else ""
            src_path = os.path.join(td, f"input{src_suffix}")
            with open(src_path, "wb") as f:
                f.write(await audio_file.read())
            wav_path = os.path.join(td, "input.wav")
            _ffmpeg_convert_to_wav(src_path, wav_path)
            text = _transcribe_wav(wav_path)
            return {"transcript": text}
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

# === Plan.md compatibility endpoints ===
@app.post("/asr", response_model=ASRResp)
async def asr_endpoint(file: UploadFile = File(...)):
    """ASR endpoint returning { text, duration_sec } for an uploaded file (webm/wav/mp3)."""
    start_t = time.time()
    try:
        with tempfile.TemporaryDirectory(prefix="vc_asr_") as td:
            src_path = os.path.join(td, file.filename or "audio")
            with open(src_path, "wb") as f:
                f.write(await file.read())
            # Faster-Whisper can ingest many formats directly
            segments, info = fw_model.transcribe(
                src_path,
                language="en",
                vad_filter=False,
                beam_size=1,
                temperature=0.0,
            )
            text = " ".join([s.text.strip() for s in segments]).strip()
            duration_sec = float(getattr(info, "duration", time.time() - start_t))
            return ASRResp(text=text, duration_sec=duration_sec)
    except Exception as e:
        logger.error(f"/asr failed: {e}")
        raise HTTPException(status_code=500, detail="ASR failed")

def _levenshtein_distance_words(ref_words: list[str], hyp_words: list[str]) -> int:
    m, n = len(ref_words), len(hyp_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if ref_words[i - 1] == hyp_words[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost  # substitution
            )
    return dp[m][n]

@app.post("/metrics/wer", response_model=WERResp)
async def wer_endpoint(req: WERReq):
    ref_words = req.reference.strip().split()
    hyp_words = req.hypothesis.strip().split()
    dist = _levenshtein_distance_words(ref_words, hyp_words)
    denom = max(1, len(ref_words))
    return WERResp(wer=round(dist / denom, 3))

# ================= LLM endpoints (with mock fallback) =================
SYSTEM_GEN = (
    "You are VoiceCoach, generating CEFR-appropriate drills. Reply ONLY JSON. "
    "Shape: {\"drills\":[{\"id\":\"string\",\"title\":\"string\",\"type\":\"articulation|descriptive|emotion|instructional|narrative\",\"prompt\":\"string\",\"script\":\"optional string\",\"constraints\":{\"banned_words\":[\"...\"]}}]}\n"
)

SYSTEM_CRIT = (
    "You are a concise speech coach. Given transcript + metrics, return JSON: "
    "{\"score\":0-100, \"feedback\":[\"..\",\"..\"], \"next_drill_hint\":\"...\"}."
)

SYSTEM_FOLLOW = (
    "Return JSON of the form {\"questions\":[\"short CEFR-consistent questions\"]}"
)

MODEL = os.getenv("VC_MODEL", "gpt-4o-mini")

@app.post("/llm/generate-drills")
async def generate_drills(req: GenReq):
    # Mock fallback
    if _openai_client is None:
        drills = []
        for i in range(req.count):
            drills.append({
                "id": f"mock_{i+1}",
                "title": f"{req.skill.title()} Drill {i+1}",
                "type": req.skill,
                "prompt": f"Talk about {req.topic or 'any topic'} for 60s with clear pacing.",
                "constraints": (req.constraints.model_dump() if req.constraints else None),
            })
        return {"drills": drills}
    # Live call
    messages = [
        {"role": "system", "content": SYSTEM_GEN},
        {"role": "user", "content": f"skill={req.skill}; cefr={req.cefr}; topic={req.topic}; count={req.count}; constraints={req.constraints.model_dump() if req.constraints else {}}"},
    ]
    try:
        resp = _openai_client.chat.completions.create(model=MODEL, messages=messages, temperature=0.7)
        text = resp.choices[0].message.content
        import json, re
        try:
            data = json.loads(text)
        except Exception:
            text = re.search(r"\{[\s\S]*\}", text).group(0)
            data = json.loads(text)
        # ensure IDs/types
        for d in data.get("drills", []):
            d.setdefault("id", os.urandom(4).hex())
            d.setdefault("type", req.skill)
        return data
    except Exception as e:
        logger.warning(f"/llm/generate-drills failed: {e}")
        raise HTTPException(status_code=500, detail="generate-drills failed")

@app.post("/llm/critique")
async def critique(req: CritiqueReq):
    if _openai_client is None:
        score = 75
        fb = [
            "Good clarity overall.",
            "Reduce fillers to <4/min.",
            "Add two emphasis peaks for key nouns.",
        ]
        return {"score": score, "feedback": fb, "next_drill_hint": "Shadow a 60s paragraph at 140 WPM"}
    messages = [
        {"role": "system", "content": SYSTEM_CRIT},
        {"role": "user", "content": f"metrics={req.metrics}; cefr={req.cefr}; skill={req.skill}; transcript=```{req.transcript}```"},
    ]
    try:
        r = _openai_client.chat.completions.create(model=MODEL, messages=messages, temperature=0.4)
        text = r.choices[0].message.content
        import json, re
        try:
            return json.loads(text)
        except Exception:
            text = re.search(r"\{[\s\S]*\}", text).group(0)
            return json.loads(text)
    except Exception as e:
        logger.warning(f"/llm/critique failed: {e}")
        raise HTTPException(status_code=500, detail="critique failed")

@app.post("/llm/followups")
async def followups(req: FollowReq):
    if _openai_client is None:
        return {"questions": [
            f"What landmark do you pass first near {req.topic}?",
            "How would you simplify the route?",
            "Which step could be merged to reduce confusion?",
        ]}
    messages = [
        {"role": "system", "content": SYSTEM_FOLLOW},
        {"role": "user", "content": f"topic={req.topic}; cefr={req.cefr}; count={req.count}"},
    ]
    try:
        r = _openai_client.chat.completions.create(model=MODEL, messages=messages, temperature=0.6)
        text = r.choices[0].message.content
        import json, re
        try:
            return json.loads(text)
        except Exception:
            text = re.search(r"\{[\s\S]*\}", text).group(0)
            return json.loads(text)
    except Exception as e:
        logger.warning(f"/llm/followups failed: {e}")
        raise HTTPException(status_code=500, detail="followups failed")

@app.post("/audio/assess")
async def assess_pronunciation(assessment: AudioAssessment):
    """Assess pronunciation accuracy"""
    try:
        scores = compute_scores(
            assessment.reference_text,
            assessment.hypothesis_text,
            assessment.audio_path
        )
        
        return {
            "phoneme_accuracy": scores.phoneme_acc,
            "word_error_rate": scores.wer,
            "pace_wpm": scores.pace_wpm,
            "overall_score": scores.phoneme_acc,
            "cefr_level": accuracy_to_cefr(scores.phoneme_acc)
        }
    except Exception as e:
        logger.error(f"Assessment failed: {e}")
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")

# WebSocket for real-time communication
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "audio_chunk":
                await _ensure_ctx(websocket)
                ctx = _ws_context.get(websocket)
                chunk_b64 = message.get("data", {}).get("chunk")
                if isinstance(chunk_b64, str):
                    try:
                        chunk_bytes = base64.b64decode(chunk_b64)
                        seg_idx = ctx["seg_idx"]
                        ctx["seg_idx"] += 1
                        seg_path = os.path.join(ctx["seg_dir"], f"seg_{seg_idx:06d}.webm")
                        with open(seg_path, "wb") as f:
                            f.write(chunk_bytes)
                        # transcribe this segment if it's sufficiently large
                        if len(chunk_bytes) > 4096:
                            asyncio.create_task(_transcribe_segment(websocket, seg_path))
                    except Exception as e:
                        logger.warning(f"Failed to buffer/transcribe audio chunk: {e}")

            elif message["type"] == "pcm_chunk":
                # Raw 16-bit PCM, 16kHz, mono
                await _ensure_ctx(websocket)
                ctx = _ws_context.get(websocket)
                try:
                    chunk_b64 = message.get("data", {}).get("chunk")
                    if isinstance(chunk_b64, str):
                        pcm_bytes = base64.b64decode(chunk_b64)
                        with open(ctx["pcm_raw_path"], "ab") as f:
                            f.write(pcm_bytes)
                        # send partial transcription best-effort when we have enough audio
                        if not ctx.get("transcribing") and os.path.getsize(ctx["pcm_raw_path"]) > 8 * 1024:
                            async def _partial():
                                ctx["transcribing"] = True
                                try:
                                    with tempfile.TemporaryDirectory(prefix="vc_pcm_") as td:
                                        wav_path = os.path.join(td, "partial.wav")
                                        _write_wav_from_pcm(ctx["pcm_raw_path"], wav_path)
                                        text = _transcribe_wav(wav_path)
                                        if text:
                                            ctx["full_text"] = text
                                            await manager.send_personal_message({
                                                "type": "transcription",
                                                "data": {"text": text, "confidence": 0.7, "partial": True}
                                            }, websocket)
                                finally:
                                    ctx["transcribing"] = False
                            asyncio.create_task(_partial())
                except Exception as e:
                    logger.warning(f"Failed to handle pcm_chunk: {e}")
                
            elif message["type"] == "session_start":
                await _ensure_ctx(websocket)
                # reset context
                try:
                    ctx = _ws_context.get(websocket)
                    ctx["seg_idx"] = 0
                    ctx["full_text"] = ""
                    # clear old segments
                    for f in os.listdir(ctx["seg_dir"]):
                        try:
                            os.unlink(os.path.join(ctx["seg_dir"], f))
                        except Exception:
                            pass
                    # truncate raw pcm file
                    try:
                        open(ctx["pcm_raw_path"], "wb").close()
                    except Exception:
                        pass
                except Exception:
                    pass
                await manager.send_personal_message({
                    "type": "session_status",
                    "data": {"status": "started", "message": "Session started successfully"}
                }, websocket)
                
            elif message["type"] == "session_end":
                # Sequentially transcribe each saved segment and aggregate text (avoid concat issues)
                try:
                    ctx = _ws_context.get(websocket)
                    text_all = ""
                    if ctx:
                        with tempfile.TemporaryDirectory(prefix="vc_final_") as td:
                            wav_path = os.path.join(td, "final.wav")
                            # Prefer raw PCM accumulation if available
                            if os.path.exists(ctx["pcm_raw_path"]) and os.path.getsize(ctx["pcm_raw_path"]) > 0:
                                _write_wav_from_pcm(ctx["pcm_raw_path"], wav_path)
                                text_all = _transcribe_wav(wav_path)
                            else:
                                # fallback: try segments one-by-one
                                final_text_parts: list[str] = []
                                if os.path.isdir(ctx["seg_dir"]):
                                    seg_files = sorted([
                                        os.path.join(ctx["seg_dir"], f)
                                        for f in os.listdir(ctx["seg_dir"]) if f.endswith('.webm')
                                    ])
                                    for i, seg in enumerate(seg_files):
                                        try:
                                            seg_wav = os.path.join(td, f"seg_{i:04d}.wav")
                                            _ffmpeg_convert_to_wav(seg, seg_wav)
                                            t = _transcribe_wav(seg_wav)
                                            if t:
                                                final_text_parts.append(t)
                                        except Exception as e:
                                            logger.warning(f"Segment {i} transcription failed: {e}")
                                text_all = " ".join(final_text_parts).strip()
                    await manager.send_personal_message({
                        "type": "transcription",
                        "data": {"text": text_all, "confidence": 0.75 if text_all else 0.0}
                    }, websocket)
                except Exception as e:
                    logger.warning(f"Final transcription failed: {e}")
                    await manager.send_personal_message({
                        "type": "transcription",
                        "data": {"text": f"[Transcription failed: {e}]", "confidence": 0.0}
                    }, websocket)
                finally:
                    await manager.send_personal_message({
                        "type": "session_status",
                        "data": {"status": "ended", "message": "Session ended"}
                    }, websocket)
                    await _cleanup_ctx(websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await _cleanup_ctx(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        await _cleanup_ctx(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
