# VoiceCoach — Local Implementation Plan (Laptop Setup)

**Goal:** Run the React dashboard from the canvas with recording, upload fallback, and a small backend for ASR + metrics on your local PC (Hyderabad/IST). Targets: working prototype in **7 days**.

---

## 0) Architecture (dev)

```
[Next.js + Vite/React app]
  ├─ UI (Tailwind + shadcn/ui + Recharts)
  ├─ MediaRecorder (HTTPS/localhost) + Upload fallback
  └─ /asr  /metrics  (HTTP calls)
           ▲
[Backend]
  ├─ Option A: FastAPI + faster‑whisper (local CPU/GPU)
  ├─ Option B: Node/Express + cloud ASR (OpenAI/Deepgram/GCP)
  └─ Shared: WER, fillers, prosody, storage (SQLite)
```

---

## 1) Prerequisites

* **Node.js 20+** (use `fnm` or `nvm`) and **pnpm**: `corepack enable && corepack pin pnpm@9`
* **Python 3.11+**, **pipx** (for FastAPI option)
* **ffmpeg** (`brew install ffmpeg` on macOS; `choco install ffmpeg` on Windows)
* **git**
* **mkcert** (optional, for local HTTPS): `brew install mkcert nss` or Windows installer

> **Mic rule:** Chrome/Edge allow mic on **https** or **[http://localhost](http://localhost)**. Prefer `localhost`; use `mkcert` only if you need a custom domain.

---

## 2) Frontend app (Next.js + Tailwind + shadcn)

```bash
# Create project (Next.js with TypeScript)
pnpm create next-app@latest voicecoach --ts --eslint --tailwind --app --src-dir --import-alias "@/*"
cd voicecoach

# UI libs
pnpm add lucide-react recharts class-variance-authority tailwind-merge

# shadcn/ui
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button card badge switch tabs separator textarea
```

Update **`tailwind.config.ts`** to include `./src/**/*.{ts,tsx}`. Ensure `@` path alias exists in `tsconfig.json`.

### Add the canvas component

* Create `src/app/page.tsx` and paste the latest **“Voice Coach Dashboard (react) — Merged & Ux Polish”** code from the canvas.
* Confirm imports like `@/components/ui/button` resolve (shadcn generates them under `src/components/ui`).

### Run

```bash
pnpm dev
# open http://localhost:3000  (mic should work on localhost)
```

---

## 3) Backend — Option A (Recommended): FastAPI + faster‑whisper (local)

### Install & scaffold

```bash
# New terminal
mkdir voicecoach-backend && cd voicecoach-backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install fastapi uvicorn[standard] python-multipart pydantic==2.*
pip install faster-whisper==1.*
```

### `main.py`

```python
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from faster_whisper import WhisperModel
import uvicorn, tempfile

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])

# Load small model for dev (change to medium for quality)
model = WhisperModel("small", compute_type="int8")

class ASRResp(BaseModel):
    text: str
    duration_sec: float

@app.post("/asr", response_model=ASRResp)
async def asr(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=True) as tmp:
        tmp.write(await file.read()); tmp.flush()
        segments, info = model.transcribe(tmp.name, vad_filter=True)
        text = " ".join([s.text.strip() for s in segments])
        return {"text": text, "duration_sec": info.duration}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Run:

```bash
uvicorn main:app --reload --port 8000
```

### Wire the frontend

* Add a simple fetch in the React component (after recording/ upload) to `POST /asr` with the audio `Blob` or selected file.
* Update transcript textarea with `asr.text`; replace duration with `asr.duration_sec` for WPM accuracy.

---

## 4) Backend — Option B: Node/Express + Cloud ASR

Use if you prefer not to run local models.

```bash
mkdir voicecoach-api && cd voicecoach-api
pnpm init -y && pnpm add express cors multer node-fetch zod
pnpm add -D ts-node typescript @types/express @types/multer @types/node
npx tsc --init
```

`index.ts`

```ts
import express from "express"; import cors from "cors"; import multer from "multer";
const app = express(); app.use(cors({ origin: "http://localhost:3000" }));
const upload = multer();
app.post("/asr", upload.single("file"), async (req, res) => {
  const audio = req.file; if (!audio) return res.status(400).send("no file");
  // TODO: call your provider SDK/HTTP here (OpenAI/Deepgram/GCP)
  // Return { text, duration_sec } shape
  res.json({ text: "(mock) hello world", duration_sec: 10 });
});
app.listen(8000, () => console.log("api on :8000"));
```

Run: `pnpm ts-node index.ts`

> Plug in any ASR provider; keep response contract `{text, duration_sec}` to avoid touching UI logic.

---

## 5) Metrics & WER service (backend)

Add WER for scripted drills.

```bash
pip install python-Levenshtein rapidfuzz
```

```python
from fastapi import Body
from pydantic import BaseModel
from rapidfuzz.distance import Levenshtein

class WERReq(BaseModel):
    reference: str
    hypothesis: str

@app.post("/metrics/wer")
async def wer(req: WERReq):
    ref = req.reference.strip().split()
    hyp = req.hypothesis.strip().split()
    # simple WER: edit_distance / len(ref)
    ed = Levenshtein.distance(" ".join(ref), " ".join(hyp))
    return {"wer": round(ed / max(1, len(" ".join(ref))), 3)}
```

---

## 6) Frontend integration snippets

```ts
// Post audio to /asr
async function transcribeAudio(blob: Blob) {
  const fd = new FormData(); fd.append("file", blob, "audio.webm");
  const r = await fetch("http://localhost:8000/asr", { method: "POST", body: fd });
  if (!r.ok) throw new Error("ASR failed");
  return (await r.json()) as { text: string; duration_sec: number };
}
```

Use response to set `transcript` and override `duration` with `duration_sec` for accurate WPM.

---

## 7) HTTPS (optional) with mkcert

```bash
mkcert -install
mkcert localhost 127.0.0.1
# Serve Next.js with a proxy like Caddy or use vite preview with https.
```

**Tip:** You usually don’t need HTTPS locally; `http://localhost` already grants mic.

---

## 8) Data persistence (optional for week‑1)

* Add **SQLite** via Prisma to store sessions: `pnpm add @prisma/client && pnpm add -D prisma`
* Schema: `Session(id, drillId, createdAt, wpm, fillerPerMin, wer, pitchRange)`

---

## 9) Testing

### Frontend unit tests (Jest + RTL)

```bash
pnpm add -D jest @types/jest ts-jest @testing-library/react @testing-library/jest-dom
npx ts-jest config:init
```

`computeMetrics.test.ts`

```ts
import { expect, test } from "@jest/globals";
import { computeMetrics } from "../path/to/module"; // refactor to export
const drill = { id: "d", title: "t", type: "descriptive" } as any;

test("counts words and wpm", () => {
  const r = computeMetrics("one two three", 30, drill);
  expect(r.words).toBe(3); expect(r.wpm).toBe(6);
});

test("detects fillers", () => {
  const r = computeMetrics("um I uh like it", 60, drill);
  expect(r.fillerCount).toBe(3); expect(r.fillerPerMin).toBe(3);
});
```

### Backend tests (FastAPI)

```bash
pip install pytest httpx
```

`test_api.py`

```python
from fastapi.testclient import TestClient
from main import app

def test_health():
    c = TestClient(app)
    r = c.post("/metrics/wer", json={"reference":"a b","hypothesis":"a"})
    assert r.status_code == 200 and "wer" in r.json()
```

---

## 10) Scripts & DX

**frontend `package.json`**

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint",
    "test": "jest"
  }
}
```

**backend (FastAPI)**

```bash
uvicorn main:app --reload --port 8000
```

---

## 11) Day‑by‑Day Plan (7 days)

* **Day 1:** Scaffold FE, run UI; verify mic works on `localhost`. Add upload fallback smoke test.
* **Day 2:** FastAPI `/asr` with faster‑whisper (small). Return `{text, duration_sec}`.
* **Day 3:** Wire ASR -> transcript; compute WPM from server duration. Add `/metrics/wer`.
* **Day 4:** Persist last 10 sessions in memory/SQLite; show chart from data.
* **Day 5:** Prosody v0 (pitch range via `librosa` or `parselmouth`) — optional.
* **Day 6:** Polish UX: sticky metrics, keyboard shortcuts (R to record), toasts.
* **Day 7:** Tests + docs; record before/after clip; KPI check.

---

## 12) Troubleshooting

* **NotAllowedError:** Ensure Chrome, **localhost** or **HTTPS**, and mic permission allowed in the address bar.
* **No audio in Safari:** Use `audio/mp4` (`MediaRecorder` may not support WebM). Consider `recorder-js` lib fallback.
* **CORS:** Backend must allow `http://localhost:3000` origin.
* **Model too slow:** Switch to `tiny` or `base` models for faster‑whisper.

---

## 13) Open Questions (confirm before I code)

1. When mic access is **denied**, should **Record** stay disabled (current) or show a retry prompt & link to settings?
2. Do you prefer **local ASR (FastAPI)** or **cloud ASR** for week‑1?
3. Storage: keep sessions only in memory this week, or add **SQLite** now?

> Reply with choices; I’ll wire the corresponding pieces immediately.


next plan 
# VoiceCoach — LLM Integration (frontend + backend)

This doc adds **LLM-powered drill generation, critique, and coaching** to your React dashboard. It includes API contracts, FastAPI backend (Python 3.11), and React wiring snippets that work with your existing component *Voice Coach Dashboard (react) — Merged & Ux Polish*.

---

## 1) Feature set

1. **Drill Generator** — create n drills (questions/prompts) by CEFR level, skill (articulation/descriptive/emotion/instructional/narrative), topic, and constraints (e.g., banned words). Output objects align with your `Drill` type.
2. **Adaptive Follow‑ups** — after a recording/transcript + metrics (WPM, fillers/min, banned-hits), produce targeted follow‑up questions.
3. **Auto‑Critique** — rubric‑based feedback (clarity, pacing, prosody, vocabulary), 1–2 actionable tips, and a single overall score (0–100).
4. **Paraphrase/Shadow Lines** — generate lines for shadowing with syllable count and stress markers (optional).

---

## 2) API contract (backend)

All JSON; CORS allows `http://localhost:3000`.

### POST `/llm/generate-drills`

**Body**

```json
{
  "skill": "descriptive",
  "cefr": "B2",
  "topic": "Hyderabad street food",
  "count": 3,
  "constraints": {"banned_words": ["delicious", "tasty"]}
}
```

**Response**

```json
{
  "drills": [
    {"id":"gen_001","title":"Describe a Breakfast Plate","type":"descriptive","prompt":"Describe ...","constraints":{"banned_words":["delicious","tasty"]}},
    {"id":"gen_002","title":"Smell and Texture Focus","type":"descriptive","prompt":"Focus on ..."}
  ]
}
```

### POST `/llm/critique`

**Body**

```json
{
  "transcript": "...",
  "metrics": {"wpm": 142, "filler_per_min": 3.5, "banned_hits": 0},
  "cefr": "B2",
  "skill": "narrative"
}
```

**Response**

```json
{
  "score": 78,
  "feedback": ["Good pacing...", "Reduce fillers ..."],
  "next_drill_hint": "Try a 60s story with 2 contrasts; emphasize nouns."
}
```

### POST `/llm/followups`

**Body**

```json
{"topic":"giving directions to Charminar","cefr":"B2","count":5}
```

**Response**

```json
{"questions":["Which landmark ...?","How would you ...?"]}
```

---

## 3) Backend — FastAPI + OpenAI (robust with mock fallback)

Create `main.py`:

````python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, uuid

try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

# ---------- Models ----------
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

# ---------- Helpers ----------
SYSTEM_GEN = """
You are VoiceCoach, generating CEFR-appropriate drills. Reply **only JSON**.
Shape: {"drills":[{"id":"string","title":"string","type":"one of: articulation|descriptive|emotion|instructional|narrative","prompt":"string","script":"optional string","constraints":{"banned_words":["..."]}}]}
IDs must be short and unique. Keep titles concise; prompts 1-3 sentences.
"""

SYSTEM_CRIT = """
You are a concise speech coach. Given transcript + metrics, return JSON:
{"score":0-100, "feedback":["..",".."], "next_drill_hint":"..."}
Consider clarity, pacing, fillers, vocabulary variety, and prosody cues.
"""

SYSTEM_FOLLOW = "Return JSON of the form {\"questions\":["""short CEFR-consistent questions"""]}"

MODEL = os.getenv("VC_MODEL", "gpt-4o-mini")

# ---------- Endpoints ----------
@app.post("/llm/generate-drills")
def generate_drills(req: GenReq):
    if client is None or os.getenv("OPENAI_API_KEY") is None:
        # Mock fallback for offline/demo use
        drills = []
        for i in range(req.count):
            drills.append({
                "id": f"mock_{i+1}",
                "title": f"{req.skill.title()} Drill {i+1}",
                "type": req.skill,
                "prompt": f"Talk about {req.topic or 'any topic'} for 60s with clear pacing.",
                "constraints": req.constraints.model_dump() if req.constraints else None,
            })
        return {"drills": drills}
    # Live call
    messages = [
        {"role":"system","content":SYSTEM_GEN},
        {"role":"user","content": f"skill={req.skill}; cefr={req.cefr}; topic={req.topic}; count={req.count}; constraints={req.constraints.model_dump() if req.constraints else {}}"}
    ]
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.7)
    import json
    text = resp.choices[0].message.content
    try:
        data = json.loads(text)
    except Exception:
        # fallback robust parse
        import re
        text = re.search(r"\{[\s\S]*\}", text).group(0)
        data = json.loads(text)
    # ensure IDs
    for d in data.get("drills", []):
        d.setdefault("id", uuid.uuid4().hex[:8])
        d.setdefault("type", req.skill)
    return data

@app.post("/llm/critique")
def critique(req: CritiqueReq):
    if client is None or os.getenv("OPENAI_API_KEY") is None:
        score = 75
        fb = ["Good clarity overall", "Reduce fillers to <4/min", "Add two emphasis peaks for key nouns"]
        return {"score": score, "feedback": fb, "next_drill_hint": "Shadow a 60s paragraph at 140 WPM"}
    messages = [
        {"role":"system","content": SYSTEM_CRIT},
        {"role":"user","content": f"metrics={req.metrics}; cefr={req.cefr}; skill={req.skill}; transcript=```{req.transcript}```"}
    ]
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.4)
    import json, re
    text = resp.choices[0].message.content
    try:
        return json.loads(text)
    except Exception:
        text = re.search(r"\{[\s\S]*\}", text).group(0)
        return json.loads(text)

@app.post("/llm/followups")
def followups(req: FollowReq):
    if client is None or os.getenv("OPENAI_API_KEY") is None:
        return {"questions":[f"What landmark do you pass first near {req.topic}?", "How would you simplify the route?"]}
    messages=[{"role":"system","content":SYSTEM_FOLLOW}, {"role":"user","content":f"topic={req.topic}; cefr={req.cefr}; count={req.count}"}]
    r = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.6)
    import json, re
    text = r.choices[0].message.content
    try:
        return json.loads(text)
    except Exception:
        text = re.search(r"\{[\s\S]*\}", text).group(0)
        return json.loads(text)
````

Run:

```bash
uvicorn main:app --reload --port 8000
```

> **Note**: If `OPENAI_API_KEY` is unset, endpoints return **mock** data so the UI remains functional.

---

## 4) React wiring (new panel)

Add this small client helper in your React app (e.g., `src/lib/llm.ts`):

```ts
export async function genDrills(body: any) {
  const r = await fetch("http://localhost:8000/llm/generate-drills", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  if(!r.ok) throw new Error("gen-drills failed");
  return r.json();
}
export async function critique(body: any){
  const r = await fetch("http://localhost:8000/llm/critique", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  if(!r.ok) throw new Error("critique failed");
  return r.json();
}
export async function followups(body:any){
  const r = await fetch("http://localhost:8000/llm/followups", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  if(!r.ok) throw new Error("followups failed");
  return r.json();
}
```

### UI component (drop into your dashboard)

```tsx
import { useState } from "react";
import { genDrills, critique, followups } from "@/lib/llm";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export function LlmPanel({ onInsert }: { onInsert: (drills:any[])=>void }){
  const [loading, setLoading] = useState(false);
  const [skill, setSkill] = useState("descriptive");
  const [cefr, setCefr] = useState("B2");
  const [topic, setTopic] = useState("");
  const [items, setItems] = useState<any[]>([]);

  async function handleGen(){
    setLoading(true);
    try{
      const data = await genDrills({ skill, cefr, topic, count: 3, constraints: { banned_words: ["delicious","tasty"] }});
      setItems(data.drills||[]);
    } finally { setLoading(false); }
  }

  return (
    <Card className="bg-neutral-900/40 border-neutral-800">
      <CardHeader><CardTitle className="text-sm">LLM Generator</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-3 gap-2">
          <select className="bg-neutral-950 border border-neutral-800 rounded-md p-2" value={skill} onChange={(e)=>setSkill(e.target.value)}>
            {['articulation','descriptive','emotion','instructional','narrative'].map(s=> <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="bg-neutral-950 border border-neutral-800 rounded-md p-2" value={cefr} onChange={(e)=>setCefr(e.target.value)}>
            {['A2','B1','B2','C1'].map(c=> <option key={c} value={c}>{c}</option>)}
          </select>
          <Input placeholder="Topic (optional)" value={topic} onChange={(e)=>setTopic(e.target.value)} />
        </div>
        <Button disabled={loading} onClick={handleGen}>{loading? 'Generating…':'Generate'}</Button>
        {items.length>0 && (
          <div className="space-y-2">
            {items.map((d)=> (
              <div key={d.id} className="p-2 rounded-lg border border-neutral-800">
                <div className="font-medium">{d.title} <Badge variant="secondary" className="ml-2">{d.type}</Badge></div>
                {d.script && <div className="text-neutral-400 text-xs mt-1">{d.script}</div>}
                {d.prompt && <div className="text-neutral-300 mt-1">{d.prompt}</div>}
              </div>
            ))}
            <Button variant="outline" onClick={()=>onInsert(items)}>Insert into Drills</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

Usage example in your dashboard:

```tsx
// inside your page component
import { LlmPanel } from "@/components/llm-panel"; // adjust path

<LlmPanel onInsert={(newDrills)=> setDrills((prev)=> [...prev, ...newDrills])} />
```

> If your drills are constant today, refactor to `const [drills, setDrills] = useState(DRILLS);` and replace references accordingly.

---

## 5) Prompting (templates)

**Generator**

```
System: You are VoiceCoach, expert ESL creator. Output STRICT JSON schema (see contract). Keep CEFR alignment for {cefr}.
User: Create {count} {skill} drills about "{topic}". Avoid banned words: {banned_words}. Titles concise; prompts 1–3 sentences.
```

**Critique**

````
System: Speech coach. Return JSON {score, feedback[], next_drill_hint}. Consider metrics and transcript.
User: metrics={...}; transcript=```...```
````

**Follow‑ups**

```
System: Return JSON only. CEFR={cefr}.
User: topic={topic}; count={count}
```

---

## 6) Tests (backend)

`tests/test_contracts.py`

```python
from fastapi.testclient import TestClient
from main import app

c = TestClient(app)

def test_gen_mock():
    r = c.post('/llm/generate-drills', json={'skill':'descriptive','cefr':'B2','topic':'biryani','count':2})
    assert r.status_code==200
    data = r.json(); assert 'drills' in data and len(data['drills'])==2

def test_followups_mock():
    r = c.post('/llm/followups', json={'topic':'metro directions','cefr':'B2','count':3})
    assert r.status_code==200
    q = r.json()['questions']; assert isinstance(q, list) and len(q)>0
```

Run: `pytest -q`

---

## 7) Security & costs

* Keep the **system prompts** short and deterministic; set `temperature 0.4–0.7`.
* Pass only necessary transcript text; avoid storing PII.
* Rate limit per IP; cache LLM responses by `(skill, topic, cefr, count)` during dev.

---

## 8) Roadmap hooks

* Add **RAG** for domain topics (upload PDFs, fetch key facts to seed prompts).
* Fine‑tune/generate with **topic packs** for Indian English contexts (Hyderabad, Bengaluru tech scenes, PSU interviews, etc.).
* Rubric calibration by CEFR band descriptors -> more stable `score`.

